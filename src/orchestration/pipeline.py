"""
Core orchestration pipeline.

Coordinates parsing, normalization, validation, payload building, and sending.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple
import logging
from urllib.parse import urljoin
import time
import functools

import requests

from src.api.client import _get_session
from src.config import API_BASE_URL
from src.domain.builder import stringify_id_fields
from src.orchestration.blocks import SyncStatus, BlockStatus, BlockResult, BlockSpec
from src.orchestration.registry import get_registry, populate_default_registry
from src.orchestration.result import log_block_results, log_sync_summary
from src.parsers.html import get_html_content, main_parser, parse_notes

logger = logging.getLogger(__name__)

# Registry is initialized lazily on first use (avoids API calls at import time)
_registry = None

# Block timing statistics
_block_timings: Dict[str, list[float]] = {}


def _time_block(func):
    """Decorator to measure and log block execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract block_name from block_spec (first positional arg for _process_block)
        block_name = 'unknown'
        if args and hasattr(args[0], 'get'):
            block_name = args[0].get('name', 'unknown')
        
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            
            if block_name != 'unknown':
                if block_name not in _block_timings:
                    _block_timings[block_name] = []
                _block_timings[block_name].append(elapsed)
            
            logger.debug(f"⏱️ Block '{block_name}' completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"❌ Block '{block_name}' failed after {elapsed:.3f}s: {e}")
            raise
    return wrapper


def log_block_timing_summary():
    """Log summary statistics for block timings."""
    if not _block_timings:
        logger.info("📊 No block timing data collected")
        return
    
    logger.info("=" * 70)
    logger.info("📊 BLOCK TIMING SUMMARY")
    logger.info("=" * 70)
    
    total_time = sum(sum(times) for times in _block_timings.values())
    
    for block_name, times in sorted(_block_timings.items(), key=lambda x: sum(x[1]), reverse=True):
        block_total = sum(times)
        block_avg = block_total / len(times)
        block_count = len(times)
        percentage = (block_total / total_time * 100) if total_time > 0 else 0
        
        logger.info(
            f"📦 {block_name:20s} | count={block_count:3d} | "
            f"total={block_total:7.3f}s | avg={block_avg:6.3f}s | {percentage:5.1f}%"
        )
    
    logger.info("=" * 70)
    logger.info(f"⏱️ Total time across all blocks: {total_time:.3f}s")
    logger.info("=" * 70)


def _sorted_block_specs(config: Dict[str, BlockSpec]):
    return sorted(
        (spec for spec in config.values() if spec.get("enabled", False)),
        key=lambda spec: spec.get("order", 999),
    )


def _dependencies_ready(block_spec: BlockSpec, results: Dict[str, BlockResult]) -> Tuple[bool, str | None]:
    missing = [name for name in block_spec.get("depends_on", []) if name not in results]
    if missing:
        return False, f"missing dependencies: {', '.join(missing)}"
    failed = [
        name
        for name in block_spec.get("depends_on", [])
        if results[name].status not in {BlockStatus.SUCCESS, BlockStatus.SKIPPED}
    ]
    if failed:
        return False, f"unresolved dependencies: {', '.join(failed)}"
    return True, None


def _format_endpoint(endpoint: str, context: Dict[str, Any]) -> str:
    try:
        return endpoint.format(**context)
    except KeyError:
        return endpoint


def _build_request_kwargs(payload: Any) -> Dict[str, Any]:
    def _stringify_ids(value: Any) -> Any:
        if isinstance(value, dict):
            return stringify_id_fields(value)
        if isinstance(value, list):
            return [_stringify_ids(item) for item in value]
        return value

    if payload is None:
        return {}
    if isinstance(payload, dict) and ("json" in payload or "files" in payload or "data" in payload):
        request_kwargs: Dict[str, Any] = {}
        if "json" in payload:
            request_kwargs["json"] = _stringify_ids(payload["json"])
        elif "data" in payload:
            request_kwargs["data"] = payload["data"]
        else:
            request_kwargs["json"] = _stringify_ids(payload)
        if "files" in payload:
            request_kwargs["files"] = payload["files"]
        return request_kwargs
    return {"json": _stringify_ids(payload)}


def _send_payload(session: requests.Session, method: str, endpoint: str, payload: Any) -> requests.Response:
    url = urljoin(API_BASE_URL.rstrip("/") + "/", endpoint.lstrip("/"))
    request_kwargs = _build_request_kwargs(payload)
    return session.request(method=method.upper(), url=url, timeout=None, **request_kwargs)


def _raise_for_status_with_body(response: requests.Response) -> None:
    """Call raise_for_status and attach response body to the exception message."""
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        body = (response.text[:2000] if response is not None and response.text else "")
        raise requests.RequestException(f"{exc} | response_body={body}") from exc


def _handle_block_error(
    block_name: str,
    block_spec: BlockSpec,
    exc: Exception,
    results: Dict[str, BlockResult],
    overall_status_ref: list,
) -> None:
    """Record a failed block result and update overall status if block is required."""
    result = BlockResult(
        block_name=block_name,
        status=BlockStatus.FAILED,
        error=str(exc),
    )
    results[block_name] = result
    if block_spec.get("required", False):
        overall_status_ref[0] = BlockStatus.FAILED
    log_block_results(result)


def _adapt_payload_for_api(block_name: str, payload: Any, context: Dict[str, Any]) -> Any:
    """Apply API-compatibility tweaks for specific blocks before sending."""
    if block_name != "main_info" or not isinstance(payload, dict):
        # Sea-service payload needs legacy-compatible shape with seafarer_uuid.
        if block_name == "sea_service" and isinstance(payload, list):
            seafarer_uuid = context.get("seafarer_uuid")
            adapted_payloads = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                adapted_payloads.append(
                    {
                        "seafarer_uuid": seafarer_uuid,
                        "rank_id": str(item.get("rank_id")) if item.get("rank_id") is not None else None,
                        "vessel": {
                            "uuid": ((item.get("vessel") or {}).get("uuid")),
                            "source": ((item.get("vessel") or {}).get("source")) or "historical",
                        },
                        "is_automatic": True,
                        "sign_on_date": item.get("sign_on_date"),
                        "sign_off_date": item.get("sign_off_date"),
                        "off_reason_id": 0,
                        "is_historical": 1,
                        "details": item.get("details") or "Imported from CV",
                    }
                )
            return adapted_payloads
        return payload

    adapted = dict(payload)

    # Legacy /seafarers expects emails as list[str], not list[dict].
    emails = adapted.get("emails")
    if isinstance(emails, list):
        adapted["emails"] = [
            item.get("email") if isinstance(item, dict) else item
            for item in emails
            if (item.get("email") if isinstance(item, dict) else item)
        ]

    # Keep legacy parity with main.py payload.
    adapted.pop("resident_status_id", None)
    adapted.pop("photo", None)

    return adapted


@_time_block
def _process_block(
    block_spec: BlockSpec,
    raw_data: Dict[str, Any],
    context: Dict[str, Any],
    session: requests.Session,
    registry,
) -> BlockResult:
    parser = registry.get(block_spec["parser"])
    transformer = registry.get(block_spec["transformer"])
    payload_builder = registry.get(block_spec["payload_builder"])
    validator = registry.get(block_spec["validator"])

    parsed = parser(raw_data)
    normalized = transformer(parsed, context)
    is_valid, validation_errors = validator(normalized)
    if not is_valid:
        return BlockResult(
            block_name=block_spec["name"],
            status=BlockStatus.VALIDATION_ERROR,
            error="; ".join(validation_errors),
            data={"parsed": parsed, "normalized": normalized},
        )

    payload = payload_builder(normalized, context)
    payload = _adapt_payload_for_api(block_spec["name"], payload, context)
    endpoint = _format_endpoint(block_spec["endpoint"], context)

    # Some blocks (e.g., sea_service) produce multiple payload items.
    if isinstance(payload, list):
        response_data_list = []
        for item in payload:
            response = _send_payload(session, block_spec["method"], endpoint, item)
            _raise_for_status_with_body(response)
            response_data_list.append(response.json() if response.content else None)
        response_data = response_data_list
        http_status = 207 if response_data_list else None
    else:
        response = _send_payload(session, block_spec["method"], endpoint, payload)
        _raise_for_status_with_body(response)
        response_data = response.json() if response.content else None
        http_status = response.status_code

    context_updates: Dict[str, Any] = {}
    if isinstance(response_data, dict):
        inserted = response_data.get("inserted")
        if isinstance(inserted, dict) and inserted.get("uuid"):
            context_updates["seafarer_uuid"] = inserted["uuid"]

    return BlockResult(
        block_name=block_spec["name"],
        status=BlockStatus.SUCCESS,
        data=response_data if response_data is not None else {"payload": payload},
        http_status=http_status,
        context_updates=context_updates or None,
    )


def process_seafarer_sync(html_file: str, config: Dict[str, BlockSpec]) -> SyncStatus:
    """Process one HTML file through the orchestration pipeline."""
    global _registry
    if _registry is None:
        populate_default_registry()
        _registry = get_registry()
    registry = _registry

    soup = get_html_content(html_file)
    raw_data = main_parser(soup)
    # Keep soup available for strategies that need raw binary extraction (e.g., photo).
    if isinstance(raw_data, dict):
        raw_data["__soup"] = soup
    notes = parse_notes(soup)
    
    # Add intra-file cache to context for reusing computed values within the same file
    context: Dict[str, Any] = {
        "notes": notes, 
        "html_file": html_file,
        "_file_cache": {}  # Cache for computed values within this file
    }

    results: Dict[str, BlockResult] = {}
    overall_status_ref = [BlockStatus.SUCCESS]

    for block_spec in _sorted_block_specs(config):
        block_name = block_spec["name"]
        ready, reason = _dependencies_ready(block_spec, results)
        if not ready:
            result = BlockResult(
                block_name=block_name,
                status=BlockStatus.SKIPPED,
                error=reason,
            )
            results[block_name] = result
            log_block_results(result)
            continue

        try:
            result = _process_block(block_spec, raw_data, context, _get_session(), registry)
            results[block_name] = result
            if result.context_updates:
                context.update(result.context_updates)
            if result.status in {BlockStatus.FAILED, BlockStatus.VALIDATION_ERROR} and block_spec.get("required", False):
                overall_status_ref[0] = result.status
            log_block_results(result)
        except Exception as exc:
            _handle_block_error(block_name, block_spec, exc, results, overall_status_ref)

    sync_status = SyncStatus(
        file_path=html_file,
        blocks=results,
        overall_status=overall_status_ref[0] if results else BlockStatus.SKIPPED,
        error_summary=None,
    )
    log_sync_summary(sync_status)
    return sync_status
