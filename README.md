# Card Creator LLM Nodes

Registry-ready ComfyUI custom nodes for building script-driven Kling 3.0 pipelines with GPT-5.4 planning.

## Included Node Pack

- Path: `comfy_nodes/card_creator_llm`
- Entrypoint: root `__init__.py` re-exports node mappings

## Bundled Workflows

- `workflows/card_creator_kling_gpt54_base.json`
- `workflows/card_creator_kling3_start_end_chain.json`
- `workflows/card_creator_kling3_60s_auto_skip.json`
- `workflows/card_creator_kling3_start_end_chain_clean.json`
- `workflows/card_creator_kling3_60s_auto_skip_clean.json`
- `workflows/card_creator_kling3_start_end_chain_local_safe.json`
- `workflows/card_creator_kling3_60s_auto_skip_local_safe.json`

## Which Workflow To Import

1. Local ComfyUI first try:
   - `workflows/card_creator_kling3_60s_auto_skip_local_safe.json`
2. If your setup has `SaveVideo` node:
   - `workflows/card_creator_kling3_60s_auto_skip_clean.json`
3. Legacy/full template (includes extra helper nodes):
   - `workflows/card_creator_kling3_60s_auto_skip.json`

`local_safe` removes optional helper/output nodes that are commonly missing in local installs.

## Publish To Comfy Registry

1. Edit `pyproject.toml`:
   - set `[tool.comfy].PublisherId`
   - set `[project.urls].Repository`
2. Push repository to GitHub.
3. Create repository secret: `REGISTRY_ACCESS_TOKEN`.
4. Run GitHub Action from `.github/workflows/publish_registry.yml`.

## Privacy (Cloud)

- Keep workflow private by default in your account.
- Do not use `Share -> Create a link` if only you should access it.
- Store all provider keys in Cloud Secrets, not in workflow JSON.
