"""Tests for the filters module."""

import pytest
import spacy

from ambisense.filters import (
    get_phrasal_verbs,
    is_copula,
    is_phrasal_verb,
    crosses_coordination_boundary,
    load_phrasal_verbs,
)


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


class TestPhrasalVerbs:
    def test_load_phrasal_verbs_not_empty(self):
        verbs = load_phrasal_verbs()
        assert len(verbs) > 0

    def test_known_phrasal_verbs(self):
        verbs = get_phrasal_verbs()
        assert "look into" in verbs
        assert "carry out" in verbs
        assert "come across" in verbs

    def test_is_phrasal_verb_match(self, nlp):
        doc = nlp("look into the issue")
        verb = doc[0]  # look
        prep = doc[1]  # into
        assert is_phrasal_verb(verb, prep)

    def test_is_phrasal_verb_no_match(self, nlp):
        doc = nlp("start a container on worker")
        verb = doc[0]  # start
        prep = doc[3]  # on
        assert not is_phrasal_verb(verb, prep)


class TestCopula:
    def test_is_copula_be(self, nlp):
        doc = nlp("the cat is on the mat")
        assert is_copula(doc[2])  # "is"

    def test_not_copula(self, nlp):
        doc = nlp("start a container")
        assert not is_copula(doc[0])  # "start"


class TestCoordinationBoundary:
    def test_crosses_coordination(self, nlp):
        doc = nlp("read the book and write the report on the topic")
        # "read" and "report" are separated by "and"
        read_tok = doc[0]
        report_tok = doc[6]
        assert crosses_coordination_boundary(read_tok, report_tok, doc)

    def test_no_coordination(self, nlp):
        doc = nlp("start a container on worker")
        assert not crosses_coordination_boundary(doc[0], doc[2], doc)
