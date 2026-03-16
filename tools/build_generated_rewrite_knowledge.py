#!/usr/bin/env python3
"""Compile generated offline resource exports into one runtime overlay."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ambisense.rewrite_knowledge import compile_generated_knowledge  # noqa: E402


def main() -> int:
    compiled = compile_generated_knowledge(ROOT / "src" / "ambisense" / "data" / "generated")
    print("Compiled generated rewrite knowledge")
    print(f"Semantic role override groups: {len(compiled['semantic_role_overrides'])}")
    print(f"Term-class override groups: {len(compiled['term_class_overrides'])}")
    print(f"FrameNet lexical units: {len(compiled['frame_annotations'])}")
    print(f"SemLink frame mappings: {len(compiled['semlink_frame_mappings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
