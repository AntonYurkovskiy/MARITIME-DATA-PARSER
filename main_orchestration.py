"""
Alternative main script using the new orchestration layer.

This script processes HTML resumes using the config-driven orchestration pipeline
instead of the legacy hardcoded approach. It enables comparison of both methods.

Run this script to process files with the orchestration layer:
    python main_orchestration.py

Compare results with the legacy approach:
    python main.py
"""

import logging
import time
from pathlib import Path
from datetime import datetime

from src.config import INPUT_DIR
from src.orchestration.loader import load_blocks_config
from src.orchestration.pipeline import process_seafarer_sync, log_block_timing_summary
from src.orchestration.result import save_sync_report
from src.orchestration.blocks import BlockStatus
from src.api.client import log_retry_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _count_uploaded_addresses(sync_status) -> int:
    """Count successfully sent address payloads for a single file sync result."""
    block = sync_status.blocks.get("addresses")
    if not block or block.status != BlockStatus.SUCCESS:
        return 0

    data = block.data
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return 1
    return 0


def _format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or Dd HH:MM:SS."""
    total_seconds = max(0, int(round(seconds)))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_config_path() -> str:
    """Get path to blocks configuration YAML file."""
    config_path = Path(__file__).parent / "src" / "orchestration" / "blocks_config.yaml"
    return str(config_path)


def enable_blocks(config, block_names=None):
    """
    Enable specific blocks in configuration.
    
    Args:
        config: Loaded blocks configuration dict
        block_names: List of block names to enable. If None, enables all.
    """
    if block_names is None:
        # Enable all blocks
        for block_spec in config.values():
            block_spec["enabled"] = True
    else:
        # Enable only specified blocks
        for block_name in block_names:
            if block_name in config:
                config[block_name]["enabled"] = True
            else:
                logger.warning("Block '%s' not found in configuration", block_name)


def process_all_files(html_files, config, output_dir=None):
    """
    Process all HTML files through the orchestration pipeline.
    
    Args:
        html_files: List of HTML file paths to process
        config: Loaded blocks configuration
        output_dir: Directory to save results (optional)
    """
    success_count = 0
    failed_count = 0
    skipped_count = 0
    uploaded_addresses_count = 0
    files_with_uploaded_addresses = 0
    results = []
    total_start = time.perf_counter()

    logger.info("=" * 70)
    logger.info("🚀 Starting orchestration pipeline processing")
    logger.info("📁 Processing %d HTML files", len(html_files))
    logger.info("=" * 70)

    for idx, html_file in enumerate(html_files, 1):
        try:
            logger.info("")
            logger.info("📄 [%d/%d] Processing: %s", idx, len(html_files), Path(html_file).name)

            # Process file through orchestration pipeline
            sync_status = process_seafarer_sync(html_file, config)
            results.append(sync_status)

            # Update counters
            if sync_status.overall_status == BlockStatus.SUCCESS:
                success_count += 1
                logger.info("✅ File processed successfully")
            elif sync_status.overall_status == BlockStatus.FAILED:
                failed_count += 1
                logger.error("❌ File processing failed: %s", sync_status.error_summary)
            else:
                skipped_count += 1
                logger.warning("⏭️  File processing skipped")

            addresses_for_file = _count_uploaded_addresses(sync_status)
            uploaded_addresses_count += addresses_for_file
            if addresses_for_file > 0:
                files_with_uploaded_addresses += 1

        except Exception as e:
            failed_count += 1
            logger.error("❌ Exception processing file %s: %s", Path(html_file).name, e)
            continue

    total_elapsed_sec = time.perf_counter() - total_start
    avg_per_file_sec = total_elapsed_sec / len(html_files) if html_files else 0.0

    est_5k_sec = avg_per_file_sec * 5000
    est_100k_sec = avg_per_file_sec * 100000
    est_500k_sec = avg_per_file_sec * 500000
    est_1m_sec = avg_per_file_sec * 1000000

    run_metrics = {
        "total_elapsed_seconds": total_elapsed_sec,
        "total_elapsed_human": _format_duration(total_elapsed_sec),
        "average_seconds_per_file": avg_per_file_sec,
        "average_human_per_file": _format_duration(avg_per_file_sec),
        "estimated_seconds": {
            "5000": est_5k_sec,
            "100000": est_100k_sec,
            "500000": est_500k_sec,
            "1000000": est_1m_sec,
        },
        "estimated_human": {
            "5000": _format_duration(est_5k_sec),
            "100000": _format_duration(est_100k_sec),
            "500000": _format_duration(est_500k_sec),
            "1000000": _format_duration(est_1m_sec),
        },
    }

    # Save results to JSON report
    if output_dir:
        output_path = Path(output_dir) / f"orchestration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            save_sync_report(results, str(output_path), run_metrics=run_metrics)
            logger.info("")
            logger.info("💾 Report saved to: %s", output_path)
        except Exception as e:
            logger.error("Failed to save report: %s", e)

    # Log summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 ORCHESTRATION PIPELINE SUMMARY")
    logger.info("=" * 70)
    logger.info("✅ Successfully processed: %d files", success_count)
    logger.info("❌ Failed: %d files", failed_count)
    logger.info("⏭️  Skipped: %d files", skipped_count)
    logger.info("🏠 Uploaded addresses: %d", uploaded_addresses_count)
    logger.info("📄 Files with uploaded addresses: %d", files_with_uploaded_addresses)
    logger.info("📊 Total: %d files", len(html_files))
    logger.info("⏱️ Total elapsed (actual): %s", _format_duration(total_elapsed_sec))
    logger.info("⏱️ Average per file: %.2f sec (%s)", avg_per_file_sec, _format_duration(avg_per_file_sec))
    logger.info("🔮 Estimated for 5,000 files: %s", _format_duration(est_5k_sec))
    logger.info("🔮 Estimated for 100,000 files: %s", _format_duration(est_100k_sec))
    logger.info("🔮 Estimated for 500,000 files: %s", _format_duration(est_500k_sec))
    logger.info("🔮 Estimated for 1,000,000 files: %s", _format_duration(est_1m_sec))
    logger.info("=" * 70)

    # Log block timing summary
    log_block_timing_summary()
    
    # Log retry statistics
    log_retry_stats()

    return results


def main():
    """Main entry point for orchestration pipeline."""
    # Load configuration
    config_path = get_config_path()
    logger.info("📋 Loading configuration from: %s", config_path)
    
    try:
        config = load_blocks_config(config_path)
        logger.info("✅ Configuration loaded successfully")
    except Exception as e:
        logger.error("❌ Failed to load configuration: %s", e)
        return

    # Enable only implemented blocks by default.
    # This keeps main_orchestration.py focused on blocks that are production-ready.
    enable_blocks(config, ["main_info", "addresses", "relatives", "sea_service", "photo", "documents"])

    # Get HTML files to process
    html_files = sorted([str(p) for p in Path(INPUT_DIR).rglob("*.html")])
    
    if not html_files:
        logger.warning("⚠️  No HTML files found in %s", INPUT_DIR)
        return

    logger.info("🔍 Found %d HTML files to process", len(html_files))

    # Create output directory for reports
    output_dir = Path(__file__).parent / "orchestration_results"
    output_dir.mkdir(exist_ok=True)

    # Process all files
    results = process_all_files(html_files, config, output_dir=str(output_dir))

    logger.info("")
    logger.info("✨ Orchestration pipeline completed")


if __name__ == "__main__":
    main()
