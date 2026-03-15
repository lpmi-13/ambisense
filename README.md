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

Review plain text from stdin:

```bash
cat examples/sample.txt | uv run ambisense review --plain-text
```

Emit machine-readable findings for editor or CI integration:

```bash
uv run ambisense review --format json examples/tutorial.md
```

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
