# Offline Rewrite Knowledge

`ambisense` now separates generic ambiguity readings from technically tuned rewrite suggestions.

## Runtime files

- `src/ambisense/data/templates.json`
  Purpose: generic high/low readings that explain the ambiguity.
- `src/ambisense/data/rewrite_roles.json`
  Purpose: coarse semantic roles keyed by preposition.
- `src/ambisense/data/domain_lexicon.json`
  Purpose: local technical noun classes such as `runtime_workload`, `host`, `artifact_store`, and `log`.
- `src/ambisense/data/rewrite_rules.json`
  Purpose: scored technical rewrite rules that override the generic reading text when a better domain-specific suggestion is available.
- `src/ambisense/data/preferred_terms.json`
  Purpose: preferred technical terminology substitutions applied inside generated rewrites.
- `src/ambisense/data/offline_rewrite_sources.json`
  Purpose: a manifest of official offline resources that can expand the rule system later.
- `src/ambisense/data/generated/`
  Purpose: schema-stable placeholders and future imported offline resource exports.
- `src/ambisense/data/generated/compiled_rewrite_knowledge.json`
  Purpose: the compiled runtime overlay built from the generated resource exports.

## Current pipeline

At runtime, the rewrite engine:

1. Generates neutral readings from `templates.json`.
2. Classifies the noun head and PP object with `domain_lexicon.json`.
3. Assigns a coarse semantic role from `rewrite_roles.json`.
4. Selects the highest-scoring matching rule from `rewrite_rules.json`.
5. Applies preferred terminology substitutions from `preferred_terms.json`.

This keeps the system fully offline and deterministic.

## Generated-data schema

`src/ambisense/data/generated/verbnet_index.json`

```json
{
  "schema_version": 1,
  "resource": "verbnet",
  "roles": {
    "deploy": {
      "on": "location"
    }
  }
}
```

`src/ambisense/data/generated/wordnet_types.json`

```json
{
  "schema_version": 1,
  "resource": "wordnet",
  "term_classes": {
    "daemon": ["runtime_workload"],
    "machine": ["host"]
  }
}
```

`src/ambisense/data/generated/semlink_map.json`

```json
{
  "frame_mappings": {
    "put-9.1": ["Placing"]
  },
  "schema_version": 1,
  "resource": "semlink",
  "role_aliases": {
    "locative": "location"
  }
}
```

`src/ambisense/data/generated/framenet_index.json`

```json
{
  "schema_version": 1,
  "resource": "framenet",
  "frames": {}
}
```

`src/ambisense/data/generated/compiled_rewrite_knowledge.json`

```json
{
  "schema_version": 1,
  "resource": "compiled_rewrite_knowledge",
  "semantic_role_overrides": {},
  "term_class_overrides": {},
  "frame_annotations": {},
  "role_aliases": {},
  "semlink_frame_mappings": {},
  "sources": {}
}
```

## Expansion path

The next offline expansion step is to populate generated indexes from official resources:

- VerbNet: verb classes, thematic roles, and preposition-sensitive frames.
- FrameNet: frame labels and valence patterns.
- SemLink: mappings between VerbNet, FrameNet, and PropBank-style roles.
- WordNet: noun-type backoff classes for terms not present in `domain_lexicon.json`.
- Vale vocabularies: shared preferred/discouraged terms for prose linting.

Those imports should compile into `src/ambisense/data/generated/` and only feed the curated local rule files after review. Runtime should continue to read the local compiled JSON, not raw upstream XML.

## Build pipeline

The repository now includes a local build step for generated data:

```bash
uv run python tools/build_generated_rewrite_knowledge.py
```

That command reads the placeholder or imported files in `src/ambisense/data/generated/` and rebuilds `compiled_rewrite_knowledge.json`.

## Importing local exports

The repository also includes a local importer for offline resource exports:

```bash
uv run python tools/import_offline_resources.py \
  --verbnet /path/to/verbnet/xml \
  --framenet /path/to/framenet/xml \
  --semlink /path/to/semlink/xml \
  --wordnet /path/to/wordnet \
  --seed-terms docs/technical_terms.txt
```

Expected source layouts:

- VerbNet: one XML file or a directory of XML files.
- FrameNet: one XML file or a directory of XML files.
- SemLink: one XML file or directory, or a SemLink 2 tree containing `pb-vn2.json` and `vn-fn2.json`.
- WordNet: `data.noun`, `dict/data.noun`, or a simplified export with `synsets.txt` and `hypernyms.txt`.

The importer writes the normalized outputs into `src/ambisense/data/generated/` and then rebuilds the compiled overlay. Imported SemLink frame mappings are preserved in `compiled_rewrite_knowledge.json` even though runtime rewrite selection does not use them yet.

## Automatic fetches

For the resources that support direct downloads, you can fetch and import them in one step:

```bash
uv run python tools/fetch_offline_resources.py
```

As of March 15, 2026 this covers:

- VerbNet 3.3 via the public tarball on the Colorado site.
- SemLink 2.0 via the public GitHub archive.
- WordNet 3.0 via the public Princeton tarball.

FrameNet still needs a manual download from the official request flow:

```bash
uv run python tools/fetch_offline_resources.py --framenet-path /path/to/framenet/xml
```

## Validation

Use the validator to check that rewrite rules reference known classes and roles:

```bash
uv run python tools/validate_rewrite_knowledge.py
```
