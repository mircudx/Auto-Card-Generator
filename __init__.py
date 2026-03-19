"""ComfyUI entrypoint for Card Creator custom nodes.

This loader is robust to repository folder names that are not valid Python
module identifiers (for example, names with dashes).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = ROOT_DIR / "comfy_nodes" / "card_creator_llm"
BUNDLE_INIT = BUNDLE_DIR / "__init__.py"
MODULE_NAME = "card_creator_llm_bundle"

if not BUNDLE_INIT.exists():
    raise RuntimeError(f"Node bundle not found: {BUNDLE_INIT}")

spec = importlib.util.spec_from_file_location(
    MODULE_NAME,
    BUNDLE_INIT,
    submodule_search_locations=[str(BUNDLE_DIR)],
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to create import spec for bundle: {BUNDLE_INIT}")

module = importlib.util.module_from_spec(spec)
# Important: register package module before execution so relative imports
# inside the bundle (__init__.py -> .nodes/.extra_nodes) resolve correctly.
sys.modules[MODULE_NAME] = module
spec.loader.exec_module(module)

NODE_CLASS_MAPPINGS = module.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = module.NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
