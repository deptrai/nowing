"""Cassette loader and serialization for hermetic replay benchmarks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Cassette:
    """A recorded HTTP/SSE artifact for zero-cost replay."""

    type: str = "rest"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> Cassette:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Cassette not found: {p}")

        content = p.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Cassette is empty: {p}")

        first_line = content.splitlines()[0]
        try:
            data = json.loads(first_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Cassette contains invalid JSON: {p}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Cassette must contain a JSON object, got {type(data).__name__}: {p}")

        body = data.get("body", {})
        if not isinstance(body, dict):
            raise ValueError(
                f"Cassette 'body' must be a JSON object, got {type(body).__name__}: {p}"
            )

        return cls(
            type=data.get("type", "rest"),
            status=data.get("status", 200),
            headers=data.get("headers", {}),
            body=body,
        )

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        payload = {
            "type": self.type,
            "status": self.status,
            "headers": self.headers,
            "body": self.body,
        }
        tmp.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, p)
