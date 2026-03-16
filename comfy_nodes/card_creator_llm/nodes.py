"""ComfyUI nodes for dynamic LLM system prompt assembly."""

from __future__ import annotations

import json
import re
from typing import Dict, List

from .templates import (
    BASE_BLOCK,
    DEFAULT_KLING_NEGATIVE,
    KLING_DIRECTOR_RULES,
    KLING_JSON_SCHEMA_HINT,
    LOCATION_POLICY_BLOCKS,
    MODE_BLOCKS,
    OUTPUT_BLOCK,
    SAFETY_BLOCK,
    STYLE_BLOCKS,
)

WORD_PATTERN = re.compile(r"\b[\w'-]+\b")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
CLAUSE_SPLIT_PATTERN = re.compile(r"(?<=[,;:])\s+")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def _estimate_seconds(words: int, speech_rate_wpm: int) -> float:
    safe_wpm = max(80, int(speech_rate_wpm))
    return round((words * 60.0) / safe_wpm, 2)


def _split_long_unit(unit: str, max_words: int) -> List[str]:
    clause_candidates = [part.strip() for part in CLAUSE_SPLIT_PATTERN.split(unit) if part.strip()]
    if not clause_candidates:
        clause_candidates = [unit.strip()]

    output: List[str] = []
    for clause in clause_candidates:
        if _word_count(clause) <= max_words:
            output.append(clause)
            continue

        words = clause.split()
        for start in range(0, len(words), max_words):
            chunk_words = words[start : start + max_words]
            if chunk_words:
                output.append(" ".join(chunk_words).strip())

    return [x for x in output if x]


def _split_into_units(script_text: str, respect_sentence_boundaries: bool) -> List[str]:
    cleaned = _normalize_whitespace(script_text)
    if not cleaned:
        return []

    if respect_sentence_boundaries:
        units = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(cleaned) if part.strip()]
        return units if units else [cleaned]

    return [cleaned]


def _chunk_script(
    script_text: str,
    max_seconds_per_chunk: float,
    speech_rate_wpm: int,
    respect_sentence_boundaries: bool,
) -> List[Dict[str, object]]:
    max_seconds = max(3.0, float(max_seconds_per_chunk))
    safe_wpm = max(80, int(speech_rate_wpm))
    max_words = max(1, int((max_seconds * safe_wpm) / 60))

    units = _split_into_units(script_text, respect_sentence_boundaries)
    if not units:
        return []

    fragments: List[str] = []
    for unit in units:
        if _word_count(unit) <= max_words:
            fragments.append(unit)
        else:
            fragments.extend(_split_long_unit(unit, max_words))

    chunks: List[str] = []
    current_parts: List[str] = []
    current_words = 0

    for fragment in fragments:
        fragment_words = _word_count(fragment)
        if not current_parts:
            current_parts = [fragment]
            current_words = fragment_words
            continue

        if current_words + fragment_words <= max_words:
            current_parts.append(fragment)
            current_words += fragment_words
        else:
            chunks.append(" ".join(current_parts).strip())
            current_parts = [fragment]
            current_words = fragment_words

    if current_parts:
        chunks.append(" ".join(current_parts).strip())

    segments: List[Dict[str, object]] = []
    for idx, text in enumerate(chunks, start=1):
        words = _word_count(text)
        segments.append(
            {
                "segment_index": idx,
                "text": text,
                "word_count": words,
                "estimated_seconds": _estimate_seconds(words, safe_wpm),
            }
        )

    return segments


class CCPromptBuilder:
    """Builds system and user prompt blocks for downstream LLM nodes."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("system_prompt", "user_prompt", "debug_blocks")

    @classmethod
    def INPUT_TYPES(cls):
        style_options = list(STYLE_BLOCKS.keys())
        mode_options = list(MODE_BLOCKS.keys())

        return {
            "required": {
                "user_prompt": (
                    "STRING",
                    {
                        "default": "Describe your idea here.",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "style": (style_options, {"default": "ugc_style"}),
                "functional_mode": (mode_options, {"default": "kling_multisegment"}),
                "include_safety": ("BOOLEAN", {"default": True}),
                "include_output_rules": ("BOOLEAN", {"default": True}),
                "json_only_response": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "project_goal": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "brand_voice": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "hard_constraints": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "custom_system_block": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
            },
        }

    def build(
        self,
        user_prompt: str,
        style: str,
        functional_mode: str,
        include_safety: bool,
        include_output_rules: bool,
        json_only_response: bool,
        project_goal: str = "",
        brand_voice: str = "",
        hard_constraints: str = "",
        custom_system_block: str = "",
    ):
        selected_style = STYLE_BLOCKS.get(style, STYLE_BLOCKS["none"])
        selected_mode = MODE_BLOCKS.get(functional_mode, MODE_BLOCKS["general"])

        blocks: List[str] = [BASE_BLOCK, selected_style, selected_mode]
        debug_map: Dict[str, str] = {
            "style": style,
            "functional_mode": functional_mode,
            "included": "base,style,mode",
        }

        if functional_mode == "kling_multisegment":
            blocks.append(KLING_DIRECTOR_RULES)
            debug_map["kling_director_rules"] = "on"

        if project_goal.strip():
            blocks.append(f"Project goal:\n{project_goal.strip()}")
            debug_map["project_goal"] = "on"

        if brand_voice.strip():
            blocks.append(f"Brand voice:\n{brand_voice.strip()}")
            debug_map["brand_voice"] = "on"

        if hard_constraints.strip():
            blocks.append(f"Hard constraints:\n{hard_constraints.strip()}")
            debug_map["hard_constraints"] = "on"

        if include_safety:
            blocks.append(SAFETY_BLOCK)
            debug_map["safety"] = "on"

        if include_output_rules:
            output_block = OUTPUT_BLOCK
            if json_only_response:
                output_block += "\n- Final answer must be strict JSON with no surrounding commentary."
                output_block += "\n- Keep output schema stable so downstream nodes can parse it safely."
            blocks.append(output_block)
            debug_map["output_rules"] = "on"

        if custom_system_block.strip():
            blocks.append(f"Custom system block:\n{custom_system_block.strip()}")
            debug_map["custom_system_block"] = "on"

        system_prompt = "\n\n---\n\n".join(blocks).strip()
        user_prompt_clean = user_prompt.strip()

        debug_payload = {
            "style": style,
            "functional_mode": functional_mode,
            "block_count": len(blocks),
            "active_flags": debug_map,
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt_clean),
        }

        return (
            system_prompt,
            user_prompt_clean,
            json.dumps(debug_payload, ensure_ascii=True, indent=2),
        )


class CCScriptChunkPlanner:
    """Splits voice script into speech-time-aware segments."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "plan"
    RETURN_TYPES = ("STRING", "STRING", "FLOAT", "INT")
    RETURN_NAMES = ("segments_json", "segments_text", "total_estimated_seconds", "segment_count")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "script_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "max_seconds_per_chunk": (
                    "FLOAT",
                    {
                        "default": 10.0,
                        "min": 3.0,
                        "max": 30.0,
                        "step": 0.1,
                    },
                ),
                "speech_rate_wpm": (
                    "INT",
                    {
                        "default": 140,
                        "min": 80,
                        "max": 220,
                        "step": 1,
                    },
                ),
                "respect_sentence_boundaries": ("BOOLEAN", {"default": True}),
            }
        }

    def plan(
        self,
        script_text: str,
        max_seconds_per_chunk: float,
        speech_rate_wpm: int,
        respect_sentence_boundaries: bool,
    ):
        segments = _chunk_script(
            script_text=script_text,
            max_seconds_per_chunk=max_seconds_per_chunk,
            speech_rate_wpm=speech_rate_wpm,
            respect_sentence_boundaries=respect_sentence_boundaries,
        )

        total_estimated_seconds = round(
            sum(float(segment["estimated_seconds"]) for segment in segments),
            2,
        )

        lines = []
        for segment in segments:
            line = (
                f"{segment['segment_index']}) "
                f"[{segment['estimated_seconds']}s, {segment['word_count']} words] "
                f"{segment['text']}"
            )
            lines.append(line)

        return (
            json.dumps(segments, ensure_ascii=True, indent=2),
            "\n".join(lines),
            float(total_estimated_seconds),
            int(len(segments)),
        )


class CCKlingRequestBuilder:
    """Composes a strict user prompt for an LLM that must output Kling-ready prompts."""

    CATEGORY = "Card Creator/LLM"
    FUNCTION = "build_request"
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("llm_user_prompt", "segment_count", "debug_json")

    @classmethod
    def INPUT_TYPES(cls):
        style_options = list(STYLE_BLOCKS.keys())
        location_options = list(LOCATION_POLICY_BLOCKS.keys())

        return {
            "required": {
                "script_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "generation_brief": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": True,
                    },
                ),
                "style": (style_options, {"default": "ugc_style"}),
                "location_policy": (location_options, {"default": "single_location_default"}),
                "primary_location": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "max_seconds_per_segment": (
                    "FLOAT",
                    {
                        "default": 10.0,
                        "min": 3.0,
                        "max": 30.0,
                        "step": 0.1,
                    },
                ),
                "speech_rate_wpm": (
                    "INT",
                    {
                        "default": 140,
                        "min": 80,
                        "max": 220,
                        "step": 1,
                    },
                ),
                "audio_enabled": ("BOOLEAN", {"default": True}),
                "elements_enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "prepared_segments_json": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "actor_label": (
                    "STRING",
                    {
                        "default": "@Element1",
                        "multiline": False,
                        "dynamicPrompts": False,
                    },
                ),
                "elements_payload_note": (
                    "STRING",
                    {
                        "default": "@Element1 is actor identity, @Element2 is emotion sheet, @Element3 is angle sheet.",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "hard_requirements": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
            },
        }

    def build_request(
        self,
        script_text: str,
        generation_brief: str,
        style: str,
        location_policy: str,
        primary_location: str,
        max_seconds_per_segment: float,
        speech_rate_wpm: int,
        audio_enabled: bool,
        elements_enabled: bool,
        prepared_segments_json: str = "",
        actor_label: str = "@Element1",
        elements_payload_note: str = "@Element1 is actor identity, @Element2 is emotion sheet, @Element3 is angle sheet.",
        hard_requirements: str = "",
    ):
        segments: List[Dict[str, object]] = []
        source = "auto_chunked"

        if prepared_segments_json.strip():
            try:
                parsed = json.loads(prepared_segments_json)
                if isinstance(parsed, list):
                    normalized: List[Dict[str, object]] = []
                    for idx, item in enumerate(parsed, start=1):
                        if isinstance(item, dict):
                            text = str(item.get("text", "")).strip()
                            if not text:
                                continue
                            words = _word_count(text)
                            estimated = item.get("estimated_seconds", _estimate_seconds(words, speech_rate_wpm))
                            normalized.append(
                                {
                                    "segment_index": int(item.get("segment_index", idx)),
                                    "text": text,
                                    "word_count": words,
                                    "estimated_seconds": round(float(estimated), 2),
                                }
                            )
                        elif isinstance(item, str) and item.strip():
                            text = item.strip()
                            words = _word_count(text)
                            normalized.append(
                                {
                                    "segment_index": idx,
                                    "text": text,
                                    "word_count": words,
                                    "estimated_seconds": _estimate_seconds(words, speech_rate_wpm),
                                }
                            )

                    if normalized:
                        segments = normalized
                        source = "prepared_segments_json"
            except (ValueError, TypeError):
                segments = []

        if not segments:
            segments = _chunk_script(
                script_text=script_text,
                max_seconds_per_chunk=max_seconds_per_segment,
                speech_rate_wpm=speech_rate_wpm,
                respect_sentence_boundaries=True,
            )
            source = "auto_chunked"

        style_block = STYLE_BLOCKS.get(style, STYLE_BLOCKS["none"])
        location_block = LOCATION_POLICY_BLOCKS.get(
            location_policy,
            LOCATION_POLICY_BLOCKS["single_location_default"],
        )

        location_line = primary_location.strip() if primary_location.strip() else "Infer one stable location from brief and keep it across segments."
        audio_line = (
            "Native audio is ON. Keep lines short, visible speaker when speaking, and include ambience/SFX cues."
            if audio_enabled
            else "Native audio is OFF. Focus prompts on visuals only."
        )
        elements_line = (
            f"Elements are enabled. Keep identity locked using {actor_label}. {elements_payload_note.strip()}"
            if elements_enabled
            else "Elements are not enabled. Reinforce identity with repeated descriptors every segment."
        )

        segment_lines = []
        for segment in segments:
            segment_lines.append(
                f"{segment['segment_index']}) [{segment['estimated_seconds']}s] {segment['text']}"
            )

        hard_req_block = ""
        if hard_requirements.strip():
            hard_req_block = f"\nHard requirements:\n{hard_requirements.strip()}"

        llm_user_prompt = (
            "Task: Build Kling 3.0 prompts for a voice-driven character video.\n"
            "Generate ONE Kling prompt per script segment so every segment is speakable in about 10 seconds.\n\n"
            f"Creative brief:\n{generation_brief.strip()}\n\n"
            f"Style direction:\n{style_block}\n\n"
            f"Location control:\n{location_block}\n"
            f"Primary location anchor: {location_line}\n\n"
            f"Kling rules:\n{KLING_DIRECTOR_RULES}\n\n"
            f"Audio policy:\n{audio_line}\n\n"
            f"Identity policy:\n{elements_line}\n\n"
            "Script segments to cover in order:\n"
            f"{chr(10).join(segment_lines)}"
            f"{hard_req_block}\n\n"
            "Global exclusions for every segment:\n"
            "- no subtitles\n"
            "- no text overlays\n"
            "- no watermarks\n"
            f"Default negative prompt fallback: {DEFAULT_KLING_NEGATIVE}\n\n"
            "Output requirements:\n"
            "- Keep segment order exactly the same.\n"
            "- Ensure continuity with previous segment.\n"
            "- Use explicit camera framing and camera movement for each segment.\n"
            "- Include location field for each segment.\n"
            "- Include continuity_with_previous field for each segment.\n"
            "- Return strict JSON only.\n"
            f"{KLING_JSON_SCHEMA_HINT}"
        ).strip()

        debug_payload = {
            "segment_source": source,
            "segment_count": len(segments),
            "total_estimated_seconds": round(
                sum(float(segment["estimated_seconds"]) for segment in segments),
                2,
            ),
            "style": style,
            "location_policy": location_policy,
            "audio_enabled": audio_enabled,
            "elements_enabled": elements_enabled,
            "primary_location": primary_location.strip(),
        }

        return (
            llm_user_prompt,
            int(len(segments)),
            json.dumps(debug_payload, ensure_ascii=True, indent=2),
        )


NODE_CLASS_MAPPINGS = {
    "CCPromptBuilder": CCPromptBuilder,
    "CCScriptChunkPlanner": CCScriptChunkPlanner,
    "CCKlingRequestBuilder": CCKlingRequestBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CCPromptBuilder": "CC Prompt Builder",
    "CCScriptChunkPlanner": "CC Script Chunk Planner",
    "CCKlingRequestBuilder": "CC Kling Request Builder",
}
