"""Filters to reduce false positives in PP-attachment ambiguity detection."""

from pathlib import Path
from typing import Set


DEFAULT_WATCHED_PREPOSITIONS = frozenset(
    ["on", "in", "with", "for", "from", "at", "to", "by", "through", "about"]
)

COPULA_VERBS = frozenset(
    ["be", "is", "am", "are", "was", "were", "been", "being",
     "seem", "seems", "seemed", "appear", "appears", "appeared",
     "become", "becomes", "became", "remain", "remains", "remained"]
)

COORDINATION_DEPS = frozenset(["cc", "conj"])


def load_phrasal_verbs() -> Set[str]:
    """Load phrasal verbs from the data file."""
    data_path = Path(__file__).parent / "data" / "phrasal_verbs.txt"
    phrasal_verbs = set()
    if data_path.exists():
        for line in data_path.read_text().strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                phrasal_verbs.add(line.lower())
    return phrasal_verbs


_PHRASAL_VERBS = None


def get_phrasal_verbs() -> Set[str]:
    """Get the cached set of phrasal verbs."""
    global _PHRASAL_VERBS
    if _PHRASAL_VERBS is None:
        _PHRASAL_VERBS = load_phrasal_verbs()
    return _PHRASAL_VERBS


def is_phrasal_verb(verb_token, prep_token) -> bool:
    """Check if verb + preposition forms a known phrasal verb."""
    combo = f"{verb_token.lemma_.lower()} {prep_token.text.lower()}"
    return combo in get_phrasal_verbs()


def is_copula(token) -> bool:
    """Check if a token is a copula verb."""
    return token.lemma_.lower() in COPULA_VERBS or token.text.lower() in COPULA_VERBS


def crosses_coordination_boundary(token_a, token_b, doc) -> bool:
    """Check if there's a coordinating conjunction between two tokens."""
    start = min(token_a.i, token_b.i)
    end = max(token_a.i, token_b.i)
    for i in range(start + 1, end):
        if doc[i].dep_ in COORDINATION_DEPS:
            return True
    return False
