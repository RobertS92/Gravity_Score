"""Outcome label registry for Impact and Gravity training."""

from gravity_ml.labels.registry import (
    BANNED_LABEL_SOURCES,
    LabelSpec,
    get_label,
    list_labels,
    register_label,
    validate_registry,
)

__all__ = [
    "BANNED_LABEL_SOURCES",
    "LabelSpec",
    "get_label",
    "list_labels",
    "register_label",
    "validate_registry",
]
