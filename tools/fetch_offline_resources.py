#!/usr/bin/env python3
"""Download supported offline lexical resources and import them into generated data."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_CACHE_DIR = ROOT / ".offline-resources"
DEFAULT_GENERATED_DIR = ROOT / "src" / "ambisense" / "data" / "generated"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ambisense.rewrite_fetchers import (  # noqa: E402
    fetch_offline_resource,
    get_offline_resource_specs,
)
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
    specs = get_offline_resource_specs()
    parser = argparse.ArgumentParser(
        description="Fetch supported offline resources and import them into Ambisense generated data.",
    )
    parser.add_argument(
        "resources",
        nargs="*",
        help="Resources to fetch. Defaults to the automatically downloadable ones.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Directory for downloaded archives and extracted resource trees.",
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        default=DEFAULT_GENERATED_DIR,
        help="Destination directory for generated JSON files.",
    )
    parser.add_argument(
        "--seed-terms",
        type=Path,
        help="Optional newline-delimited seed terms for WordNet classification.",
    )
    parser.add_argument(
        "--framenet-path",
        type=Path,
        help="Optional local FrameNet XML path to import alongside fetched resources.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload and reextract archives even if cached copies already exist.",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Only fetch and extract resources; do not regenerate JSON outputs.",
    )
    return parser


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


def _default_resources() -> List[str]:
    return [
        key
        for key, spec in get_offline_resource_specs().items()
        if not spec.manual_only
    ]


def _selected_resources(args: argparse.Namespace) -> List[str]:
    return list(args.resources) if args.resources else _default_resources()


def _import_payloads(
    fetched_paths: Dict[str, Path],
    framenet_path: Optional[Path],
    generated_dir: Path,
    seed_terms_path: Optional[Path],
) -> Tuple[List[Tuple[str, dict]], dict]:
    ensure_generated_layout(generated_dir)
    imported: List[Tuple[str, dict]] = []

    if "verbnet" in fetched_paths:
        payload = import_verbnet(fetched_paths["verbnet"])
        write_generated_resource(payload, generated_dir / "verbnet_index.json")
        imported.append(("verbnet", payload))
    if "semlink" in fetched_paths:
        payload = import_semlink(fetched_paths["semlink"])
        write_generated_resource(payload, generated_dir / "semlink_map.json")
        imported.append(("semlink", payload))
    if "wordnet" in fetched_paths:
        payload = import_wordnet(fetched_paths["wordnet"], seed_terms_path=seed_terms_path)
        write_generated_resource(payload, generated_dir / "wordnet_types.json")
        imported.append(("wordnet", payload))
    if framenet_path is not None:
        payload = import_framenet(framenet_path)
        write_generated_resource(payload, generated_dir / "framenet_index.json")
        imported.append(("framenet", payload))

    compiled = compile_generated_knowledge(generated_dir)
    reset_compiled_cache()
    return imported, compiled


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    specs = get_offline_resource_specs()
    selected = _selected_resources(args)

    unknown = sorted(resource for resource in selected if resource not in specs)
    if unknown:
        parser.error(
            f"unknown resource(s): {', '.join(unknown)}; choose from {', '.join(sorted(specs))}"
        )

    if "framenet" in selected and args.framenet_path is None:
        parser.error(specs["framenet"].manual_instructions or "FrameNet must be supplied locally with --framenet-path.")
    if args.seed_terms is not None and "wordnet" not in selected:
        parser.error("--seed-terms requires WordNet to be selected.")
    if args.framenet_path is not None and not args.framenet_path.exists():
        parser.error(f"--framenet-path does not exist: {args.framenet_path}")
    if args.seed_terms is not None and not args.seed_terms.exists():
        parser.error(f"--seed-terms does not exist: {args.seed_terms}")

    cache_dir = args.cache_dir.resolve()
    generated_dir = args.generated_dir.resolve()
    fetched_paths: Dict[str, Path] = {}

    for resource in selected:
        spec = specs[resource]
        if spec.manual_only:
            continue
        downloaded = fetch_offline_resource(resource, cache_dir, force=args.force)
        fetched_paths[resource] = downloaded.import_path
        print(f"Fetched {spec.display_name} to {downloaded.import_path}")

    if args.framenet_path is not None:
        print(f"Using local FrameNet path {args.framenet_path.resolve()}")

    if args.skip_import:
        return 0

    imported, compiled = _import_payloads(
        fetched_paths,
        args.framenet_path.resolve() if args.framenet_path is not None else None,
        generated_dir,
        args.seed_terms.resolve() if args.seed_terms is not None else None,
    )

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
