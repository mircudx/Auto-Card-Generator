# Publishing Checklist (Comfy Cloud)

1. Update `pyproject.toml`:
   - `project.name` (final unique node name)
   - `project.urls.Repository`
   - `tool.comfy.PublisherId`
2. Commit and push repository to GitHub.
3. Create secret `REGISTRY_ACCESS_TOKEN` in repository settings.
4. Run workflow `Publish to Comfy Registry`.
5. Wait until node appears in `registry.comfy.org`.
6. In ComfyUI Cloud Manager, install node from Registry.
7. Import workflow JSON from `workflows/`.
8. Configure Secrets (OpenAI/Kling/etc) in Cloud.

## Keep It Private

- Do not publish as a public app.
- Do not click `Share -> Create a link`.
- Keep all keys in Secrets only.
