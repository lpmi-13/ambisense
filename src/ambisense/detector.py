"""PP-attachment ambiguity detection engine."""

from dataclasses import dataclass, field
from typing import List, Optional, Set

import spacy
from spacy.tokens import Doc, Span, Token

from ambisense.filters import (
    DEFAULT_WATCHED_PREPOSITIONS,
    crosses_coordination_boundary,
    is_copula,
    is_phrasal_verb,
)


DEFAULT_MAX_DISTANCE = 8


@dataclass
class AmbiguityRecord:
    """A detected PP-attachment ambiguity."""
    sentence: Span
    pp_span: Span
    pp_text: str
    preposition: Token
    parser_head: Token
    alternative_head: Token
    parser_attachment: str  # "high" or "low"
    alternative_attachment: str  # "high" or "low"

    @property
    def verb(self) -> Token:
        if self.parser_head.pos_ == "VERB":
            return self.parser_head
        return self.alternative_head

    @property
    def noun(self) -> Token:
        if self.parser_head.pos_ in ("NOUN", "PROPN"):
            return self.parser_head
        return self.alternative_head

    @property
    def pp_obj_text(self) -> str:
        """Get the text of the prepositional object subtree."""
        for child in self.preposition.children:
            if child.dep_ == "pobj":
                return " ".join(t.text for t in child.subtree)
        return ""

    @property
    def subject_text(self) -> str:
        """Get the subject phrase governing the ambiguous verb, if present."""
        verb = self.verb
        subjects = [
            child for child in verb.children
            if child.dep_ in ("nsubj", "nsubjpass", "expl")
        ]
        if not subjects:
            return ""
        subject = min(subjects, key=lambda token: token.i)
        return " ".join(t.text for t in subject.subtree)

    @property
    def verb_phrase_text(self) -> str:
        """Get the verb plus simple auxiliaries/negation."""
        parts = [
            child for child in self.verb.children
            if child.dep_ in ("aux", "auxpass", "neg")
        ]
        parts.append(self.verb)
        parts.sort(key=lambda token: token.i)
        return " ".join(token.text for token in parts)

    @property
    def np_text(self) -> str:
        """Get the noun phrase text, excluding the ambiguous PP."""
        noun = self.noun
        tokens = []
        for t in noun.subtree:
            if t == self.preposition or any(
                anc == self.preposition for anc in t.ancestors
            ):
                continue
            tokens.append(t.text)
        return " ".join(tokens)

    @property
    def det_text(self) -> str:
        """Get the determiner of the noun phrase, or 'the' as fallback."""
        noun = self.noun
        for child in noun.children:
            if child.dep_ == "det":
                return child.text
        return "the"

    @property
    def np_without_det(self) -> str:
        """Get noun phrase text without the determiner."""
        noun = self.noun
        tokens = []
        for t in noun.subtree:
            if t == self.preposition or any(
                anc == self.preposition for anc in t.ancestors
            ):
                continue
            if t.dep_ == "det" and t.head == noun:
                continue
            tokens.append(t.text)
        return " ".join(tokens)

    @property
    def clause_text(self) -> str:
        """Get a minimal clause covering the subject, verb, and noun phrase."""
        parts = []
        if self.subject_text:
            parts.append(self.subject_text)
        if self.verb_phrase_text:
            parts.append(self.verb_phrase_text)
        if self.np_text:
            parts.append(self.np_text)
        return " ".join(part for part in parts if part)


def get_pp_span(prep_token: Token) -> Span:
    """Get the span covering the entire PP (preposition + its subtree)."""
    subtree_indices = [t.i for t in prep_token.subtree]
    start = min(subtree_indices)
    end = max(subtree_indices) + 1
    return prep_token.doc[start:end]


def find_alternative_head(
    prep_token: Token,
    current_head: Token,
    doc: Doc,
    max_distance: int = DEFAULT_MAX_DISTANCE,
) -> Optional[Token]:
    """Find an alternative plausible attachment head for a PP."""
    if current_head.pos_ == "VERB":
        # Parser attached PP to verb → look for a noun object between
        # the verb and the PP that could plausibly own the PP.
        candidates = [
            tok
            for tok in current_head.children
            if tok.dep_ in ("dobj", "attr", "nsubjpass", "oprd")
            and tok.i < prep_token.i
            and tok.pos_ in ("NOUN", "PROPN")
        ]
        if candidates:
            best = max(candidates, key=lambda t: t.i)
            if abs(best.i - prep_token.i) <= max_distance:
                return best

    elif current_head.pos_ in ("NOUN", "PROPN"):
        # Parser attached PP to noun → look for a governing verb
        ancestor = current_head.head
        visited = {current_head.i}
        while ancestor.i not in visited:
            visited.add(ancestor.i)
            if ancestor.pos_ == "VERB":
                if abs(ancestor.i - prep_token.i) <= max_distance:
                    return ancestor
                break
            if ancestor == ancestor.head:
                break
            ancestor = ancestor.head

    return None


def detect_ambiguities(
    doc: Doc,
    watched_prepositions: Optional[Set[str]] = None,
    include_of: bool = False,
    include_copula: bool = False,
    max_distance: int = DEFAULT_MAX_DISTANCE,
) -> List[AmbiguityRecord]:
    """Detect PP-attachment ambiguities in a parsed spaCy Doc."""
    if watched_prepositions is None:
        watched_prepositions = set(DEFAULT_WATCHED_PREPOSITIONS)

    if include_of:
        watched_prepositions = watched_prepositions | {"of"}

    results = []

    for token in doc:
        if token.dep_ != "prep":
            continue

        prep_text = token.text.lower()
        if prep_text not in watched_prepositions:
            continue

        head = token.head

        # Copula filter
        if not include_copula and head.pos_ == "VERB" and is_copula(head):
            continue

        # Phrasal verb filter
        if head.pos_ == "VERB" and is_phrasal_verb(head, token):
            continue

        alt_head = find_alternative_head(token, head, doc, max_distance)
        if alt_head is None:
            continue

        # Coordination boundary filter
        if crosses_coordination_boundary(head, alt_head, doc):
            continue

        # Also check phrasal verb with the alternative head if it's a verb
        if alt_head.pos_ == "VERB" and is_phrasal_verb(alt_head, token):
            continue

        pp_span = get_pp_span(token)

        if head.pos_ == "VERB":
            parser_attachment = "high"
            alternative_attachment = "low"
        else:
            parser_attachment = "low"
            alternative_attachment = "high"

        results.append(
            AmbiguityRecord(
                sentence=token.sent,
                pp_span=pp_span,
                pp_text=pp_span.text,
                preposition=token,
                parser_head=head,
                alternative_head=alt_head,
                parser_attachment=parser_attachment,
                alternative_attachment=alternative_attachment,
            )
        )

    return results


_nlp_cache = {}


def load_model(model_name: str = "en_core_web_sm"):
    """Load and cache a spaCy model."""
    if model_name not in _nlp_cache:
        _nlp_cache[model_name] = spacy.load(model_name)
    return _nlp_cache[model_name]


def analyze_text(
    text: str,
    model_name: str = "en_core_web_sm",
    watched_prepositions: Optional[Set[str]] = None,
    include_of: bool = False,
    include_copula: bool = False,
    max_distance: int = DEFAULT_MAX_DISTANCE,
) -> List[AmbiguityRecord]:
    """Analyze text for PP-attachment ambiguities."""
    nlp = load_model(model_name)
    doc = nlp(text)
    return detect_ambiguities(
        doc,
        watched_prepositions=watched_prepositions,
        include_of=include_of,
        include_copula=include_copula,
        max_distance=max_distance,
    )
