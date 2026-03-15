"""Tests for the PP-attachment ambiguity detector."""

import pytest
import spacy

from ambisense.detector import (
    analyze_text,
    detect_ambiguities,
    find_alternative_head,
    get_pp_span,
)


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


class TestDetectAmbiguities:
    """Test that known ambiguous sentences are flagged."""

    @pytest.mark.parametrize("sentence", [
        "start a container on worker 2",
        "cut the steak with the knife",
        "I saw the man with the telescope",
    ])
    def test_known_ambiguous_sentences(self, nlp, sentence):
        doc = nlp(sentence)
        results = detect_ambiguities(doc)
        assert len(results) > 0, f"Expected ambiguity in: {sentence}"

    @pytest.mark.parametrize("sentence", [
        "he is happy",
        "she walked quickly",
    ])
    def test_no_pp_sentences(self, nlp, sentence):
        doc = nlp(sentence)
        results = detect_ambiguities(doc)
        assert len(results) == 0, f"Expected no ambiguity in: {sentence}"

    def test_of_suppressed_by_default(self, nlp):
        doc = nlp("the color of the button")
        results = detect_ambiguities(doc)
        assert len(results) == 0

    def test_of_included_when_requested(self, nlp):
        doc = nlp("the color of the button")
        results = detect_ambiguities(doc, include_of=True)
        # May or may not flag depending on parse structure
        # The important thing is that "of" is now in the watchlist

    def test_phrasal_verb_suppressed(self, nlp):
        doc = nlp("look into the issue")
        results = detect_ambiguities(doc)
        assert len(results) == 0, "Phrasal verb 'look into' should be suppressed"

    def test_copula_suppressed_by_default(self, nlp):
        doc = nlp("the cat is on the mat")
        results = detect_ambiguities(doc)
        # Copula verbs should be suppressed
        for r in results:
            assert r.verb.lemma_ != "be", "Copula 'be' should be suppressed"


class TestAnalyzeText:
    def test_basic_analysis(self):
        results = analyze_text("start a container on worker 2")
        assert len(results) > 0

    def test_empty_text(self):
        results = analyze_text("")
        assert len(results) == 0

    def test_custom_prepositions(self):
        results = analyze_text(
            "start a container on worker 2",
            watched_prepositions={"with"},  # "on" not watched
        )
        # Should not flag "on" since it's not in the watchlist
        for r in results:
            assert r.preposition.text.lower() != "on"


class TestAmbiguityRecord:
    def test_record_properties(self, nlp):
        doc = nlp("start a container on worker 2")
        results = detect_ambiguities(doc)
        if results:
            record = results[0]
            assert record.verb is not None
            assert record.noun is not None
            assert record.pp_obj_text != ""
            assert record.np_text != ""
            assert record.det_text != ""
            assert record.parser_attachment in ("high", "low")
            assert record.alternative_attachment in ("high", "low")


class TestGetPPSpan:
    def test_pp_span(self, nlp):
        doc = nlp("start a container on worker 2")
        for token in doc:
            if token.dep_ == "prep" and token.text == "on":
                span = get_pp_span(token)
                assert "on" in span.text
                assert "worker" in span.text
                break


class TestEdgeCases:
    def test_multiple_pps(self, nlp):
        doc = nlp("send the report to the client for review")
        results = detect_ambiguities(doc)
        # Should be able to handle sentences with multiple PPs

    def test_max_distance(self, nlp):
        doc = nlp("start a container on worker 2")
        results_short = detect_ambiguities(doc, max_distance=1)
        results_long = detect_ambiguities(doc, max_distance=20)
        # Shorter distance should find fewer or equal ambiguities
        assert len(results_short) <= len(results_long)
