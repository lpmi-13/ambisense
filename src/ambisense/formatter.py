"""Output formatting for ambisense (human, JSON, CSV)."""

import csv
import io
import json
from typing import List, Optional

from ambisense.detector import AmbiguityRecord
from ambisense.paraphraser import generate_paraphrases
from ambisense.review import DocumentReview


def format_human(
    records: List[AmbiguityRecord],
    filename: Optional[str] = None,
    verbose: bool = False,
    use_color: bool = True,
) -> str:
    """Format ambiguity records for human-readable output."""
    if not records:
        if use_color:
            return "\u2713 No PP-attachment ambiguities detected."
        return "No PP-attachment ambiguities detected."

    lines = []
    for i, record in enumerate(records):
        high, low = generate_paraphrases(record)

        if use_color:
            header = f" \u26a0  Ambiguous PP: \"{record.pp_text}\""
        else:
            header = f" !  Ambiguous PP: \"{record.pp_text}\""

        lines.append(header)
        lines.append(f"    Sentence: {record.sentence.text.strip()}")
        lines.append(
            f"    Parser attached \"{record.pp_text}\" to: "
            f"{record.parser_head.pos_} \"{record.parser_head.text}\""
        )
        lines.append(
            f"    Alternative head: "
            f"{record.alternative_head.pos_} \"{record.alternative_head.text}\""
        )

        lines.append(
            f"    Reading A (high \u2192 verb \"{record.verb.text}\"):"
        )
        lines.append(f"      {high}")
        lines.append(
            f"    Reading B (low \u2192 noun \"{record.noun.text}\"):"
        )
        lines.append(f"      {low}")

        if verbose:
            lines.append(f"    Preposition: {record.preposition.text}")
            lines.append(f"    PP span: [{record.pp_span.start}:{record.pp_span.end}]")
            lines.append(
                f"    Parser attachment: {record.parser_attachment}"
            )

        if i < len(records) - 1:
            lines.append("")

    return "\n".join(lines)


def format_json(
    records: List[AmbiguityRecord],
    filename: Optional[str] = None,
    trees_ascii: Optional[List[str]] = None,
    trees_data: Optional[List[dict]] = None,
) -> str:
    """Format ambiguity records as JSON."""
    ambiguities = []
    for i, record in enumerate(records):
        high, low = generate_paraphrases(record)
        entry = {
            "sentence": record.sentence.text.strip(),
            "sentence_index": record.sentence.start,
            "pp_text": record.pp_text,
            "pp_start_char": record.pp_span.start_char,
            "pp_end_char": record.pp_span.end_char,
            "preposition": record.preposition.text,
            "parser_head": {
                "text": record.parser_head.text,
                "pos": record.parser_head.pos_,
                "index": record.parser_head.i,
            },
            "alternative_head": {
                "text": record.alternative_head.text,
                "pos": record.alternative_head.pos_,
                "index": record.alternative_head.i,
            },
            "readings": {
                "high": high,
                "low": low,
            },
        }
        if trees_ascii and i < len(trees_ascii):
            entry["tree_ascii"] = trees_ascii[i]
        if trees_data and i < len(trees_data):
            entry["tree"] = trees_data[i]
        ambiguities.append(entry)

    output = {"file": filename or "<stdin>", "ambiguities": ambiguities}
    return json.dumps(output, indent=2, ensure_ascii=False)


def format_csv(
    records: List[AmbiguityRecord],
    filename: Optional[str] = None,
) -> str:
    """Format ambiguity records as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "file", "sentence", "pp_text", "preposition",
        "parser_head", "parser_head_pos",
        "alternative_head", "alternative_head_pos",
        "reading_high", "reading_low",
    ])

    for record in records:
        high, low = generate_paraphrases(record)
        writer.writerow([
            filename or "<stdin>",
            record.sentence.text.strip(),
            record.pp_text,
            record.preposition.text,
            record.parser_head.text,
            record.parser_head.pos_,
            record.alternative_head.text,
            record.alternative_head.pos_,
            high,
            low,
        ])

    return buf.getvalue()


def format_interactive_prompt(
    record: AmbiguityRecord,
    index: int,
    total: int,
    use_color: bool = True,
) -> str:
    """Format a single ambiguity for interactive mode."""
    high, low = generate_paraphrases(record)

    if use_color:
        header = f" \u26a0  Ambiguous PP: \"{record.pp_text}\"  [{index} of {total}]"
    else:
        header = f" !  Ambiguous PP: \"{record.pp_text}\"  [{index} of {total}]"

    lines = [
        header,
        f"    Sentence: {record.sentence.text.strip()}",
        f"    [A] {high}",
        f"    [B] {low}",
        f"    [S] Skip (not ambiguous / false positive)",
    ]
    return "\n".join(lines)


def format_review_human(
    results: List[DocumentReview],
    use_color: bool = True,
) -> str:
    """Format author-facing review findings."""
    if not results:
        if use_color:
            return "\u2713 No PP-attachment ambiguities detected."
        return "No PP-attachment ambiguities detected."

    lines = []
    for result_index, result in enumerate(results):
        count = len(result.findings)
        if count == 0:
            if use_color:
                lines.append(f"\u2713 No PP-attachment ambiguities detected in {result.filename}.")
            else:
                lines.append(f"No PP-attachment ambiguities detected in {result.filename}.")
        else:
            prefix = "\u26a0" if use_color else "!"
            noun = "ambiguity" if count == 1 else "ambiguities"
            lines.append(f"{prefix} {count} possible PP-attachment {noun} in {result.filename}")
            lines.append("")

            for finding_index, finding in enumerate(result.findings):
                lines.append(f"{finding.filename}:{finding.line}:{finding.column}")
                lines.append(f"  {finding.highlighted_sentence}")
                lines.append(f'  If you mean the phrase attaches to verb "{finding.verb_text}":')
                lines.append(f"    {finding.rewrite_high}")
                lines.append(f'  If you mean the phrase modifies noun "{finding.noun_text}":')
                lines.append(f"    {finding.rewrite_low}")

                if finding_index < count - 1:
                    lines.append("")

        if result_index < len(results) - 1:
            lines.append("")

    return "\n".join(lines)


def format_review_json(results: List[DocumentReview]) -> str:
    """Format author-facing review findings as JSON."""
    payload = {
        "files": [
            {
                "file": result.filename,
                "ambiguities": [
                    {
                        "sentence": finding.sentence,
                        "highlighted_sentence": finding.highlighted_sentence,
                        "pp_text": finding.pp_text,
                        "line": finding.line,
                        "column": finding.column,
                        "sentence_start_char": finding.sentence_start_char,
                        "sentence_end_char": finding.sentence_end_char,
                        "pp_start_char": finding.pp_start_char,
                        "pp_end_char": finding.pp_end_char,
                        "parser_head": {
                            "text": finding.parser_head_text,
                            "pos": finding.parser_head_pos,
                        },
                        "alternative_head": {
                            "text": finding.alternative_head_text,
                            "pos": finding.alternative_head_pos,
                        },
                        "rewrites": {
                            "verb_attachment": finding.rewrite_high,
                            "noun_attachment": finding.rewrite_low,
                        },
                    }
                    for finding in result.findings
                ],
            }
            for result in results
        ]
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
