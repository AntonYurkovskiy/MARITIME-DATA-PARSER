"""
Result handling and reporting for orchestration pipeline.

Provides functions to save, log, and summarize sync results.
"""

import json
from typing import List
from pathlib import Path
import logging

from src.orchestration.blocks import SyncStatus, BlockResult, BlockStatus

logger = logging.getLogger(__name__)


def _status_to_text(status: BlockStatus) -> str:
    return status.value if isinstance(status, BlockStatus) else str(status)


def save_sync_report(results: List[SyncStatus], output_path: str) -> str:
    """
    Save synchronization results to JSON report file.

    Args:
        results: List of SyncStatus objects
        output_path: Path to save report JSON file

    Returns:
        Path to saved report file
    """
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "total_files": len(results),
        "success_files": sum(1 for item in results if item.overall_status == BlockStatus.SUCCESS),
        "failed_files": sum(1 for item in results if item.overall_status == BlockStatus.FAILED),
        "files": [
            {
                "file_path": item.file_path,
                "overall_status": _status_to_text(item.overall_status),
                "error_summary": item.error_summary,
                "timestamp": item.timestamp,
                "summary": item.summary,
                "blocks": {name: block.to_dict() for name, block in item.blocks.items()},
            }
            for item in results
        ],
    }

    with report_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    logger.info("Saved sync report to %s", report_path)
    return str(report_path)


def log_block_results(block_result: BlockResult) -> None:
    """Log individual block result."""
    if block_result.status == BlockStatus.SUCCESS:
        logger.info("Block %s succeeded", block_result.block_name)
    elif block_result.status == BlockStatus.SKIPPED:
        logger.info("Block %s skipped: %s", block_result.block_name, block_result.error)
    elif block_result.status == BlockStatus.VALIDATION_ERROR:
        logger.warning("Block %s validation error: %s", block_result.block_name, block_result.error)
    else:
        logger.error("Block %s failed: %s", block_result.block_name, block_result.error)


def log_sync_summary(sync_status: SyncStatus) -> None:
    """Log summary of entire file sync."""
    logger.info(
        "File %s processed: %s",
        sync_status.file_path,
        sync_status.summary,
    )
    if sync_status.error_summary:
        logger.warning("Sync error summary: %s", sync_status.error_summary)
