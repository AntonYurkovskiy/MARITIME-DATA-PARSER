"""
Orchestration layer for the staff parsing pipeline.

Provides config-driven block-based processing of HTML files.
"""

from src.orchestration.blocks import BlockResult, BlockStatus, SyncStatus, BlockSpec
from src.orchestration.pipeline import process_seafarer_sync
from src.orchestration.loader import load_blocks_config

__all__ = [
    "BlockResult",
    "BlockStatus",
    "SyncStatus",
    "BlockSpec",
    "process_seafarer_sync",
    "load_blocks_config",
]
