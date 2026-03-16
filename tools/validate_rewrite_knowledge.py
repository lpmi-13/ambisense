#!/usr/bin/env python3
"""Validate local offline rewrite knowledge files."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "ambisense" / "data"
SRC_DIR = ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ambisense.rewrite_knowledge import (  # noqa: E402
    compile_generated_knowledge,
    load_generated_documents,
    validate_generated_documents,
)


def load_json(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    roles = load_json("rewrite_roles.json")
    lexicon = load_json("domain_lexicon.json")
    rules = load_json("rewrite_rules.json")["rules"]
    preferred = load_json("preferred_terms.json")["substitutions"]
    sources = load_json("offline_rewrite_sources.json")["sources"]

    generated_documents = load_generated_documents(DATA_DIR / "generated")
    generated_errors = validate_generated_documents(generated_documents)

    known_roles = {entry["default"] for entry in roles.values()}
    known_classes = {
        class_name
        for classes in lexicon["terms"].values()
        for class_name in classes
    }

    errors = list(generated_errors)
    for rule in rules:
        when = rule.get("when", {})
        for class_name in when.get("noun_classes", []):
            if class_name not in known_classes:
                errors.append(f'rule "{rule["id"]}" references unknown noun class "{class_name}"')
        for class_name in when.get("object_classes", []):
            if class_name not in known_classes:
                errors.append(f'rule "{rule["id"]}" references unknown object class "{class_name}"')
        for role_name in when.get("semantic_roles", []):
            if role_name not in known_roles:
                errors.append(f'rule "{rule["id"]}" references unknown semantic role "{role_name}"')

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    compiled = compile_generated_knowledge(DATA_DIR / "generated")

    print(f"Validated {len(rules)} rewrite rule(s)")
    print(f"Validated {len(lexicon['terms'])} lexicon term(s)")
    print(f"Validated {len(preferred)} preferred-term substitution(s)")
    print(f"Documented {len(sources)} offline source reference(s)")
    print(f"Compiled {len(compiled['semantic_role_overrides'])} semantic role override group(s)")
    print(f"Compiled {len(compiled['term_class_overrides'])} term-class override group(s)")
    print(f"Compiled {len(compiled['frame_annotations'])} FrameNet lexical unit annotation(s)")
    print(f"Compiled {len(compiled['semlink_frame_mappings'])} SemLink frame mapping group(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
