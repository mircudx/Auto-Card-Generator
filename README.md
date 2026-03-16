# Card Creator LLM Nodes

Registry-ready ComfyUI custom nodes for building script-driven Kling 3.0 pipelines with GPT-5.4 planning.

## Included Node Pack

- Path: `comfy_nodes/card_creator_llm`
- Entrypoint: root `__init__.py` re-exports node mappings

## Bundled Workflows

- `workflows/card_creator_kling_gpt54_base.json`
- `workflows/card_creator_kling3_start_end_chain.json`
- `workflows/card_creator_kling3_60s_auto_skip.json`

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
