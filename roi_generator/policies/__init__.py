"""ROI policy implementations."""

from roi_generator.policies.base import RoiPolicy
from roi_generator.policies.component_bbox import ComponentBboxPolicy

__all__ = ["RoiPolicy", "ComponentBboxPolicy"]
