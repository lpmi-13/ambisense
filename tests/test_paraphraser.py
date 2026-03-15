"""Tests for the paraphrase generator."""

import pytest
import spacy

from ambisense.detector import detect_ambiguities
from ambisense.paraphraser import generate_paraphrases, get_templates


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


class TestTemplates:
    def test_templates_loaded(self):
        templates = get_templates()
        assert len(templates) > 0

    def test_known_prepositions_have_templates(self):
        templates = get_templates()
        for prep in ["on", "in", "with", "for", "from", "at", "to", "by", "through", "about"]:
            assert prep in templates
            assert "high" in templates[prep]
            assert "low" in templates[prep]

    def test_default_template_exists(self):
        templates = get_templates()
        assert "_default" in templates


class TestGenerateParaphrases:
    def test_paraphrases_for_on(self, nlp):
        doc = nlp("start a container on worker 2")
        results = detect_ambiguities(doc)
        if results:
            high, low = generate_paraphrases(results[0])
            assert isinstance(high, str)
            assert isinstance(low, str)
            assert len(high) > 0
            assert len(low) > 0

    def test_paraphrases_for_with(self, nlp):
        doc = nlp("cut the steak with the knife")
        results = detect_ambiguities(doc)
        if results:
            high, low = generate_paraphrases(results[0])
            assert isinstance(high, str)
            assert isinstance(low, str)

    def test_paraphrases_differ(self, nlp):
        doc = nlp("I saw the man with the telescope")
        results = detect_ambiguities(doc)
        if results:
            high, low = generate_paraphrases(results[0])
            assert high != low, "High and low paraphrases should differ"
