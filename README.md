# ambisense

`ambisense` is a small Python CLI for detecting prepositional phrase attachment ambiguity in English text.

It uses spaCy to flag sentences where a prepositional phrase could plausibly attach to either a verb or a noun, such as `I saw the man with the telescope`.

## Setup

The project pins the default spaCy English model as a normal dependency, so `uv sync` is enough to create the environment and install what the CLI needs.

```bash
uv sync
```

## Run It

`uv run` is the simplest way to execute the CLI inside the project environment without activating `.venv` manually.

Run against sample text by piping text into stdin:

```bash
echo "I saw the man with the telescope." | uv run ambisense scan
```

Run against the sample file already included in this repository:

```bash
uv run ambisense scan examples/sample.txt
```

You can also switch formats when needed:

```bash
uv run ambisense scan --format json examples/sample.txt
```

You can also activate the environment and run the installed CLI directly:

```bash
source .venv/bin/activate
ambisense scan examples/sample.txt
```

Or call the script by path without activating anything:

```bash
.venv/bin/ambisense scan examples/sample.txt
```

## Review Tutorials

Use `review` when you want author-facing rewrite suggestions for a full document. The workflow is rule-based and local; it does not require an LLM. By default it treats input as Markdown, scans prose, and skips fenced code blocks and inline code.

Review a Markdown tutorial file:

```bash
uv run ambisense review examples/tutorial.md
```

Step through one ambiguity at a time and choose the intended meaning:

```bash
uv run ambisense review --interactive examples/tutorial.md
```

Apply the chosen rewrites back to the file in place:

```bash
uv run ambisense review --interactive --apply examples/tutorial.md
```

`--apply` only works with file inputs. For stdin or piped text, interactive review stays preview-only.

Interactive review presents each finding in an author-facing block:

```text
examples/tutorial.md:9:19
  Ambiguous phrase: "on worker 2"
  Sentence: "Start a container on worker 2."

  Possible readings:
  A. While on worker 2, start a container.
  B. Start a container that is on worker 2.

  Suggested rewrites:
  - If you mean A: "While connected to worker 2, start a container."
  - If you mean B: "Start a container running on worker 2."
```

Review plain text from stdin:

```bash
cat examples/sample.txt | uv run ambisense review --plain-text
```

Emit machine-readable findings for editor or CI integration:

```bash
uv run ambisense review --format json examples/tutorial.md
```

## Rewrite Knowledge

Technical rewrite suggestions come from local offline configuration in `src/ambisense/data/`. The current setup combines generic ambiguity readings with a curated technical lexicon, semantic-role defaults, preferred terms, and scored rewrite rules.

Validate that the local rewrite knowledge is internally consistent:

```bash
uv run python tools/validate_rewrite_knowledge.py
```

Import local offline resource exports into the generated overlay inputs, then recompile the runtime JSON in one step:

```bash
uv run python tools/import_offline_resources.py \
  --verbnet /path/to/verbnet/xml \
  --framenet /path/to/framenet/xml \
  --semlink /path/to/semlink/xml \
  --wordnet /path/to/wordnet \
  --seed-terms docs/technical_terms.txt
```

The importer only reads local files. It currently accepts:
- VerbNet: an XML file or directory of XML files
- FrameNet: an XML file or directory of XML files
- SemLink: an XML file or directory, or a SemLink 2 directory containing `pb-vn2.json` and `vn-fn2.json`
- WordNet: `data.noun`, `dict/data.noun`, or `synsets.txt` plus `hypernyms.txt`

Fetch and import the sources that support direct downloads:

```bash
uv run python tools/fetch_offline_resources.py
```

That command currently downloads and imports:
- `VerbNet 3.3`
- `SemLink 2.0`
- `WordNet 3.0`

`FrameNet 1.7` still needs a manual download from the official request page, then you can add it with:

```bash
uv run python tools/fetch_offline_resources.py --framenet-path /path/to/framenet/xml
```

Rebuild the compiled generated overlay after importing or editing files in `src/ambisense/data/generated/`:

```bash
uv run python tools/build_generated_rewrite_knowledge.py
```

The longer design notes for extending this offline are in `docs/offline_rewrite_knowledge.md`.

## Parse Trees

Use the `tree` subcommand to render competing parses for a single ambiguous sentence. The renderer supports `unicode`, `ascii`, and `bracket` styles.

Generate ASCII-art trees from a sentence passed directly on the command line:

```bash
uv run ambisense tree --style ascii "I saw the man with the telescope."
```

Generate the same ASCII-art trees by reading the sentence from a file:

```bash
uv run ambisense tree --style ascii < examples/sample.txt
```

The output shows both competing attachments side by side when the terminal is wide enough:

```text
HIGH (PP → verb "saw"):
                   S
 +-----------------+-+
NP                  VP
```
