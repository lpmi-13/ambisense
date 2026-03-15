"""ASCII art rendering for constituency trees."""

import shutil
from typing import List, Optional

from ambisense.tree_builder import TreeNode


HORIZONTAL_GAP = 2


def _block_width(block: List[str]) -> int:
    """Get the width of a text block."""
    return max((len(line) for line in block), default=0)


def _pad_block(block: List[str], width: int) -> List[str]:
    """Pad each line of a block to the given width."""
    return [line.ljust(width) for line in block]


def _center(text: str, width: int) -> str:
    """Center text within the given width."""
    if len(text) >= width:
        return text
    pad = (width - len(text)) // 2
    return " " * pad + text + " " * (width - len(text) - pad)


def _merge_blocks(blocks: List[List[str]], widths: List[int], gap: int) -> List[str]:
    """Merge multiple text blocks side by side."""
    if not blocks:
        return []

    max_height = max(len(b) for b in blocks)
    padded = []
    for block, w in zip(blocks, widths):
        extended = block + [" " * w] * (max_height - len(block))
        padded.append(_pad_block(extended, w))

    result = []
    separator = " " * gap
    for row_idx in range(max_height):
        row_parts = [padded[col_idx][row_idx] for col_idx in range(len(blocks))]
        result.append(separator.join(row_parts))

    return result


def render_unicode(node: TreeNode) -> List[str]:
    """Render a tree with Unicode box-drawing characters."""
    if node.is_leaf:
        return [node.text]

    if not node.children:
        return [node.label]

    # Recursively render children
    child_blocks = [render_unicode(c) for c in node.children]
    child_widths = [_block_width(b) for b in child_blocks]

    # Ensure minimum width for each child
    for i in range(len(child_widths)):
        child_widths[i] = max(child_widths[i], 1)

    total_width = sum(child_widths) + HORIZONTAL_GAP * (len(child_widths) - 1)
    label_width = len(node.label)
    total_width = max(total_width, label_width)

    # Center the label
    label_line = _center(node.label, total_width)

    # Draw connector line
    if len(node.children) == 1:
        # Single child - just a vertical bar
        child_center = child_widths[0] // 2
        connector = " " * child_center + "│" + " " * (total_width - child_center - 1)
    else:
        # Multiple children - draw ┌──┼──┐ style connectors
        centers = []
        offset = 0
        for i, w in enumerate(child_widths):
            centers.append(offset + w // 2)
            offset += w + HORIZONTAL_GAP

        connector_chars = [" "] * total_width
        leftmost = centers[0]
        rightmost = centers[-1]

        # Fill horizontal line
        for i in range(leftmost, min(rightmost + 1, total_width)):
            connector_chars[i] = "─"

        # Place connectors at child centers
        for idx, c in enumerate(centers):
            if c < total_width:
                if idx == 0:
                    connector_chars[c] = "┌"
                elif idx == len(centers) - 1:
                    connector_chars[c] = "┐"
                else:
                    connector_chars[c] = "┬"

        # Place the parent connector (┴) at the label center
        label_center = total_width // 2
        if leftmost < label_center < rightmost:
            connector_chars[label_center] = "┴"
        elif leftmost == rightmost:
            connector_chars[leftmost] = "│"

        connector = "".join(connector_chars)

    # Merge child blocks
    merged = _merge_blocks(child_blocks, child_widths, HORIZONTAL_GAP)

    return [label_line, connector] + merged


def render_ascii(node: TreeNode) -> List[str]:
    """Render a tree with ASCII characters (no Unicode)."""
    if node.is_leaf:
        return [node.text]

    if not node.children:
        return [node.label]

    child_blocks = [render_ascii(c) for c in node.children]
    child_widths = [_block_width(b) for b in child_blocks]

    for i in range(len(child_widths)):
        child_widths[i] = max(child_widths[i], 1)

    total_width = sum(child_widths) + HORIZONTAL_GAP * (len(child_widths) - 1)
    label_width = len(node.label)
    total_width = max(total_width, label_width)

    label_line = _center(node.label, total_width)

    if len(node.children) == 1:
        child_center = child_widths[0] // 2
        connector = " " * child_center + "|" + " " * (total_width - child_center - 1)
    else:
        centers = []
        offset = 0
        for i, w in enumerate(child_widths):
            centers.append(offset + w // 2)
            offset += w + HORIZONTAL_GAP

        connector_chars = [" "] * total_width
        leftmost = centers[0]
        rightmost = centers[-1]

        for i in range(leftmost, min(rightmost + 1, total_width)):
            connector_chars[i] = "-"

        for c in centers:
            if c < total_width:
                connector_chars[c] = "+"

        label_center = total_width // 2
        if leftmost < label_center < rightmost:
            connector_chars[label_center] = "+"

        connector = "".join(connector_chars)

    merged = _merge_blocks(child_blocks, child_widths, HORIZONTAL_GAP)
    return [label_line, connector] + merged


def render_bracket(node: TreeNode) -> str:
    """Render as bracket notation."""
    return node.to_bracket()


def render_tree(
    node: TreeNode,
    style: str = "unicode",
    max_width: Optional[int] = None,
) -> str:
    """Render a tree to a string.

    Args:
        node: The tree to render.
        style: "unicode", "ascii", or "bracket".
        max_width: Maximum width before falling back to bracket notation.

    Returns:
        The rendered tree as a string.
    """
    if style == "bracket":
        return render_bracket(node)

    if max_width is None:
        try:
            max_width = shutil.get_terminal_size().columns
        except (ValueError, OSError):
            max_width = 120

    if style == "ascii":
        lines = render_ascii(node)
    else:
        lines = render_unicode(node)

    rendered = "\n".join(line.rstrip() for line in lines)

    # If too wide, fall back to bracket
    actual_width = max(len(line) for line in lines) if lines else 0
    if actual_width > max_width:
        return render_bracket(node)

    return rendered


def render_tree_pair(
    high_tree: TreeNode,
    low_tree: TreeNode,
    style: str = "unicode",
    pp_text: str = "",
    verb_text: str = "",
    noun_text: str = "",
) -> str:
    """Render a pair of trees (high and low attachment) side by side."""
    high_str = render_tree(high_tree, style=style, max_width=999)
    low_str = render_tree(low_tree, style=style, max_width=999)

    high_lines = high_str.split("\n")
    low_lines = low_str.split("\n")

    high_header = f'HIGH (PP \u2192 verb "{verb_text}"):'
    low_header = f'LOW (PP \u2192 noun "{noun_text}"):'

    high_lines = [high_header, ""] + high_lines
    low_lines = [low_header, ""] + low_lines

    # Compute widths
    high_width = max(len(line) for line in high_lines)
    low_width = max(len(line) for line in low_lines)

    gap = 4
    total_width = high_width + gap + low_width

    # Check terminal width
    try:
        term_width = shutil.get_terminal_size().columns
    except (ValueError, OSError):
        term_width = 120

    if total_width > term_width:
        # Stack vertically instead
        return f"{high_header}\n{render_tree(high_tree, style=style)}\n\n{low_header}\n{render_tree(low_tree, style=style)}"

    # Merge side by side
    max_height = max(len(high_lines), len(low_lines))
    high_lines += [""] * (max_height - len(high_lines))
    low_lines += [""] * (max_height - len(low_lines))

    result = []
    for h, l in zip(high_lines, low_lines):
        result.append(f"{h:<{high_width}}{' ' * gap}{l}")

    return "\n".join(line.rstrip() for line in result)
