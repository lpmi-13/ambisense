"""Shared test fixtures."""

import pytest
import spacy


@pytest.fixture(scope="session")
def nlp():
    """Load the spaCy model once for all tests."""
    return spacy.load("en_core_web_sm")
