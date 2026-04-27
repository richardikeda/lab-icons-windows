from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class PerfLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session = time.strftime("%Y%m%d-%H%M%S")

    @contextmanager
    def measure(self, name: str, **fields: object) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.log(name, (time.perf_counter() - start) * 1000, **fields)

    def log(self, name: str, elapsed_ms: float, **fields: object) -> None:
        payload = {
            "session": self.session,
            "event": name,
            "elapsed_ms": round(elapsed_ms, 2),
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
