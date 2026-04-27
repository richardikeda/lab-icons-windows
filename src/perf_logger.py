from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


class PerfLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session = time.strftime("%Y%m%d-%H%M%S")
        self._normalize_legacy_log()

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

    def _normalize_legacy_log(self) -> None:
        try:
            raw = self.path.read_bytes()
        except OSError:
            return
        if not raw:
            return
        normalized = _normalized_log_bytes(raw)
        if normalized is None or normalized == raw:
            return
        self.path.write_bytes(normalized)


def _normalized_log_bytes(raw: bytes) -> bytes | None:
    if raw.startswith(UTF16_BOMS):
        json_start = raw.find(b'{"')
        if json_start >= 0:
            return raw[json_start:]
        if _is_comment_only_text(_decode_legacy_text(raw)):
            return b""
    return None


def _decode_legacy_text(raw: bytes) -> str:
    for encoding in ("utf-16", "utf-16-le", "utf-16-be", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _is_comment_only_text(text: str) -> bool:
    logical_lines = [line.strip() for line in text.replace("\\n", "\n").splitlines()]
    return all(not line or line.startswith("#") for line in logical_lines)
