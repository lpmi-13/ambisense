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

## Development

Add a runtime dependency:

```bash
uv add <package>
```

Add a development dependency:

```bash
uv add --dev <package>
```

Run the test suite:

```bash
uv run pytest
```
