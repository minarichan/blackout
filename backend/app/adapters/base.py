from __future__ import annotations

from dataclasses import dataclass, field

from app.models.position import Position


@dataclass
class AdapterResult:
    chain: str
    protocol: str
    positions: list[Position] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    warning: str | None = None
    elapsed_ms: int = 0
