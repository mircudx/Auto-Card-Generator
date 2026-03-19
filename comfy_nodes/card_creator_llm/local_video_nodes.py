"""Local media utility nodes for ComfyUI.

This module provides a local equivalent of the Replicate zip2mp4 behavior:
- accepts up to 50 video inputs (+ optional audio)
- concatenates clips into one mp4
- can loop source videos to match audio length
- can loop audio to match video length
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List
from urllib import parse, request


def _normalize_path_or_url(value: str) -> str:
    return str(value or "").strip()


def _is_http_url(value: str) -> bool:
    try:
        parsed = parse.urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"}


def _resolve_binary(binary_name_or_path: str) -> str:
    value = str(binary_name_or_path or "").strip() or "ffmpeg"
    if os.path.isabs(value) or os.path.sep in value:
        if Path(value).exists():
            return value
        raise RuntimeError(f"Binary not found at path: {value}")

    found = shutil.which(value)
    if not found:
        raise RuntimeError(
            f"Binary '{value}' was not found in PATH. Install ffmpeg/ffprobe and restart ComfyUI."
        )
    return found


def _run_cmd(args: List[str], timeout_seconds: int) -> str:
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=max(10, int(timeout_seconds)),
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        details = stderr if stderr else stdout
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(args)}\n{details}")
    return (proc.stdout or "").strip()


def _ffprobe_duration_seconds(ffprobe_bin: str, media_path: str, timeout_seconds: int) -> float:
    args = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        media_path,
    ]
    try:
        out = _run_cmd(args, timeout_seconds=timeout_seconds)
        return float(out.strip())
    except Exception:
        return 0.0


def _download_to_temp(url: str, temp_dir: Path, prefix: str, timeout_seconds: int) -> str:
    parsed = parse.urlparse(url)
    ext = Path(parsed.path).suffix or ".bin"
    name = f"{prefix}_{int(time.time() * 1000)}{ext}"
    output = temp_dir / name
    req = request.Request(url, headers={"User-Agent": "card-creator-local-node"})
    with request.urlopen(req, timeout=max(10, int(timeout_seconds))) as resp:
        data = resp.read()
    output.write_bytes(data)
    return str(output)


def _materialize_media(value: str, temp_dir: Path, prefix: str, timeout_seconds: int) -> str:
    source = _normalize_path_or_url(value)
    if not source:
        return ""
    if _is_http_url(source):
        return _download_to_temp(source, temp_dir=temp_dir, prefix=prefix, timeout_seconds=timeout_seconds)

    p = Path(source)
    if not p.exists():
        raise RuntimeError(f"Input file does not exist: {source}")
    return str(p.resolve())


def _build_output_path(prefix: str) -> str:
    try:
        import folder_paths  # type: ignore

        out_dir = Path(folder_paths.get_output_directory())
    except Exception:
        out_dir = Path.cwd() / "output"

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_prefix = (prefix or "zip2mp4").strip().replace(" ", "_")
    return str((out_dir / f"{safe_prefix}_{ts}.mp4").resolve())


class MirVideoMerger:
    """Concatenate up to 50 videos locally into one mp4, with optional audio."""

    CATEGORY = "Card Creator/Local Video"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "INT", "FLOAT")
    RETURN_NAMES = ("output_video_path", "debug_json", "input_video_count", "output_duration_seconds")

    @classmethod
    def INPUT_TYPES(cls):
        optional_videos: Dict[str, tuple] = {}
        for idx in range(2, 51):
            optional_videos[f"video{idx}"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "dynamicPrompts": True,
                },
            )

        optional_inputs: Dict[str, tuple] = {
            "audio": (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "dynamicPrompts": True,
                },
            ),
            "ffmpeg_path": (
                "STRING",
                {
                    "default": "ffmpeg",
                    "multiline": False,
                    "dynamicPrompts": False,
                },
            ),
            "ffprobe_path": (
                "STRING",
                {
                    "default": "ffprobe",
                    "multiline": False,
                    "dynamicPrompts": False,
                },
            ),
        }
        optional_inputs.update(optional_videos)

        return {
            "required": {
                "video1": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": True,
                    },
                ),
                "loop_audio": ("BOOLEAN", {"default": False}),
                "loop_videos": ("BOOLEAN", {"default": False}),
                "output_file_prefix": (
                    "STRING",
                    {
                        "default": "zip2mp4_local",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "target_fps": (
                    "INT",
                    {
                        "default": 30,
                        "min": 12,
                        "max": 120,
                        "step": 1,
                    },
                ),
                "crf": (
                    "INT",
                    {
                        "default": 18,
                        "min": 0,
                        "max": 51,
                        "step": 1,
                    },
                ),
                "preset": (
                    ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"),
                    {"default": "medium"},
                ),
                "timeout_seconds": (
                    "INT",
                    {
                        "default": 600,
                        "min": 30,
                        "max": 7200,
                        "step": 1,
                    },
                ),
                "max_video_repeats": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "max": 200,
                        "step": 1,
                    },
                ),
                "keep_temp_files": ("BOOLEAN", {"default": False}),
            },
            "optional": optional_inputs,
        }

    def run(
        self,
        video1: str,
        loop_audio: bool,
        loop_videos: bool,
        output_file_prefix: str,
        target_fps: int,
        crf: int,
        preset: str,
        timeout_seconds: int,
        max_video_repeats: int,
        keep_temp_files: bool,
        audio: str = "",
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        **kwargs,
    ):
        ffmpeg_bin = _resolve_binary(ffmpeg_path)
        ffprobe_bin = _resolve_binary(ffprobe_path)

        raw_video_sources = [_normalize_path_or_url(video1)]
        for idx in range(2, 51):
            raw_video_sources.append(_normalize_path_or_url(kwargs.get(f"video{idx}", "")))
        raw_video_sources = [x for x in raw_video_sources if x]
        if not raw_video_sources:
            raise RuntimeError("At least one video input is required (video1).")

        temp_dir_path = Path(tempfile.mkdtemp(prefix="cc_zip2mp4_local_"))
        temp_keep = bool(keep_temp_files)

        try:
            video_paths = [
                _materialize_media(src, temp_dir=temp_dir_path, prefix=f"video_{i+1}", timeout_seconds=timeout_seconds)
                for i, src in enumerate(raw_video_sources)
            ]

            audio_path = ""
            if _normalize_path_or_url(audio):
                audio_path = _materialize_media(
                    audio,
                    temp_dir=temp_dir_path,
                    prefix="audio",
                    timeout_seconds=timeout_seconds,
                )

            if loop_videos and audio_path:
                base_duration = sum(
                    _ffprobe_duration_seconds(ffprobe_bin, p, timeout_seconds=timeout_seconds) for p in video_paths
                )
                audio_duration = _ffprobe_duration_seconds(ffprobe_bin, audio_path, timeout_seconds=timeout_seconds)
                if base_duration > 0.0 and audio_duration > base_duration:
                    repeats = int(math.ceil(audio_duration / base_duration))
                    repeats = max(1, min(int(max_video_repeats), repeats))
                    video_paths = video_paths * repeats

            concat_video = str((temp_dir_path / "concatenated_video.mp4").resolve())

            concat_cmd: List[str] = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
            for p in video_paths:
                concat_cmd.extend(["-i", p])

            filters = []
            concat_inputs = []
            for i in range(len(video_paths)):
                filters.append(
                    f"[{i}:v]fps={int(target_fps)},scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,format=yuv420p[v{i}]"
                )
                concat_inputs.append(f"[v{i}]")

            filters.append(f"{''.join(concat_inputs)}concat=n={len(video_paths)}:v=1:a=0[vout]")
            concat_cmd.extend(
                [
                    "-filter_complex",
                    ";".join(filters),
                    "-map",
                    "[vout]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    str(preset),
                    "-crf",
                    str(int(crf)),
                    "-pix_fmt",
                    "yuv420p",
                    concat_video,
                ]
            )
            _run_cmd(concat_cmd, timeout_seconds=timeout_seconds)

            final_output = _build_output_path(output_file_prefix)

            if audio_path:
                mux_cmd: List[str] = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
                if loop_audio:
                    mux_cmd.extend(["-stream_loop", "-1"])
                mux_cmd.extend(
                    [
                        "-i",
                        audio_path,
                        "-i",
                        concat_video,
                        "-map",
                        "1:v:0",
                        "-map",
                        "0:a:0",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        "-shortest",
                        final_output,
                    ]
                )
                _run_cmd(mux_cmd, timeout_seconds=timeout_seconds)
            else:
                shutil.copy2(concat_video, final_output)

            output_duration = _ffprobe_duration_seconds(
                ffprobe_bin,
                final_output,
                timeout_seconds=timeout_seconds,
            )

            debug_payload = {
                "engine": "local_ffmpeg",
                "input_video_count": len(raw_video_sources),
                "effective_video_count_after_loop": len(video_paths),
                "has_audio": bool(audio_path),
                "loop_audio": bool(loop_audio),
                "loop_videos": bool(loop_videos),
                "target_fps": int(target_fps),
                "crf": int(crf),
                "preset": str(preset),
                "output_video_path": final_output,
                "output_duration_seconds": round(float(output_duration), 3),
                "temp_dir": str(temp_dir_path),
                "keep_temp_files": bool(temp_keep),
            }

            return (
                final_output,
                json.dumps(debug_payload, ensure_ascii=True, indent=2),
                int(len(raw_video_sources)),
                float(round(float(output_duration), 3)),
            )
        finally:
            if not temp_keep and temp_dir_path.exists():
                shutil.rmtree(temp_dir_path, ignore_errors=True)


NODE_CLASS_MAPPINGS = {
    "MirVideoMerger": MirVideoMerger,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MirVideoMerger": "MirVideoMerger",
}
