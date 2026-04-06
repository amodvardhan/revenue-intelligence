"""Load and validate semantic_layer.yaml; compute content hash for traceability (Story 3.1)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SemanticBundle:
    """In-memory view of the governed semantic artifact."""

    version_label: str
    raw_bytes: bytes
    content_sha256: str
    data: dict[str, Any]


_bundle_cache: SemanticBundle | None = None


def semantic_yaml_path() -> Path:
    return Path(__file__).resolve().parent / "semantic_layer.yaml"


def load_semantic_bundle() -> SemanticBundle:
    """Load YAML from disk; cache for process lifetime."""
    global _bundle_cache
    if _bundle_cache is not None:
        return _bundle_cache
    path = semantic_yaml_path()
    raw = path.read_bytes()
    h = hashlib.sha256(raw).hexdigest()
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("semantic_layer.yaml must parse to a mapping")
    label = data.get("version_label")
    if not label or not isinstance(label, str):
        raise ValueError("semantic_layer.yaml must set version_label: string")
    _bundle_cache = SemanticBundle(version_label=label, raw_bytes=raw, content_sha256=h, data=data)
    return _bundle_cache


def clear_bundle_cache() -> None:
    """Test hook."""
    global _bundle_cache
    _bundle_cache = None
