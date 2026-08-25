from __future__ import annotations

import unittest

from common import FrameSize, ROI
from roi_generator.core.budget import estimate_budget_cost, evaluate_budget_fallback
from roi_generator.core.config import RoiGeneratorConfig


class RoiBudgetTest(unittest.TestCase):
    def test_budget_can_be_disabled(self) -> None:
        decision = evaluate_budget_fallback(
            [ROI(0, 0, 100, 100)],
            FrameSize(100, 100),
            RoiGeneratorConfig(budget_enabled=False, max_total_roi_area_ratio=0.1),
        )

        self.assertFalse(decision.should_fallback)

    def test_roi_count_is_batch_slot_overflow(self) -> None:
        decision = evaluate_budget_fallback(
            [ROI(0, 0, 10, 10), ROI(20, 20, 10, 10)],
            FrameSize(100, 100),
            RoiGeneratorConfig(max_roi_per_frame=1),
        )

        self.assertTrue(decision.should_fallback)
        self.assertEqual(decision.reason, "batch_slot_overflow")

    def test_tile_budget_applies_only_to_tile_policies(self) -> None:
        config = RoiGeneratorConfig(max_selected_tile_count=2)

        component_decision = evaluate_budget_fallback(
            [ROI(0, 0, 10, 10)],
            FrameSize(100, 100),
            config,
            selected_tile_count=3,
            tile_budget_applies=False,
        )
        tile_decision = evaluate_budget_fallback(
            [ROI(0, 0, 10, 10)],
            FrameSize(100, 100),
            config,
            selected_tile_count=3,
            tile_budget_applies=True,
        )

        self.assertFalse(component_decision.should_fallback)
        self.assertTrue(tile_decision.should_fallback)
        self.assertEqual(tile_decision.reason, "tile_count_overhead_exceeds_gain")

    def test_tensor_budget_overflow(self) -> None:
        decision = evaluate_budget_fallback(
            [ROI(0, 0, 30, 30)],
            FrameSize(100, 100),
            RoiGeneratorConfig(max_tensor_batch_cost=800),
        )

        self.assertTrue(decision.should_fallback)
        self.assertEqual(decision.reason, "tensor_budget_overflow")

    def test_estimate_budget_cost_includes_full_frame_when_requested(self) -> None:
        cost = estimate_budget_cost(
            [ROI(0, 0, 10, 20)],
            FrameSize(100, 100),
            selected_tile_count=4,
            tile_group_count=2,
            should_run_full_frame=True,
        )

        self.assertEqual(cost.roi_batch_slots_used, 1)
        self.assertEqual(cost.selected_tile_count, 4)
        self.assertEqual(cost.tile_group_count, 2)
        self.assertEqual(cost.estimated_tensor_pixels, 200)
        self.assertEqual(cost.tensor_batch_cost, 200)
        self.assertEqual(cost.effective_input_area, 10200)


if __name__ == "__main__":
    unittest.main()
