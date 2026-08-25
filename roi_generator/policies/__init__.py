"""ROI policy implementations."""

from roi_generator.core.config import RoiGeneratorConfig
from roi_generator.policies.base import RoiPolicy
from roi_generator.policies.component_bbox import ComponentBboxPolicy
from roi_generator.policies.hybrid_component_tile import HybridComponentTilePolicy
from roi_generator.policies.tile_mask import TileMaskPolicy


def create_roi_policy(config: RoiGeneratorConfig) -> RoiPolicy:
    policy_name = config.roi_policy.strip().lower()
    if policy_name == ComponentBboxPolicy.name:
        return ComponentBboxPolicy(config)
    if policy_name == TileMaskPolicy.name:
        return TileMaskPolicy(config)
    if policy_name == HybridComponentTilePolicy.name:
        return HybridComponentTilePolicy(config)
    raise ValueError(f"Unsupported roi_policy: {config.roi_policy}")


__all__ = [
    "RoiPolicy",
    "ComponentBboxPolicy",
    "HybridComponentTilePolicy",
    "TileMaskPolicy",
    "create_roi_policy",
]
