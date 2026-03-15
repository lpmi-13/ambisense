"""Tests for the tree renderer module."""

import pytest

from ambisense.tree_builder import TreeNode
from ambisense.tree_renderer import (
    render_ascii,
    render_bracket,
    render_tree,
    render_tree_pair,
    render_unicode,
)


def make_sample_tree():
    """Create a sample tree for testing."""
    det = TreeNode(label="det", text="a", is_leaf=True)
    noun = TreeNode(label="N", text="container", is_leaf=True)
    np = TreeNode(label="NP", children=[det, noun])

    verb = TreeNode(label="V", text="start", is_leaf=True)
    vp = TreeNode(label="VP", children=[verb, np])

    return TreeNode(label="S", children=[vp])


class TestRenderUnicode:
    def test_leaf(self):
        node = TreeNode(label="N", text="cat", is_leaf=True)
        lines = render_unicode(node)
        assert lines == ["cat"]

    def test_simple_tree(self):
        tree = make_sample_tree()
        lines = render_unicode(tree)
        assert len(lines) > 0
        # The root label should appear
        assert any("S" in line for line in lines)

    def test_single_child(self):
        child = TreeNode(label="N", text="cat", is_leaf=True)
        parent = TreeNode(label="NP", children=[child])
        lines = render_unicode(parent)
        assert any("NP" in line for line in lines)
        assert any("cat" in line for line in lines)


class TestRenderAscii:
    def test_simple_tree(self):
        tree = make_sample_tree()
        lines = render_ascii(tree)
        assert len(lines) > 0
        # Should not contain unicode box-drawing characters
        text = "\n".join(lines)
        assert "┌" not in text
        assert "┐" not in text

    def test_leaf(self):
        node = TreeNode(label="N", text="cat", is_leaf=True)
        lines = render_ascii(node)
        assert lines == ["cat"]


class TestRenderBracket:
    def test_simple_tree(self):
        tree = make_sample_tree()
        result = render_bracket(tree)
        assert result.startswith("[S")
        assert "[VP" in result
        assert "[NP" in result
        assert "start" in result
        assert "container" in result


class TestRenderTree:
    def test_unicode_style(self):
        tree = make_sample_tree()
        result = render_tree(tree, style="unicode", max_width=200)
        assert "S" in result

    def test_ascii_style(self):
        tree = make_sample_tree()
        result = render_tree(tree, style="ascii", max_width=200)
        assert "S" in result

    def test_bracket_style(self):
        tree = make_sample_tree()
        result = render_tree(tree, style="bracket")
        assert result.startswith("[S")

    def test_fallback_to_bracket_on_narrow_width(self):
        tree = make_sample_tree()
        result = render_tree(tree, style="unicode", max_width=5)
        # Should fall back to bracket notation
        assert result.startswith("[S")


class TestRenderTreePair:
    def test_pair_rendering(self):
        tree1 = make_sample_tree()
        tree2 = make_sample_tree()
        result = render_tree_pair(
            tree1, tree2,
            style="unicode",
            pp_text="on worker 2",
            verb_text="start",
            noun_text="container",
        )
        assert "HIGH" in result
        assert "LOW" in result
