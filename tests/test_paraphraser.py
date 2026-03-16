"""Tests for the paraphrase generator."""

import pytest
import spacy

from ambisense.detector import detect_ambiguities
from ambisense.paraphraser import (
    generate_paraphrases,
    generate_suggestions,
    get_domain_lexicon,
    get_rewrite_roles,
    get_rewrite_rules,
    get_templates,
)


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

    def test_offline_rewrite_config_loaded(self):
        assert len(get_rewrite_roles()) > 0
        assert len(get_domain_lexicon()["terms"]) > 0
        assert len(get_rewrite_rules()) > 0


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

    def test_paraphrases_preserve_subject_when_present(self, nlp):
        doc = nlp("I saw the man with the telescope")
        results = detect_ambiguities(doc)
        if results:
            high, low = generate_paraphrases(results[0])
            assert high == "Using the telescope, I saw the man"
            assert low == "I saw the man that has the telescope"


class TestGenerateSuggestions:
    def test_runtime_rule_prefers_running_on_for_low_attachment(self, nlp):
        doc = nlp("start a container on worker 2")
        results = detect_ambiguities(doc)
        if results:
            suggestions = generate_suggestions(results[0])
            assert suggestions.reading_high == "While on worker 2, start a container"
            assert suggestions.reading_low == "start a container that is on worker 2"
            assert suggestions.rewrite_high == "While connected to worker 2, start a container"
            assert suggestions.rewrite_low == "start a container running on worker 2"
            assert suggestions.high_rule_id == "runtime_on_host_or_cluster"
            assert suggestions.low_rule_id == "runtime_on_host_or_cluster"

    def test_artifact_rule_prefers_store_language(self, nlp):
        doc = nlp("download the image from the registry")
        results = detect_ambiguities(doc)
        if results:
            suggestions = generate_suggestions(results[0])
            assert suggestions.rewrite_high == "download the image directly from the registry"
            assert suggestions.rewrite_low == "download the image stored in the registry"
            assert suggestions.high_rule_id == "artifact_from_store"
            assert suggestions.low_rule_id == "artifact_from_store"

    def test_log_rule_prefers_recorded_in_for_low_attachment(self, nlp):
        doc = nlp("find the error in the log file")
        results = detect_ambiguities(doc)
        if results:
            suggestions = generate_suggestions(results[0])
            assert suggestions.rewrite_high == "Search the log file for the error"
            assert suggestions.rewrite_low == "find the error recorded in the log file"
            assert suggestions.high_rule_id == "diagnostic_in_log"
            assert suggestions.low_rule_id == "diagnostic_in_log"
