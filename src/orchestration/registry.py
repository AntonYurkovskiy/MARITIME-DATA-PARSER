"""
Registry of block handlers (parsers, transformers, validators, payload builders).

Maps function names from config to actual callable functions.
"""

from typing import Callable, Dict
import logging

logger = logging.getLogger(__name__)


class HandlersRegistry:
    """
    Registry for block handler functions.
    
    Maps string names (from config) to actual Python callables.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, name: str, func: Callable) -> None:
        """Register a handler function."""
        self._handlers[name] = func
        logger.debug("Registered handler: %s", name)
    
    def get(self, name: str) -> Callable:
        """Get a registered handler by name."""
        if name not in self._handlers:
            raise KeyError(f"Handler '{name}' not found in registry")
        return self._handlers[name]
    
    def __contains__(self, name: str) -> bool:
        """Check if handler is registered."""
        return name in self._handlers


# Global registry instance
_REGISTRY = HandlersRegistry()


def get_registry() -> HandlersRegistry:
    """Get the global handlers registry."""
    return _REGISTRY


def register_handler(name: str, func: Callable) -> None:
    """Convenience function to register a handler globally."""
    _REGISTRY.register(name, func)


def get_handler(name: str) -> Callable:
    """Convenience function to get a handler from global registry."""
    return _REGISTRY.get(name)


def populate_default_registry() -> None:
    """
    Populate registry with handlers from strategies and existing modules.
    
    Called once at startup to register all available block handlers.
    """
    from src.orchestration.strategies.addresses import (
        build_addresses_payload,
        normalize_addresses,
        parse_addresses_raw,
        validate_addresses,
    )
    from src.orchestration.strategies.certificates import (
        build_certificates_payload,
        normalize_certificates,
        parse_certificates_raw,
        validate_certificates,
    )
    from src.orchestration.strategies.contracts import (
        build_contracts_payloads,
        normalize_sea_service,
        parse_sea_service_raw,
        validate_contracts,
    )
    from src.orchestration.strategies.documents import (
        build_documents_payload,
        normalize_documents,
        parse_documents_raw,
        validate_documents,
    )
    from src.orchestration.strategies.main_info import (
        build_main_info_payload,
        normalize_main_info,
        parse_main_info_raw,
        validate_main_info,
    )
    from src.orchestration.strategies.photo import (
        build_photo_payload,
        normalize_photo,
        parse_photo_raw,
        validate_photo,
    )
    from src.orchestration.strategies.relatives import (
        build_relatives_payload,
        normalize_relatives,
        parse_relatives_raw,
        validate_relatives,
    )

    registrations = {
        "parse_main_info_raw": parse_main_info_raw,
        "normalize_main_info": normalize_main_info,
        "validate_main_info": validate_main_info,
        "build_main_info_payload": build_main_info_payload,
        "parse_addresses_raw": parse_addresses_raw,
        "normalize_addresses": normalize_addresses,
        "validate_addresses": validate_addresses,
        "build_addresses_payload": build_addresses_payload,
        "parse_certificates_raw": parse_certificates_raw,
        "normalize_certificates": normalize_certificates,
        "validate_certificates": validate_certificates,
        "build_certificates_payload": build_certificates_payload,
        "parse_relatives_raw": parse_relatives_raw,
        "normalize_relatives": normalize_relatives,
        "validate_relatives": validate_relatives,
        "build_relatives_payload": build_relatives_payload,
        "parse_sea_service_raw": parse_sea_service_raw,
        "normalize_sea_service": normalize_sea_service,
        "validate_contracts": validate_contracts,
        "build_contracts_payloads": build_contracts_payloads,
        "parse_documents_raw": parse_documents_raw,
        "normalize_documents": normalize_documents,
        "validate_documents": validate_documents,
        "build_documents_payload": build_documents_payload,
        "parse_photo_raw": parse_photo_raw,
        "normalize_photo": normalize_photo,
        "validate_photo": validate_photo,
        "build_photo_payload": build_photo_payload,
    }

    for name, func in registrations.items():
        register_handler(name, func)

    logger.info("Registered %d default handlers", len(registrations))
