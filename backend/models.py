from dataclasses import dataclass
from typing import Optional

@dataclass
class NamespaceRequest:
    team_name: str
    environment: str        # dev | staging | prod
    cpu_limit: str          # e.g. "4"
    memory_limit: str       # e.g. "8Gi"
    owner_email: str
    requested_by: str

@dataclass
class NamespaceStatus:
    name: str
    status: str
    created_at: Optional[str]
    cpu_limit: str
    memory_limit: str
    owner: str