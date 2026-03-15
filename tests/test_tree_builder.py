"""Tests for the tree builder module."""

import pytest
import spacy

from ambisense.detector import detect_ambiguities
from ambisense.tree_builder import (
    TreeNode,
    build_np_node,
    build_pp_node,
    build_tree_pair,
    dep_to_constituency,
    leaf,
)


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


class TestTreeNode:
    def test_leaf_node(self):
        node = TreeNode(label="N", text="container", is_leaf=True)
        assert node.is_leaf
        assert node.text == "container"

    def test_bracket_notation_leaf(self):
        node = TreeNode(label="N", text="container", is_leaf=True)
        assert node.to_bracket() == "[N container]"

    def test_bracket_notation_tree(self):
        child1 = TreeNode(label="det", text="a", is_leaf=True)
        child2 = TreeNode(label="N", text="container", is_leaf=True)
        np = TreeNode(label="NP", children=[child1, child2])
        result = np.to_bracket()
        assert result == "[NP [det a] [N container]]"

    def test_to_dict(self):
        child = TreeNode(label="N", text="cat", is_leaf=True)
        parent = TreeNode(label="NP", children=[child])
        d = parent.to_dict()
        assert d["label"] == "NP"
        assert len(d["children"]) == 1
        assert d["children"][0]["text"] == "cat"


class TestBuildTreePair:
    def test_tree_pair_basic(self, nlp):
        doc = nlp("start a container on worker 2")
        results = detect_ambiguities(doc)
        if results:
            high_tree, low_tree = build_tree_pair(results[0])
            assert high_tree.label == "S"
            assert low_tree.label == "S"
            # The trees should differ in structure
            assert high_tree.to_bracket() != low_tree.to_bracket()

    def test_tree_pair_with_multiple_ambiguities(self, nlp):
        doc = nlp("I saw the man with the telescope")
        results = detect_ambiguities(doc)
        if results:
            for record in results:
                high_tree, low_tree = build_tree_pair(record, results)
                assert high_tree.label == "S"
                assert low_tree.label == "S"


class TestDepToConstituency:
    def test_basic_sentence(self, nlp):
        doc = nlp("start a container")
        sent = list(doc.sents)[0]
        tree = dep_to_constituency(sent, [], {})
        assert tree.label == "S"

    def test_with_subject(self, nlp):
        doc = nlp("I saw the man")
        sent = list(doc.sents)[0]
        tree = dep_to_constituency(sent, [], {})
        assert tree.label == "S"
        # Should have at least NP (subject) and VP
        labels = [c.label for c in tree.children]
        assert "VP" in labels


class TestLeaf:
    def test_leaf_creation(self, nlp):
        doc = nlp("container")
        node = leaf(doc[0])
        assert node.is_leaf
        assert node.text == "container"
