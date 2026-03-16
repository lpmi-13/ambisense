"""Offline generated rewrite-knowledge loading and compilation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List, Optional, Set


DATA_DIR = Path(__file__).parent / "data"
GENERATED_DIR = DATA_DIR / "generated"
COMPILED_FILENAME = "compiled_rewrite_knowledge.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CompiledRewriteKnowledge:
    """Generated offline overlays that augment curated rewrite rules."""

    semantic_role_overrides: Dict[str, Dict[str, str]]
    term_class_overrides: Dict[str, List[str]]
    frame_annotations: Dict[str, Dict[str, object]]
    role_aliases: Dict[str, str]
    semlink_frame_mappings: Dict[str, List[str]]


def _load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def default_generated_documents() -> Dict[str, dict]:
    """Return empty generated-data documents with the current schema."""
    return {
        "verbnet_index.json": {
            "schema_version": SCHEMA_VERSION,
            "resource": "verbnet",
            "roles": {},
        },
        "framenet_index.json": {
            "schema_version": SCHEMA_VERSION,
            "resource": "framenet",
            "frames": {},
        },
        "semlink_map.json": {
            "schema_version": SCHEMA_VERSION,
            "resource": "semlink",
            "role_aliases": {},
            "frame_mappings": {},
        },
        "wordnet_types.json": {
            "schema_version": SCHEMA_VERSION,
            "resource": "wordnet",
            "term_classes": {},
        },
        COMPILED_FILENAME: {
            "schema_version": SCHEMA_VERSION,
            "resource": "compiled_rewrite_knowledge",
            "semantic_role_overrides": {},
            "term_class_overrides": {},
            "frame_annotations": {},
            "role_aliases": {},
            "semlink_frame_mappings": {},
            "sources": {},
        },
    }


def ensure_generated_layout(generated_dir: Path = GENERATED_DIR) -> None:
    """Create placeholder generated-data documents if they do not exist yet."""
    generated_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in default_generated_documents().items():
        path = generated_dir / filename
        if not path.exists():
            _write_json(path, payload)


def load_generated_documents(generated_dir: Path = GENERATED_DIR) -> Dict[str, dict]:
    """Load all generated-data documents from disk."""
    ensure_generated_layout(generated_dir)
    return {
        filename: _load_json(generated_dir / filename)
        for filename in default_generated_documents()
    }


def validate_generated_documents(
    documents: Dict[str, dict],
    include_compiled: bool = True,
) -> List[str]:
    """Validate the basic shape of generated-data documents."""
    errors: List[str] = []
    required = {
        "verbnet_index.json": ("verbnet", ("roles",)),
        "framenet_index.json": ("framenet", ("frames",)),
        "semlink_map.json": ("semlink", ("role_aliases", "frame_mappings")),
        "wordnet_types.json": ("wordnet", ("term_classes",)),
    }
    if include_compiled:
        required[COMPILED_FILENAME] = (
            "compiled_rewrite_knowledge",
            ("semantic_role_overrides", "semlink_frame_mappings"),
        )

    for filename, (resource, keys) in required.items():
        doc = documents.get(filename)
        if doc is None:
            errors.append(f"missing generated document {filename}")
            continue
        if doc.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{filename} has unsupported schema version {doc.get('schema_version')}")
        if doc.get("resource") != resource:
            errors.append(f'{filename} has unexpected resource "{doc.get("resource")}"')
        for key in keys:
            if key not in doc:
                errors.append(f"{filename} is missing top-level key {key}")

    return errors


def compile_generated_knowledge(generated_dir: Path = GENERATED_DIR) -> dict:
    """Compile imported generated signals into one runtime overlay file."""
    documents = load_generated_documents(generated_dir)
    errors = validate_generated_documents(documents, include_compiled=False)
    if errors:
        raise ValueError("; ".join(errors))

    verbnet = documents["verbnet_index.json"]
    framenet = documents["framenet_index.json"]
    semlink = documents["semlink_map.json"]
    wordnet = documents["wordnet_types.json"]

    compiled = {
        "schema_version": SCHEMA_VERSION,
        "resource": "compiled_rewrite_knowledge",
        "semantic_role_overrides": verbnet.get("roles", {}),
        "term_class_overrides": wordnet.get("term_classes", {}),
        "frame_annotations": framenet.get("frames", {}),
        "role_aliases": semlink.get("role_aliases", {}),
        "semlink_frame_mappings": semlink.get("frame_mappings", {}),
        "sources": {
            "verbnet": "verbnet_index.json",
            "framenet": "framenet_index.json",
            "semlink": "semlink_map.json",
            "wordnet": "wordnet_types.json",
        },
    }

    _write_json(generated_dir / COMPILED_FILENAME, compiled)
    return compiled


def _coerce_compiled(payload: dict) -> CompiledRewriteKnowledge:
    """Coerce the compiled JSON payload into a typed structure."""
    return CompiledRewriteKnowledge(
        semantic_role_overrides=payload.get("semantic_role_overrides", {}),
        term_class_overrides=payload.get("term_class_overrides", {}),
        frame_annotations=payload.get("frame_annotations", {}),
        role_aliases=payload.get("role_aliases", {}),
        semlink_frame_mappings=payload.get("semlink_frame_mappings", {}),
    )


_COMPILED_CACHE: Optional[CompiledRewriteKnowledge] = None


def load_compiled_rewrite_knowledge(generated_dir: Path = GENERATED_DIR) -> CompiledRewriteKnowledge:
    """Load the compiled generated overlay file."""
    global _COMPILED_CACHE
    if generated_dir == GENERATED_DIR and _COMPILED_CACHE is not None:
        return _COMPILED_CACHE

    ensure_generated_layout(generated_dir)
    payload = _load_json(generated_dir / COMPILED_FILENAME)
    compiled = _coerce_compiled(payload)

    if generated_dir == GENERATED_DIR:
        _COMPILED_CACHE = compiled
    return compiled


def reset_compiled_cache() -> None:
    """Reset the compiled knowledge cache for tests or rebuilds."""
    global _COMPILED_CACHE
    _COMPILED_CACHE = None


def semantic_role_for(verb_lemma: str, prep: str, default_role: str) -> str:
    """Resolve a semantic role, preferring compiled offline overrides."""
    compiled = load_compiled_rewrite_knowledge()
    role = compiled.semantic_role_overrides.get(verb_lemma, {}).get(prep, default_role)
    return compiled.role_aliases.get(role, role)


def augment_term_classes(candidates: Set[str]) -> Set[str]:
    """Add generated term classes on top of curated local classes."""
    compiled = load_compiled_rewrite_knowledge()
    classes: Set[str] = set()
    for candidate in candidates:
        classes.update(compiled.term_class_overrides.get(candidate, []))
    return classes
