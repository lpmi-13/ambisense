"""Author-oriented document review helpers."""

from bisect import bisect_right
from dataclasses import dataclass
import re
from typing import List, Optional, Set

from ambisense.detector import detect_ambiguities, load_model
from ambisense.paraphraser import generate_suggestions


HEADING_PREFIX_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+")
LIST_PREFIX_RE = re.compile(r"^[ \t]{0,3}(?:[-+*]|\d+[.)])[ \t]+")
BLOCKQUOTE_PREFIX_RE = re.compile(r"^[ \t]{0,3}>[ \t]?")
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
INLINE_LINK_RE = re.compile(r"!?\[([^\]\n]+)\]\(([^)\n]+)\)")
REFERENCE_LINK_RE = re.compile(r"!?\[([^\]\n]+)\]\[[^\]\n]*\]")
URL_RE = re.compile(r"https?://[^\s)>]+")
AUTOLINK_RE = re.compile(r"<https?://[^>\n]+>")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class ProseBlock:
    """A contiguous block of prose extracted from a source document."""

    start_char: int
    text: str


@dataclass
class ReviewFinding:
    """A single author-facing ambiguity finding."""

    filename: str
    sentence: str
    highlighted_sentence: str
    pp_text: str
    line: int
    column: int
    sentence_start_char: int
    sentence_end_char: int
    pp_start_char: int
    pp_end_char: int
    parser_head_text: str
    parser_head_pos: str
    alternative_head_text: str
    alternative_head_pos: str
    verb_text: str
    noun_text: str
    reading_high: str
    reading_low: str
    rewrite_high: str
    rewrite_low: str
    high_rule_id: Optional[str]
    low_rule_id: Optional[str]


@dataclass
class DocumentReview:
    """Review results for a single document."""

    filename: str
    findings: List[ReviewFinding]


def _mask(chars: List[str], start: int, end: int) -> None:
    """Replace a character range with spaces while preserving newlines."""
    for idx in range(start, end):
        if chars[idx] != "\n":
            chars[idx] = " "


def _preserve_group(chars: List[str], source: str, match: re.Match, group: int) -> None:
    """Restore a captured group after masking the full match."""
    start, end = match.span(group)
    chars[start:end] = list(source[start:end])


def _collapse_whitespace(text: str) -> str:
    """Collapse internal whitespace for display."""
    return WHITESPACE_RE.sub(" ", text).strip()


def _line_kind(line: str) -> str:
    """Classify a Markdown line into a coarse prose block type."""
    if HEADING_PREFIX_RE.match(line):
        return "heading"
    if LIST_PREFIX_RE.match(line):
        return "list"
    if BLOCKQUOTE_PREFIX_RE.match(line):
        return "quote"
    return "paragraph"


def _apply_line_prefix_masks(raw_text: str, chars: List[str]) -> None:
    """Mask Markdown control prefixes but keep the visible prose."""
    offset = 0
    for line in raw_text.splitlines(keepends=True):
        line_body = line[:-1] if line.endswith("\n") else line
        consumed = 0

        while consumed < len(line_body):
            remaining = line_body[consumed:]
            match = (
                BLOCKQUOTE_PREFIX_RE.match(remaining)
                or HEADING_PREFIX_RE.match(remaining)
                or LIST_PREFIX_RE.match(remaining)
            )
            if match is None:
                break
            _mask(chars, offset + consumed + match.start(), offset + consumed + match.end())
            consumed += match.end()

        offset += len(line)


def _mask_inline_code(raw_text: str, chars: List[str]) -> None:
    """Mask inline code spans inside prose blocks."""
    offset = 0
    for line in raw_text.splitlines(keepends=True):
        line_body = line[:-1] if line.endswith("\n") else line
        idx = 0
        while idx < len(line_body):
            if line_body[idx] != "`":
                idx += 1
                continue

            run = 1
            while idx + run < len(line_body) and line_body[idx + run] == "`":
                run += 1

            closing = line_body.find("`" * run, idx + run)
            if closing == -1:
                idx += run
                continue

            _mask(chars, offset + idx, offset + closing + run)
            idx = closing + run

        offset += len(line)


def _sanitize_block(raw_text: str) -> str:
    """Prepare a prose block for parsing while preserving source offsets."""
    chars = list(raw_text)

    _apply_line_prefix_masks(raw_text, chars)

    for match in HTML_COMMENT_RE.finditer(raw_text):
        _mask(chars, match.start(), match.end())

    for pattern in (INLINE_LINK_RE, REFERENCE_LINK_RE):
        for match in pattern.finditer(raw_text):
            _mask(chars, match.start(), match.end())
            _preserve_group(chars, raw_text, match, 1)

    for pattern in (AUTOLINK_RE, URL_RE):
        for match in pattern.finditer(raw_text):
            _mask(chars, match.start(), match.end())

    _mask_inline_code(raw_text, chars)

    return "".join(chars)


def _finalize_block(blocks: List[ProseBlock], start: Optional[int], parts: List[str]) -> None:
    """Commit the current block if it contains any content."""
    if start is None or not parts:
        return
    text = "".join(parts)
    blocks.append(ProseBlock(start_char=start, text=_sanitize_block(text)))


def extract_prose_blocks(text: str, markdown: bool = True) -> List[ProseBlock]:
    """Extract parseable prose blocks from plain text or Markdown."""
    if not markdown:
        return [ProseBlock(start_char=0, text=text)]

    blocks: List[ProseBlock] = []
    current_start: Optional[int] = None
    current_parts: List[str] = []
    current_kind: Optional[str] = None

    offset = 0
    in_frontmatter = False
    frontmatter_open = False
    in_fence = False
    fence_marker = ""
    in_comment = False

    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        in_frontmatter = True
        frontmatter_open = True

    for line in lines:
        line_start = offset
        line_end = offset + len(line)
        stripped = line.strip()

        if in_frontmatter:
            if frontmatter_open:
                frontmatter_open = False
            elif stripped in ("---", "..."):
                in_frontmatter = False
            offset = line_end
            continue

        if in_comment:
            if "-->" in line:
                in_comment = False
            offset = line_end
            continue

        if in_fence:
            if stripped.startswith(fence_marker):
                in_fence = False
            offset = line_end
            continue

        if stripped.startswith("<!--") and "-->" not in stripped:
            _finalize_block(blocks, current_start, current_parts)
            current_start = None
            current_parts = []
            current_kind = None
            in_comment = True
            offset = line_end
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            _finalize_block(blocks, current_start, current_parts)
            current_start = None
            current_parts = []
            current_kind = None
            in_fence = True
            fence_marker = fence_match.group(1)[0] * len(fence_match.group(1))
            offset = line_end
            continue

        if not stripped:
            _finalize_block(blocks, current_start, current_parts)
            current_start = None
            current_parts = []
            current_kind = None
            offset = line_end
            continue

        kind = _line_kind(line)

        if kind == "heading":
            _finalize_block(blocks, current_start, current_parts)
            current_start = None
            current_parts = []
            current_kind = None
            blocks.append(ProseBlock(start_char=line_start, text=_sanitize_block(line)))
            offset = line_end
            continue

        if current_start is None:
            current_start = line_start
            current_parts = [line]
            current_kind = kind
        elif current_kind == kind:
            current_parts.append(line)
        elif current_kind in ("list", "quote") and kind == "paragraph":
            current_parts.append(line)
        else:
            _finalize_block(blocks, current_start, current_parts)
            current_start = line_start
            current_parts = [line]
            current_kind = kind

        offset = line_end

    _finalize_block(blocks, current_start, current_parts)
    return blocks


def _line_starts(text: str) -> List[int]:
    """Compute the starting offset of each source line."""
    starts = [0]
    for idx, char in enumerate(text):
        if char == "\n":
            starts.append(idx + 1)
    return starts


def _line_and_column(starts: List[int], char_index: int) -> tuple[int, int]:
    """Map a character offset to 1-based line and column numbers."""
    line_idx = bisect_right(starts, char_index) - 1
    line_start = starts[line_idx]
    return line_idx + 1, char_index - line_start + 1


def _highlight_sentence(sentence_text: str, start: int, end: int) -> str:
    """Insert visible markers around the ambiguous PP for display."""
    marked = sentence_text[:start] + "[[" + sentence_text[start:end] + "]]" + sentence_text[end:]
    return _collapse_whitespace(marked)


def _verb_label(record) -> str:
    """Return a stable, author-facing label for the governing verb."""
    return record.verb.text.lower()


def review_text(
    text: str,
    filename: str = "<stdin>",
    markdown: bool = True,
    model_name: str = "en_core_web_sm",
    watched_prepositions: Optional[Set[str]] = None,
    include_of: bool = False,
    include_copula: bool = False,
    max_distance: int = 8,
) -> DocumentReview:
    """Review a document and return author-facing ambiguity findings."""
    nlp = load_model(model_name)
    blocks = extract_prose_blocks(text, markdown=markdown)
    starts = _line_starts(text)
    findings: List[ReviewFinding] = []

    for block in blocks:
        if not block.text.strip():
            continue

        doc = nlp(block.text)
        records = detect_ambiguities(
            doc,
            watched_prepositions=watched_prepositions,
            include_of=include_of,
            include_copula=include_copula,
            max_distance=max_distance,
        )

        for record in records:
            suggestions = generate_suggestions(record)
            abs_sentence_start = block.start_char + record.sentence.start_char
            abs_sentence_end = block.start_char + record.sentence.end_char
            abs_pp_start = block.start_char + record.pp_span.start_char
            abs_pp_end = block.start_char + record.pp_span.end_char
            line, column = _line_and_column(starts, abs_pp_start)

            relative_start = record.pp_span.start_char - record.sentence.start_char
            relative_end = record.pp_span.end_char - record.sentence.start_char
            sentence_text = _collapse_whitespace(record.sentence.text)

            findings.append(
                ReviewFinding(
                    filename=filename,
                    sentence=sentence_text,
                    highlighted_sentence=_highlight_sentence(
                        record.sentence.text,
                        relative_start,
                        relative_end,
                    ),
                    pp_text=_collapse_whitespace(record.pp_text),
                    line=line,
                    column=column,
                    sentence_start_char=abs_sentence_start,
                    sentence_end_char=abs_sentence_end,
                    pp_start_char=abs_pp_start,
                    pp_end_char=abs_pp_end,
                    parser_head_text=record.parser_head.text,
                    parser_head_pos=record.parser_head.pos_,
                    alternative_head_text=record.alternative_head.text,
                    alternative_head_pos=record.alternative_head.pos_,
                    verb_text=_verb_label(record),
                    noun_text=record.noun.text,
                    reading_high=suggestions.reading_high,
                    reading_low=suggestions.reading_low,
                    rewrite_high=suggestions.rewrite_high,
                    rewrite_low=suggestions.rewrite_low,
                    high_rule_id=suggestions.high_rule_id,
                    low_rule_id=suggestions.low_rule_id,
                )
            )

    findings.sort(key=lambda finding: finding.pp_start_char)
    return DocumentReview(filename=filename, findings=findings)
