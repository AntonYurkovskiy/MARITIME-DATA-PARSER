"""
Data structures for orchestration layer.

Defines BlockSpec, BlockResult, BlockStatus, and SyncStatus types.
"""

from typing import TypedDict, Optional, Any, Dict, List
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime


class BlockStatus(str, Enum):
    """Status of a block processing."""
    PENDING = "pending"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    VALIDATION_ERROR = "validation_error"


@dataclass
class BlockResult:
    """Result of processing a single block."""
    
    block_name: str
    status: BlockStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    http_status: Optional[int] = None
    context_updates: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class SyncStatus:
    """Overall result of processing a single seafarer from HTML file."""
    
    file_path: str
    blocks: Dict[str, BlockResult]
    overall_status: BlockStatus
    error_summary: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    @property
    def summary(self) -> str:
        """Human-readable summary of sync status."""
        success = sum(1 for b in self.blocks.values() if b.status == BlockStatus.SUCCESS)
        total = len(self.blocks)
        return f"{success}/{total} blocks OK ({self.overall_status.value})"


class BlockSpec(TypedDict):
    """Specification of a block loaded from config."""
    
    name: str
    enabled: bool
    order: int
    parser: str                    # function name for parsing
    transformer: str               # function name for transformation
    payload_builder: str           # function name for payload building
    validator: str                 # function name for validation
    endpoint: str
    method: str                    # HTTP method
    required: bool                 # fail entire sync if this block fails?
    retry_max: int
    depends_on: List[str]
    context_keys: Optional[List[str]]
