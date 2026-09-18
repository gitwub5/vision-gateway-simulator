from __future__ import annotations

import unittest

from evaluation.reports.compression_signal import (
    CompressionFrameRecord,
    build_compression_signal_report,
    unavailable_compression_signal_report,
)


class CompressionSignalReportTest(unittest.TestCase):
    def test_build_report_summarizes_frame_metadata(self) -> None:
        report = build_compression_signal_report(
            records=[
                CompressionFrameRecord(
                    frame_index=0,
                    timestamp=0.0,
                    pict_type="I",
                    key_frame=True,
                    packet_size=1000,
                ),
                CompressionFrameRecord(
                    frame_index=1,
                    timestamp=0.04,
                    pict_type="P",
                    key_frame=False,
                    packet_size=500,
                ),
                CompressionFrameRecord(
                    frame_index=2,
                    timestamp=0.08,
                    pict_type="P",
                    key_frame=False,
                    packet_size=250,
                ),
            ],
            dataset_config="sample.yaml",
            experiment_name="sample",
            dataset_type="video",
            input_path="sample.mp4",
        )

        self.assertTrue(report.metadata_available)
        self.assertEqual(report.frame_count, 3)
        self.assertEqual(report.key_frame_count, 1)
        self.assertAlmostEqual(report.key_frame_rate, 1 / 3)
        self.assertAlmostEqual(report.average_packet_size, 1750 / 3)
        self.assertEqual(report.max_packet_size, 1000)
        self.assertEqual(report.min_packet_size, 250)
        self.assertEqual(report.pict_type_counts, {"I": 1, "P": 2})

    def test_unavailable_report_keeps_reason(self) -> None:
        report = unavailable_compression_signal_report(
            dataset_config="sample.yaml",
            experiment_name="sample",
            dataset_type="image_sequence",
            input_path="frames",
            reason="image sequence",
        )

        self.assertFalse(report.metadata_available)
        self.assertEqual(report.status, "unavailable")
        self.assertEqual(report.reason, "image sequence")
        self.assertEqual(report.frame_count, 0)


if __name__ == "__main__":
    unittest.main()
