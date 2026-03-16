#!/usr/bin/env python3
"""Import local offline resource exports into generated rewrite-knowledge files."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_GENERATED_DIR = ROOT / "src" / "ambisense" / "data" / "generated"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ambisense.rewrite_importers import (  # noqa: E402
    import_framenet,
    import_semlink,
    import_verbnet,
    import_wordnet,
    write_generated_resource,
)
from ambisense.rewrite_knowledge import (  # noqa: E402
    compile_generated_knowledge,
    ensure_generated_layout,
    reset_compiled_cache,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import local VerbNet/FrameNet/SemLink/WordNet exports into Ambisense generated data.",
    )
    parser.add_argument("--verbnet", type=Path, help="Path to a VerbNet XML file or directory.")
    parser.add_argument("--framenet", type=Path, help="Path to a FrameNet XML file or directory.")
    parser.add_argument(
        "--semlink",
        type=Path,
        help="Path to a SemLink XML file/directory or a SemLink 2 JSON directory containing pb-vn2.json and vn-fn2.json.",
    )
    parser.add_argument(
        "--wordnet",
        type=Path,
        help="Path to a WordNet export directory containing data.noun, dict/data.noun, or synsets.txt/hypernyms.txt.",
    )
    parser.add_argument(
        "--seed-terms",
        type=Path,
        help="Optional newline-delimited seed terms for WordNet classification.",
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        default=DEFAULT_GENERATED_DIR,
        help="Destination directory for generated JSON files.",
    )
    return parser


def _parse_args(argv: Optional[List[str]] = None) -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = _build_parser()
    return parser, parser.parse_args(argv)


def _require_existing_path(path: Optional[Path], flag: str, parser: argparse.ArgumentParser) -> None:
    if path is None:
        return
    if not path.exists():
        parser.error(f"{flag} path does not exist: {path}")


def _resource_summary(resource: str, payload: dict) -> List[str]:
    if resource == "verbnet":
        prep_count = sum(len(entry) for entry in payload["roles"].values())
        return [
            f"VerbNet lemma groups: {len(payload['roles'])}",
            f"VerbNet prep overrides: {prep_count}",
        ]
    if resource == "framenet":
        element_count = sum(len(entry["frame_elements"]) for entry in payload["frames"].values())
        return [
            f"FrameNet lexical units: {len(payload['frames'])}",
            f"FrameNet frame-element groups: {element_count}",
        ]
    if resource == "semlink":
        return [
            f"SemLink role aliases: {len(payload['role_aliases'])}",
            f"SemLink frame mappings: {len(payload.get('frame_mappings', {}))}",
        ]
    if resource == "wordnet":
        return [f"WordNet term-class groups: {len(payload['term_classes'])}"]
    raise ValueError(f"Unsupported resource summary: {resource}")


def main(argv: Optional[List[str]] = None) -> int:
    parser, args = _parse_args(argv)

    _require_existing_path(args.verbnet, "--verbnet", parser)
    _require_existing_path(args.framenet, "--framenet", parser)
    _require_existing_path(args.semlink, "--semlink", parser)
    _require_existing_path(args.wordnet, "--wordnet", parser)
    _require_existing_path(args.seed_terms, "--seed-terms", parser)

    if args.seed_terms is not None and args.wordnet is None:
        parser.error("--seed-terms requires --wordnet")

    generated_dir = args.generated_dir.resolve()
    ensure_generated_layout(generated_dir)

    imported: List[Tuple[str, dict]] = []

    if args.verbnet is not None:
        payload = import_verbnet(args.verbnet)
        write_generated_resource(payload, generated_dir / "verbnet_index.json")
        imported.append(("verbnet", payload))
    if args.framenet is not None:
        payload = import_framenet(args.framenet)
        write_generated_resource(payload, generated_dir / "framenet_index.json")
        imported.append(("framenet", payload))
    if args.semlink is not None:
        payload = import_semlink(args.semlink)
        write_generated_resource(payload, generated_dir / "semlink_map.json")
        imported.append(("semlink", payload))
    if args.wordnet is not None:
        payload = import_wordnet(args.wordnet, seed_terms_path=args.seed_terms)
        write_generated_resource(payload, generated_dir / "wordnet_types.json")
        imported.append(("wordnet", payload))

    if not imported:
        print("No resources imported. Provide at least one of --verbnet, --framenet, --semlink, or --wordnet.", file=sys.stderr)
        return 1

    compiled = compile_generated_knowledge(generated_dir)
    reset_compiled_cache()

    print(f"Wrote generated resource files to {generated_dir}")
    for resource, payload in imported:
        for line in _resource_summary(resource, payload):
            print(line)
    print(f"Compiled semantic role override groups: {len(compiled['semantic_role_overrides'])}")
    print(f"Compiled term-class override groups: {len(compiled['term_class_overrides'])}")
    print(f"Compiled FrameNet lexical units: {len(compiled['frame_annotations'])}")
    print(f"Compiled SemLink frame mappings: {len(compiled['semlink_frame_mappings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
