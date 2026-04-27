from __future__ import annotations

import hashlib
from pathlib import Path


def sha1_digest_prefix(path: Path, *, prefix_length: int = 12, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha1()
    try:
        with path.open("rb") as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()[:prefix_length]
    except OSError:
        return hashlib.sha1(str(path).encode("utf-8", errors="ignore")).hexdigest()[:prefix_length]
