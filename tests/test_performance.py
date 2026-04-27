from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from src.app_discovery import discover_targets
from src.app_discovery import DiscoveredTarget
from src.perf_logger import PerfLogger
from src.ui import filter_discovered_targets, discovered_search_text


class PerformanceTests(unittest.TestCase):
    def test_perf_logger_rewrites_utf16_redacted_stub_as_utf8_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.log"
            path.write_text("# Arquivo removido por conter logs sensiveis.\\n# Nao versionar este arquivo.", encoding="utf-16")

            logger = PerfLogger(path)
            logger.log("ui.refresh_icons", 12.345, items=3)

            content = path.read_text(encoding="utf-8")
            entry = json.loads(content.strip())
            self.assertEqual(entry["event"], "ui.refresh_icons")
            self.assertEqual(entry["items"], 3)
            self.assertFalse(content.startswith("#"))

    def test_perf_logger_strips_utf16_stub_before_existing_utf8_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.log"
            prefix = "# Arquivo removido por conter logs sensiveis.\r\n# Nao versionar este arquivo.\r\n".encode("utf-16")
            existing = b'{"session":"old","event":"startup","elapsed_ms":1.23}\n'
            path.write_bytes(prefix + existing)

            logger = PerfLogger(path)
            logger.log("ui.refresh_icons", 4.56)

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event"], "startup")
            self.assertEqual(json.loads(lines[1])["event"], "ui.refresh_icons")

    def test_discovery_completes_under_reasonable_time(self) -> None:
        start = time.perf_counter()
        targets = discover_targets()
        elapsed = time.perf_counter() - start

        self.assertGreater(len(targets), 0)
        self.assertLess(elapsed, 8.0)

    def test_detected_filter_uses_index_quickly(self) -> None:
        targets = [
            DiscoveredTarget(
                key=f"shortcut:{index}",
                name=f"Visual Studio Code {index}" if index % 25 == 0 else f"Demo App {index}",
                group="Dev" if index % 25 == 0 else "Pessoal",
                path=f"C:/Apps/Demo/{index}.lnk",
                target_type="shortcut",
            )
            for index in range(2500)
        ]
        index = {target.key: discovered_search_text(target) for target in targets}

        start = time.perf_counter()
        result = filter_discovered_targets(targets, index, "visual code")
        elapsed = time.perf_counter() - start

        self.assertEqual(len(result), 100)
        self.assertLess(elapsed, 0.08)


if __name__ == "__main__":
    unittest.main()
