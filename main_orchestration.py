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
from pathlib import Path
from datetime import datetime

from src.config import INPUT_DIR
from src.orchestration.loader import load_blocks_config
from src.orchestration.pipeline import process_seafarer_sync
from src.orchestration.result import save_sync_report, log_sync_summary
from src.orchestration.blocks import BlockStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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
    results = []

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

        except Exception as e:
            failed_count += 1
            logger.error("❌ Exception processing file %s: %s", Path(html_file).name, e)
            continue

    # Save results to JSON report
    if output_dir:
        output_path = Path(output_dir) / f"orchestration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            save_sync_report(results, str(output_path))
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
    logger.info("📊 Total: %d files", len(html_files))
    logger.info("=" * 70)

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

    # Enable desired blocks (you can customize which blocks to enable)
    # Option 1: Enable only main_info and sea_service
    # enable_blocks(config, ["main_info", "sea_service"])
    
    # Option 2: Enable all blocks
    enable_blocks(config)

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
