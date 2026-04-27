from __future__ import annotations

import time
import unittest

from src.app_discovery import discover_targets
from src.app_discovery import DiscoveredTarget
from src.ui import filter_discovered_targets, discovered_search_text


class PerformanceTests(unittest.TestCase):
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
