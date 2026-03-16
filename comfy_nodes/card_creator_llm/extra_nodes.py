"""Additional Card Creator nodes for OpenAI and Kling plan parsing."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from urllib import error, request

from .templates import DEFAULT_KLING_NEGATIVE


def _safe_json_loads(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _extract_json_candidate(value: str) -> str:
    if not isinstance(value, str):
        return ""
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        return value[start : end + 1]
    return ""


def _extract_openai_output_text(payload: Dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    if isinstance(direct, list):
        joined = "\n".join(str(x) for x in direct if isinstance(x, str) and x.strip()).strip()
        if joined:
            return joined

    chunks: List[str] = []
    output_items = payload.get("output", [])
    if isinstance(output_items, list):
        for item in output_items:
            if not isinstance(item, dict):
                continue
            content_items = item.get("content", [])
            if not isinstance(content_items, list):
                continue
            for part in content_items:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())

    return "\n".join(chunks).strip()


class CCTextInput:
    """Simple text source node for reusable text inputs."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "emit"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                )
            }
        }

    def emit(self, text: str):
        return (text.strip(),)


class CCOpenAIResponsesNode:
    """Calls OpenAI Responses API with explicit system and user prompts."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("output_text", "raw_json", "usage_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "user_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "system_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "model": (("gpt-5.4", "gpt-5", "gpt-5-mini", "gpt-5-nano"), {"default": "gpt-5.4"}),
                "reasoning_effort": (("minimal", "low", "medium", "high"), {"default": "high"}),
                "max_output_tokens": (
                    "INT",
                    {
                        "default": 3500,
                        "min": 256,
                        "max": 16000,
                        "step": 1,
                    },
                ),
                "timeout_seconds": (
                    "INT",
                    {
                        "default": 180,
                        "min": 10,
                        "max": 600,
                        "step": 1,
                    },
                ),
            },
            "optional": {
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "base_url": (
                    "STRING",
                    {
                        "default": "https://api.openai.com/v1/responses",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "metadata_tag": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
            },
        }

    def run(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        reasoning_effort: str,
        max_output_tokens: int,
        timeout_seconds: int,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1/responses",
        metadata_tag: str = "",
    ):
        resolved_api_key = api_key.strip() or os.getenv("OPENAI_API_KEY", "").strip()
        if not resolved_api_key:
            raise ValueError("Missing OpenAI API key. Set api_key input or OPENAI_API_KEY env var.")

        payload: Dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt,
                        }
                    ],
                },
            ],
            "reasoning": {"effort": reasoning_effort},
            "max_output_tokens": int(max_output_tokens),
        }

        if metadata_tag.strip():
            payload["metadata"] = {"tag": metadata_tag.strip()}

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=base_url.strip() or "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=max(10, int(timeout_seconds))) as resp:
                raw_text = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {err_body}")
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}")

        payload_json = _safe_json_loads(raw_text)
        if not isinstance(payload_json, dict):
            raise RuntimeError(f"OpenAI returned non-JSON response: {raw_text[:500]}")

        output_text = _extract_openai_output_text(payload_json)
        if not output_text:
            output_text = json.dumps(payload_json, ensure_ascii=True)

        usage = payload_json.get("usage", {})
        return (
            output_text,
            json.dumps(payload_json, ensure_ascii=True, indent=2),
            json.dumps(usage, ensure_ascii=True, indent=2),
        )


class CCKlingPlanParser:
    """Parses LLM JSON plan and returns one segment payload for Kling."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "parse"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "FLOAT", "INT", "STRING")
    RETURN_NAMES = (
        "kling_prompt_for_node",
        "kling_prompt",
        "negative_prompt",
        "segment_script",
        "location",
        "estimated_seconds",
        "segment_count",
        "debug_json",
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "llm_json_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "segment_index": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 64,
                        "step": 1,
                    },
                ),
                "fallback_negative": (
                    "STRING",
                    {
                        "default": DEFAULT_KLING_NEGATIVE,
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "include_negative_in_prompt": ("BOOLEAN", {"default": True}),
            }
        }

    def parse(
        self,
        llm_json_text: str,
        segment_index: int,
        fallback_negative: str,
        include_negative_in_prompt: bool,
    ):
        parse_mode = "direct_json"
        payload = _safe_json_loads(llm_json_text)

        if not isinstance(payload, dict):
            payload = _safe_json_loads(_extract_json_candidate(llm_json_text))
            parse_mode = "extracted_json"

        if not isinstance(payload, dict):
            prompt = llm_json_text.strip()
            negative = fallback_negative.strip() or DEFAULT_KLING_NEGATIVE
            prompt_for_node = prompt
            if include_negative_in_prompt and negative:
                prompt_for_node = f"{prompt}\n\nExclude: {negative}".strip()
            debug_payload = {
                "parse_mode": "fallback_plaintext",
                "reason": "Could not parse JSON",
                "segment_index_requested": int(segment_index),
            }
            return (
                prompt_for_node,
                prompt,
                negative,
                "",
                "",
                float(0.0),
                int(1),
                json.dumps(debug_payload, ensure_ascii=True, indent=2),
            )

        segments = payload.get("segments", [])
        if not isinstance(segments, list) or not segments:
            prompt = str(payload.get("kling_prompt", "")).strip() or llm_json_text.strip()
            negative = str(payload.get("negative_prompt", "")).strip() or fallback_negative.strip() or DEFAULT_KLING_NEGATIVE
            prompt_for_node = prompt
            if include_negative_in_prompt and negative:
                prompt_for_node = f"{prompt}\n\nExclude: {negative}".strip()
            debug_payload = {
                "parse_mode": parse_mode,
                "reason": "No segments array",
                "segment_index_requested": int(segment_index),
            }
            return (
                prompt_for_node,
                prompt,
                negative,
                str(payload.get("script_chunk", "")).strip(),
                str(payload.get("location", "")).strip(),
                float(payload.get("estimated_speech_seconds", 0.0) or 0.0),
                int(1),
                json.dumps(debug_payload, ensure_ascii=True, indent=2),
            )

        safe_index = max(1, int(segment_index))
        selected_position = min(safe_index, len(segments)) - 1
        selected = segments[selected_position] if isinstance(segments[selected_position], dict) else {}

        kling_prompt = str(selected.get("kling_prompt", "")).strip() or str(selected.get("prompt", "")).strip()
        negative_prompt = str(selected.get("negative_prompt", "")).strip() or fallback_negative.strip() or DEFAULT_KLING_NEGATIVE
        segment_script = str(selected.get("script_chunk", "")).strip() or str(selected.get("text", "")).strip()

        location = str(selected.get("location", "")).strip()
        if not location:
            global_info = payload.get("global", {})
            if isinstance(global_info, dict):
                location = str(global_info.get("location_anchor", "")).strip()

        estimated_seconds_raw = selected.get("estimated_speech_seconds", selected.get("estimated_seconds", 0.0))
        try:
            estimated_seconds = float(estimated_seconds_raw)
        except (TypeError, ValueError):
            estimated_seconds = 0.0

        kling_prompt_for_node = kling_prompt
        if include_negative_in_prompt and negative_prompt:
            kling_prompt_for_node = f"{kling_prompt}\n\nExclude: {negative_prompt}".strip()

        debug_payload = {
            "parse_mode": parse_mode,
            "segment_index_requested": int(segment_index),
            "segment_index_used": int(selected.get("segment_index", selected_position + 1)),
            "total_segments": len(segments),
        }

        return (
            kling_prompt_for_node,
            kling_prompt,
            negative_prompt,
            segment_script,
            location,
            float(round(estimated_seconds, 2)),
            int(len(segments)),
            json.dumps(debug_payload, ensure_ascii=True, indent=2),
        )
try:
    from comfy_execution.graph import ExecutionBlocker
except Exception:
    class ExecutionBlocker:  # type: ignore[override]
        def __init__(self, message=None):
            self.message = message


class CCSegmentImageGate:
    """Conditionally passes an IMAGE or blocks downstream execution."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "gate"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_or_block",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "segment_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 64,
                        "step": 1,
                    },
                ),
                "segment_index": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 64,
                        "step": 1,
                    },
                ),
                "enabled": ("BOOLEAN", {"default": True}),
                "image": ("IMAGE", {"lazy": True}),
            }
        }

    @classmethod
    def check_lazy_status(cls, segment_count, segment_index, enabled, image=None):
        active = bool(enabled) and int(segment_index) <= int(segment_count)
        if active and image is None:
            return ["image"]
        return []

    def gate(self, segment_count: int, segment_index: int, enabled: bool, image=None):
        active = bool(enabled) and int(segment_index) <= int(segment_count)
        if not active:
            return (ExecutionBlocker(None),)
        if image is None:
            return (ExecutionBlocker(f"Missing start frame for active segment {segment_index}"),)
        return (image,)

class CCFramePairPlanner:
    """Builds start/end frame pairing plan for 10s Kling segments."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "plan"
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("pairs_json", "pairs_text", "required_frame_count")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "segment_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 64,
                        "step": 1,
                    },
                ),
                "available_frame_count": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 128,
                        "step": 1,
                    },
                ),
                "start_frame_index": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 128,
                        "step": 1,
                    },
                ),
            }
        }

    def plan(self, segment_count: int, available_frame_count: int, start_frame_index: int):
        safe_segments = max(1, int(segment_count))
        safe_start = max(1, int(start_frame_index))
        required_frame_count = safe_start + safe_segments

        if int(available_frame_count) <= 0:
            available_max_index = required_frame_count
            availability_mode = "assumed_required"
        else:
            available_max_index = safe_start + int(available_frame_count) - 1
            availability_mode = "explicit"

        pairs = []
        lines = []
        for i in range(safe_segments):
            segment_idx = i + 1
            start_idx = safe_start + i
            end_idx_candidate = start_idx + 1
            has_end = end_idx_candidate <= available_max_index
            end_idx = end_idx_candidate if has_end else None

            pair = {
                "segment_index": segment_idx,
                "start_frame_index": start_idx,
                "end_frame_index": end_idx,
                "end_frame_missing": not has_end,
                "seconds_window": [i * 10, (i + 1) * 10],
            }
            pairs.append(pair)

            if has_end:
                lines.append(
                    f"Segment {segment_idx}: frame {start_idx} -> frame {end_idx} (seconds {i*10}-{(i+1)*10})"
                )
            else:
                lines.append(
                    f"Segment {segment_idx}: frame {start_idx} -> [empty end frame] (seconds {i*10}-{(i+1)*10})"
                )

        meta = {
            "availability_mode": availability_mode,
            "segment_count": safe_segments,
            "start_frame_index": safe_start,
            "available_max_index": available_max_index,
            "required_frame_count": required_frame_count,
        }

        payload = {
            "meta": meta,
            "pairs": pairs,
        }

        return (
            json.dumps(payload, ensure_ascii=True, indent=2),
            "\n".join(lines),
            int(required_frame_count),
        )

NODE_CLASS_MAPPINGS = {
    "CCTextInput": CCTextInput,
    "CCOpenAIResponsesNode": CCOpenAIResponsesNode,
    "CCKlingPlanParser": CCKlingPlanParser,
    "CCSegmentImageGate": CCSegmentImageGate,
    "CCFramePairPlanner": CCFramePairPlanner,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CCTextInput": "CC Text Input",
    "CCOpenAIResponsesNode": "CC OpenAI Responses",
    "CCKlingPlanParser": "CC Kling Plan Parser",
    "CCSegmentImageGate": "CC Segment Image Gate",
    "CCFramePairPlanner": "CC Frame Pair Planner",
}




