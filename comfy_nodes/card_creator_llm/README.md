# Card Creator LLM Nodes (ComfyUI)

This package includes baseline stacks for script-driven Kling workflows.

## Nodes

- `CC Prompt Builder`
- `CC Script Chunk Planner`
- `CC Kling Request Builder`
- `CC Text Input`
- `CC OpenAI Responses`
- `CC Kling Plan Parser`
- `CC Frame Pair Planner`
- `CC Segment Image Gate`

## Workflow Files

- `workflows/card_creator_kling_gpt54_base.json`
  - Kling 3.0 storyboard baseline.
- `workflows/card_creator_kling3_start_end_chain.json`
  - 2-segment start/end chaining baseline.
- `workflows/card_creator_kling3_60s_auto_skip.json`
  - Up to 60s (6 x 10s segments) with auto-skip of unused Kling nodes.
- `workflows/card_creator_kling3_start_end_chain_clean.json`
  - Same as chain baseline, but without helper UI nodes.
- `workflows/card_creator_kling3_60s_auto_skip_clean.json`
  - Same as 60s baseline, but without helper UI nodes.
- `workflows/card_creator_kling3_start_end_chain_local_safe.json`
  - Local-safe chain profile (no optional SaveVideo/helper nodes).
- `workflows/card_creator_kling3_60s_auto_skip_local_safe.json`
  - Local-safe 60s profile (no optional SaveVideo/helper nodes).

## 60s Auto-Skip Behavior

The 60s workflow uses this logic:

1. Script is split into ~10s segments.
2. `segment_count` from parser controls `CC Segment Image Gate` nodes.
3. For each segment node:
   - if `segment_index <= segment_count` -> gate passes start frame
   - if `segment_index > segment_count` -> gate emits `ExecutionBlocker`
4. Blocked segments skip downstream Kling execution.

Example:
- Script fits ~20s -> `segment_count = 2`
- Segment 1 and 2 run
- Segment 3..6 are skipped automatically

## Start/End Frame Rule

In the 60s workflow:

- Segment1 uses `frame1 -> frame2`
- Segment2..6 use start frame only by default (`end_frame` is empty)
- If next frame exists, connect it manually to that segment's `end_frame`

This matches your rule: if the next image does not exist, `last frame` stays empty.

## Install

Copy `card_creator_llm` into:
- `ComfyUI/custom_nodes/card_creator_llm`

Restart ComfyUI.

If a workflow imports with missing node errors, try the `*_local_safe.json` variant first.
