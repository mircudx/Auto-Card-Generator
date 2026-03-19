"""ComfyUI entrypoint for Card Creator custom nodes.

Loads the internal node bundle via file-path import so it works even when
the repository folder name contains characters that are not valid module names.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = ROOT_DIR / "comfy_nodes" / "card_creator_llm"
BUNDLE_INIT = BUNDLE_DIR / "__init__.py"

spec = importlib.util.spec_from_file_location(
    "card_creator_llm_bundle",
    BUNDLE_INIT,
    submodule_search_locations=[str(BUNDLE_DIR)],
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load node bundle from {BUNDLE_INIT}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NODE_CLASS_MAPPINGS = module.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = module.NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
