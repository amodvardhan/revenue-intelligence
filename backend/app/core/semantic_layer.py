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


def format_nl_system_addendum(data: dict[str, Any]) -> str:
    """
    Compact governed grounding for the NL planner system prompt (plan JSON, not SQL).
    Source: nl_grounding in semantic_layer.yaml.
    """
    block = data.get("nl_grounding")
    if not isinstance(block, dict):
        return ""
    lines: list[str] = [
        "Governed semantic layer (reference only — never emit SQL or invent tables):",
    ]
    pt = block.get("primary_fact_table")
    if isinstance(pt, str) and pt:
        lines.append(f"- Primary revenue fact: {pt}")
    fcol = block.get("fact_columns")
    if isinstance(fcol, dict) and fcol:
        parts = [f"{k} → {v}" for k, v in fcol.items()]
        lines.append(f"  Columns: {', '.join(parts)}")
    fks = block.get("foreign_keys")
    if isinstance(fks, dict) and fks:
        lines.append("- Fact foreign keys → dimension tables:")
        for fk, dim in fks.items():
            lines.append(f"  - {fk} → {dim}")
    hints = block.get("planner_hints")
    if isinstance(hints, list):
        for h in hints:
            if isinstance(h, str) and h.strip():
                lines.append(f"- {h.strip()}")
    vn = block.get("variance_narrative")
    if isinstance(vn, dict):
        lines.append("- Variance / MoM commentary (intent variance_comment):")
        desc = vn.get("description")
        if isinstance(desc, str) and desc.strip():
            lines.append(f"  {desc.strip()}")
        tbl = vn.get("table")
        tcol = vn.get("text_column")
        tkey = vn.get("time_key")
        if isinstance(tbl, str) and tbl:
            tail = ""
            if isinstance(tcol, str) and tcol:
                tail += f", text column {tcol}"
            if isinstance(tkey, str) and tkey:
                tail += f", month key {tkey}"
            lines.append(f"  Physical table: {tbl}{tail}.")
        vfks = vn.get("foreign_keys")
        if isinstance(vfks, dict) and vfks:
            lines.append("  Scope (FKs):")
            for fk, dim in vfks.items():
                lines.append(f"    - {fk} → {dim}")
        vhints = vn.get("planner_hints")
        if isinstance(vhints, list):
            for h in vhints:
                if isinstance(h, str) and h.strip():
                    lines.append(f"  - {h.strip()}")
    return "\n".join(lines)
