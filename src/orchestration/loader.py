"""
Load and parse block configuration from YAML.
"""

from typing import Dict, Any, List
import logging
from pathlib import Path

import yaml

from src.orchestration.blocks import BlockSpec

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = {
    "enabled",
    "order",
    "parser",
    "transformer",
    "payload_builder",
    "validator",
    "endpoint",
    "method",
    "required",
    "retry_max",
    "depends_on",
    "context_keys",
}


def _ensure_block_dict(block_name: str, block_data: Any) -> Dict[str, Any]:
    if not isinstance(block_data, dict):
        raise ValueError(f"Block '{block_name}' must be a mapping")
    missing = sorted(field for field in _REQUIRED_FIELDS if field not in block_data)
    if missing:
        raise ValueError(f"Block '{block_name}' missing fields: {missing}")
    return block_data


def load_blocks_config(yaml_path: str) -> Dict[str, BlockSpec]:
    """
    Load block specifications from YAML configuration file.

    Args:
        yaml_path: Path to blocks_config.yaml

    Returns:
        Dict mapping block name to BlockSpec

    Raises:
        FileNotFoundError: If YAML file not found
        ValueError: If required fields missing or config format is invalid
    """
    config_path = Path(yaml_path)
    with config_path.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj) or {}

    if not isinstance(config, dict):
        raise ValueError("Blocks config must be a mapping at the top level")

    blocks_section = config.get("blocks", {})
    if not isinstance(blocks_section, dict):
        raise ValueError("'blocks' section must be a mapping")

    blocks: Dict[str, BlockSpec] = {}
    for block_name, block_data in blocks_section.items():
        normalized = _ensure_block_dict(block_name, block_data)

        blocks[block_name] = {
            "name": block_name,
            "enabled": bool(normalized["enabled"]),
            "order": int(normalized["order"]),
            "parser": str(normalized["parser"]),
            "transformer": str(normalized["transformer"]),
            "payload_builder": str(normalized["payload_builder"]),
            "validator": str(normalized["validator"]),
            "endpoint": str(normalized["endpoint"]),
            "method": str(normalized["method"]),
            "required": bool(normalized["required"]),
            "retry_max": int(normalized["retry_max"]),
            "depends_on": list(normalized.get("depends_on", [])),
            "context_keys": list(normalized.get("context_keys", [])),
        }

    logger.info("Loaded %d block specs from %s", len(blocks), config_path)
    return blocks
