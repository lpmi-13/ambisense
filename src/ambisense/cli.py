"""CLI interface for ambisense — subcommand routing and shared options."""

import sys
from typing import Optional

import click

from ambisense import __version__
from ambisense.detector import analyze_text, load_model, detect_ambiguities
from ambisense.formatter import (
    format_csv,
    format_human,
    format_interactive_prompt,
    format_json,
)
from ambisense.paraphraser import generate_paraphrases
from ambisense.tree_builder import build_tree_pair
from ambisense.tree_renderer import render_tree, render_tree_pair


DEFAULT_PREPOSITIONS = "on,in,with,for,from,at,to,by,through,about"


def read_input(files, text=None):
    """Read input text from files, stdin, or inline text."""
    if text:
        return text.strip(), "<inline>"

    if files:
        parts = []
        for f in files:
            if f == "-":
                parts.append(sys.stdin.read().strip())
            else:
                with open(f) as fh:
                    parts.append(fh.read().strip())
        filename = files[0] if len(files) == 1 else "<multiple>"
        return "\n".join(parts), filename

    if not sys.stdin.isatty():
        return sys.stdin.read().strip(), "<stdin>"

    click.echo("Error: No input provided. Pass a file, pipe text, or use --help.", err=True)
    sys.exit(1)


@click.group(invoke_without_command=True)
@click.version_option(__version__, "-v", "--version")
@click.pass_context
def main(ctx):
    """ambisense — Prepositional Phrase Attachment Ambiguity Detector.

    Detect PP-attachment ambiguities in English text and show competing readings.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(scan)


@main.command()
@click.argument("files", nargs=-1, type=click.Path())
@click.option("-f", "--format", "fmt", type=click.Choice(["human", "json", "csv"]),
              default="human", help="Output format.")
@click.option("-i", "--interactive", is_flag=True, help="Interactive disambiguation mode.")
@click.option("-p", "--prepositions", default=DEFAULT_PREPOSITIONS,
              help="Comma-separated preposition watchlist.")
@click.option("--include-of", is_flag=True, help="Also flag 'of' PPs.")
@click.option("--include-copula", is_flag=True, help="Also flag PPs after copula verbs.")
@click.option("--max-distance", type=int, default=8,
              help="Max token distance for alternative head.")
@click.option("--model", default="en_core_web_sm", help="spaCy model to use.")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
@click.option("--verbose", is_flag=True, help="Show parse details.")
def scan(files, fmt, interactive, prepositions, include_of, include_copula,
         max_distance, model, no_color, verbose):
    """Detect PP-attachment ambiguities and show competing readings."""
    text, filename = read_input(files)
    if not text.strip():
        click.echo("No input text provided.", err=True)
        return

    watched = set(p.strip() for p in prepositions.split(","))

    records = analyze_text(
        text,
        model_name=model,
        watched_prepositions=watched,
        include_of=include_of,
        include_copula=include_copula,
        max_distance=max_distance,
    )

    use_color = not no_color and sys.stdout.isatty()

    if interactive:
        _run_interactive(records, use_color)
    elif fmt == "json":
        click.echo(format_json(records, filename=filename))
    elif fmt == "csv":
        click.echo(format_csv(records, filename=filename), nl=False)
    else:
        click.echo(format_human(records, filename=filename, verbose=verbose,
                                use_color=use_color))


def _run_interactive(records, use_color):
    """Run interactive disambiguation mode."""
    if not records:
        click.echo("\u2713 No PP-attachment ambiguities detected.")
        return

    total = len(records)
    for i, record in enumerate(records, 1):
        prompt_text = format_interactive_prompt(record, i, total, use_color=use_color)
        click.echo(prompt_text)

        choice = click.prompt("    Your intended meaning?", type=click.Choice(["A", "B", "S"],
                              case_sensitive=False))

        if choice.upper() == "S":
            click.echo("    \u2713 Marked as false positive. Skipping.")
        elif choice.upper() == "A":
            high, _ = generate_paraphrases(record)
            click.echo(f"    \u2713 Suggested rewrite:")
            click.echo(f"      \"{high}\"")
        elif choice.upper() == "B":
            _, low = generate_paraphrases(record)
            click.echo(f"    \u2713 Suggested rewrite:")
            click.echo(f"      \"{low}\"")

        if i < total:
            click.echo("")


@main.command()
@click.argument("sentence", required=False)
@click.option("--style", type=click.Choice(["unicode", "ascii", "bracket"]),
              default="unicode", help="Tree rendering style.")
@click.option("--compact", is_flag=True, help="Show only attachment-differing subtree.")
@click.option("--all-combos", is_flag=True,
              help="Show full cross-product of PP attachments.")
@click.option("-p", "--prepositions", default=DEFAULT_PREPOSITIONS,
              help="Comma-separated preposition watchlist.")
@click.option("--include-of", is_flag=True, help="Also flag 'of' PPs.")
@click.option("--max-distance", type=int, default=8,
              help="Max token distance for alternative head.")
@click.option("--model", default="en_core_web_sm", help="spaCy model to use.")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
def tree(sentence, style, compact, all_combos, prepositions, include_of,
         max_distance, model, no_color):
    """Parse a sentence and render competing syntax trees for each PP reading."""
    if sentence is None:
        if not sys.stdin.isatty():
            sentence = sys.stdin.read().strip()
        else:
            click.echo("Error: Provide a sentence as an argument or via stdin.", err=True)
            sys.exit(1)

    if not sentence.strip():
        click.echo("No sentence provided.", err=True)
        return

    watched = set(p.strip() for p in prepositions.split(","))

    nlp = load_model(model)
    doc = nlp(sentence)

    # Warn if multiple sentences
    sents = list(doc.sents)
    if len(sents) > 1:
        click.echo(
            f"Warning: Input contains {len(sents)} sentences. "
            "Processing only the first one.",
            err=True,
        )

    first_sent = sents[0]
    sent_doc = nlp(first_sent.text)

    records = detect_ambiguities(
        sent_doc,
        watched_prepositions=watched,
        include_of=include_of,
        max_distance=max_distance,
    )

    if not records:
        click.echo("\u2713 No PP-attachment ambiguities detected in this sentence.")
        return

    use_color = not no_color and sys.stdout.isatty()

    if all_combos:
        _render_all_combos(records, sent_doc, style, compact)
    else:
        _render_pairs(records, sent_doc, style, compact, use_color)


def _render_pairs(records, doc, style, compact, use_color):
    """Render one tree pair per ambiguous PP."""
    total = len(records)

    for i, record in enumerate(records):
        pp_text = record.pp_text
        verb_text = record.verb.text
        noun_text = record.noun.text

        if use_color:
            click.echo(f" \u26a0  Ambiguous PP: \"{pp_text}\"")
        else:
            click.echo(f" !  Ambiguous PP: \"{pp_text}\"")
        click.echo(
            f"    Showing high vs. low attachment for "
            f"verb \"{verb_text}\" / noun \"{noun_text}\""
        )

        # Note which other PPs are held at default
        if total > 1:
            others = [r for r in records if r is not record]
            held = ", ".join(f'"{r.pp_text}"' for r in others)
            click.echo(f"    Holding {held} at parser default.")

        click.echo()

        high_tree, low_tree = build_tree_pair(record, records if total > 1 else None)

        if compact:
            click.echo(f"    HIGH:  {render_tree(high_tree, style='bracket')}")
            click.echo(f"    LOW:   {render_tree(low_tree, style='bracket')}")
        else:
            pair_str = render_tree_pair(
                high_tree, low_tree,
                style=style,
                pp_text=pp_text,
                verb_text=verb_text,
                noun_text=noun_text,
            )
            # Indent each line
            for line in pair_str.split("\n"):
                click.echo(f"  {line}")

        if i < total - 1:
            click.echo()
            click.echo(f"{'─' * 60}")
            click.echo()


def _render_all_combos(records, doc, style, compact):
    """Render the full cross-product of PP attachments."""
    import itertools

    n = len(records)
    click.echo(f"Showing all {2**n} combinations for {n} ambiguous PP(s).\n")

    all_pp_tokens = [r.preposition for r in records]

    for combo_idx, bits in enumerate(itertools.product(["high", "low"], repeat=n)):
        assignments = dict(zip(all_pp_tokens, bits))
        label = ", ".join(
            f'"{r.pp_text}" \u2192 {b}' for r, b in zip(records, bits)
        )
        click.echo(f"  Combo {combo_idx + 1}: {label}")

        from ambisense.tree_builder import dep_to_constituency

        tree_node = dep_to_constituency(
            records[0].sentence, all_pp_tokens, assignments
        )

        if compact:
            click.echo(f"    {render_tree(tree_node, style='bracket')}")
        else:
            rendered = render_tree(tree_node, style=style)
            for line in rendered.split("\n"):
                click.echo(f"    {line}")
        click.echo()


if __name__ == "__main__":
    main()
