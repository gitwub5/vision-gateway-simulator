from __future__ import annotations

import unittest

from evaluation.hardware_metrics import collect_hardware_snapshot


class HardwareMetricsTest(unittest.TestCase):
    def test_collect_hardware_snapshot_has_stable_keys(self) -> None:
        snapshot = collect_hardware_snapshot()

        self.assertIn("platform", snapshot)
        self.assertIn("machine", snapshot)
        self.assertIn("python_version", snapshot)
        self.assertIn("torch", snapshot)
        self.assertIn("nvidia_smi", snapshot)


if __name__ == "__main__":
    unittest.main()
