from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class ProjectPollBatch:
    project_id: int
    ac_data: List[Dict[str, Any]] = field(default_factory=list)
    mppt_data: List[Dict[str, Any]] = field(default_factory=list)
    string_data: List[Dict[str, Any]] = field(default_factory=list)
    error_data: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
