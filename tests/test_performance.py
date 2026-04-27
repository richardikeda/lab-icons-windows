from __future__ import annotations

import time
import unittest

from src.app_discovery import discover_targets


class PerformanceTests(unittest.TestCase):
    def test_discovery_completes_under_reasonable_time(self) -> None:
        start = time.perf_counter()
        targets = discover_targets()
        elapsed = time.perf_counter() - start

        self.assertGreater(len(targets), 0)
        self.assertLess(elapsed, 8.0)


if __name__ == "__main__":
    unittest.main()
