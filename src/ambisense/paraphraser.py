"""Offline reading and rewrite generation for PP-attachment ambiguities."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

from ambisense.detector import AmbiguityRecord
from ambisense.rewrite_knowledge import augment_term_classes, semantic_role_for


DATA_DIR = Path(__file__).parent / "data"
WHITESPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^\w\s-]")


@dataclass(frozen=True)
class SuggestionSet:
    """Possible readings plus author-facing rewrite suggestions."""

    reading_high: str
    reading_low: str
    rewrite_high: str
    rewrite_low: str
    high_rule_id: Optional[str] = None
    low_rule_id: Optional[str] = None


@dataclass(frozen=True)
class RewriteContext:
    """Normalized lexical and semantic context for rule matching."""

    prep: str
    semantic_role: str
    verb_lemma: str
    verb_text: str
    noun_head: str
    noun_phrase: str
    object_head: str
    object_phrase: str
    noun_classes: Set[str]
    object_classes: Set[str]


def _load_json(name: str):
    """Load a JSON data file from the package data directory."""
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_templates() -> Dict[str, Dict[str, str]]:
    """Load generic reading templates."""
    return _load_json("templates.json")


def load_rewrite_roles() -> Dict[str, Dict[str, str]]:
    """Load preposition-to-semantic-role defaults."""
    return _load_json("rewrite_roles.json")


def load_domain_lexicon() -> Dict[str, Dict[str, List[str]]]:
    """Load local technical term classes."""
    return _load_json("domain_lexicon.json")


def load_preferred_terms() -> Dict[str, str]:
    """Load preferred offline term substitutions."""
    return _load_json("preferred_terms.json")["substitutions"]


def load_rewrite_rules() -> List[Dict[str, object]]:
    """Load scored technical rewrite rules."""
    return _load_json("rewrite_rules.json")["rules"]


_TEMPLATES = None
_REWRITE_ROLES = None
_DOMAIN_LEXICON = None
_PREFERRED_TERMS = None
_REWRITE_RULES = None


def get_templates() -> Dict[str, Dict[str, str]]:
    """Get cached generic reading templates."""
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = load_templates()
    return _TEMPLATES


def get_rewrite_roles() -> Dict[str, Dict[str, str]]:
    """Get cached semantic-role defaults."""
    global _REWRITE_ROLES
    if _REWRITE_ROLES is None:
        _REWRITE_ROLES = load_rewrite_roles()
    return _REWRITE_ROLES


def get_domain_lexicon() -> Dict[str, Dict[str, List[str]]]:
    """Get cached technical term classes."""
    global _DOMAIN_LEXICON
    if _DOMAIN_LEXICON is None:
        _DOMAIN_LEXICON = load_domain_lexicon()
    return _DOMAIN_LEXICON


def get_preferred_terms() -> Dict[str, str]:
    """Get cached preferred term substitutions."""
    global _PREFERRED_TERMS
    if _PREFERRED_TERMS is None:
        _PREFERRED_TERMS = load_preferred_terms()
    return _PREFERRED_TERMS


def get_rewrite_rules() -> List[Dict[str, object]]:
    """Get cached technical rewrite rules."""
    global _REWRITE_RULES
    if _REWRITE_RULES is None:
        _REWRITE_RULES = load_rewrite_rules()
    return _REWRITE_RULES


def _normalize(text: str) -> str:
    """Normalize free text for lexicon lookups."""
    cleaned = NON_WORD_RE.sub(" ", text.lower())
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def _apply_preferred_terms(text: str) -> str:
    """Rewrite known technical aliases to preferred terms."""
    updated = text
    for source, target in get_preferred_terms().items():
        pattern = rf"\b{re.escape(source)}\b"
        updated = re.sub(pattern, target, updated, flags=re.IGNORECASE)
    return updated


def _capitalize_first(text: str) -> str:
    """Uppercase the first non-space character."""
    if not text:
        return text
    return text[:1].upper() + text[1:]


def _render_template(template: str, variables: Dict[str, str]) -> str:
    """Render a template and normalize technical terminology."""
    return _apply_preferred_terms(template.format(**variables)).strip()


def _pobj_token(record: AmbiguityRecord):
    """Return the token headed by the ambiguous preposition, if present."""
    for child in record.preposition.children:
        if child.dep_ == "pobj":
            return child
    return None


def _collect_term_candidates(head_text: str, phrase_text: str) -> Set[str]:
    """Build exact and token-level lookup candidates for lexicon matches."""
    candidates = set()
    for text in (head_text, phrase_text):
        normalized = _normalize(text)
        if normalized:
            candidates.add(normalized)
            candidates.update(part for part in normalized.split() if part)
    return candidates


def _classify_terms(candidates: Set[str]) -> Set[str]:
    """Map normalized terms to configured classes."""
    classes = set()
    terms = get_domain_lexicon()["terms"]
    for candidate in candidates:
        classes.update(terms.get(candidate, []))
    classes.update(augment_term_classes(candidates))
    return classes


def _build_variables(record: AmbiguityRecord) -> Dict[str, str]:
    """Create template variables for readings and rewrites."""
    verb_text = _apply_preferred_terms(record.verb.text)
    np_text = _apply_preferred_terms(record.np_without_det)
    det_text = _apply_preferred_terms(record.det_text)
    pp_obj = _apply_preferred_terms(record.pp_obj_text)
    prep_text = _apply_preferred_terms(record.preposition.text)
    clause = _apply_preferred_terms(record.clause_text)
    subject = _apply_preferred_terms(record.subject_text)
    verb_phrase = _apply_preferred_terms(record.verb_phrase_text)

    if subject:
        embedded_clause = clause
    elif clause:
        embedded_clause = clause[:1].lower() + clause[1:]
    else:
        embedded_clause = clause

    det_np = " ".join(part for part in (det_text, np_text) if part)

    return {
        "verb": verb_text,
        "verb_cap": _capitalize_first(verb_text),
        "np": np_text,
        "np_cap": _capitalize_first(np_text),
        "det": det_text,
        "det_np": det_np,
        "det_np_cap": _capitalize_first(det_np),
        "pp_obj": pp_obj,
        "pp_obj_cap": _capitalize_first(pp_obj),
        "prep": prep_text,
        "pp": _apply_preferred_terms(record.pp_text),
        "subject": subject,
        "subject_cap": _capitalize_first(subject),
        "verb_phrase": verb_phrase,
        "verb_phrase_cap": _capitalize_first(verb_phrase),
        "clause": clause,
        "clause_cap": _capitalize_first(clause),
        "embedded_clause": embedded_clause,
        "embedded_clause_cap": _capitalize_first(embedded_clause),
    }


def _build_context(record: AmbiguityRecord) -> RewriteContext:
    """Build normalized rule-matching context for an ambiguity."""
    prep = record.preposition.text.lower()
    roles = get_rewrite_roles()
    default_role = roles.get(prep, {}).get("default", "generic")
    semantic_role = semantic_role_for(record.verb.lemma_.lower(), prep, default_role)
    pobj = _pobj_token(record)
    object_head = pobj.lemma_.lower() if pobj is not None else _normalize(record.pp_obj_text)
    noun_head = record.noun.lemma_.lower()
    noun_phrase = record.np_without_det
    object_phrase = record.pp_obj_text

    noun_candidates = _collect_term_candidates(noun_head, noun_phrase)
    object_candidates = _collect_term_candidates(object_head, object_phrase)

    return RewriteContext(
        prep=prep,
        semantic_role=semantic_role,
        verb_lemma=record.verb.lemma_.lower(),
        verb_text=record.verb.text.lower(),
        noun_head=noun_head,
        noun_phrase=_normalize(noun_phrase),
        object_head=object_head,
        object_phrase=_normalize(object_phrase),
        noun_classes=_classify_terms(noun_candidates),
        object_classes=_classify_terms(object_candidates),
    )


def _matches_any(expected: List[str], actual: Set[str]) -> bool:
    """Return whether any configured value appears in the actual set."""
    return bool(set(expected) & actual)


def _rule_matches(rule: Dict[str, object], context: RewriteContext) -> bool:
    """Check whether a rewrite rule applies to the current context."""
    if rule.get("prep") and rule["prep"] != context.prep:
        return False

    when = rule.get("when", {})
    if not isinstance(when, dict):
        return False

    verb_lemmas = when.get("verb_lemmas", [])
    if verb_lemmas and context.verb_lemma not in verb_lemmas:
        return False

    noun_terms = when.get("noun_terms", [])
    if noun_terms and context.noun_head not in noun_terms and context.noun_phrase not in noun_terms:
        return False

    object_terms = when.get("object_terms", [])
    if object_terms and context.object_head not in object_terms and context.object_phrase not in object_terms:
        return False

    noun_classes = when.get("noun_classes", [])
    if noun_classes and not _matches_any(noun_classes, context.noun_classes):
        return False

    object_classes = when.get("object_classes", [])
    if object_classes and not _matches_any(object_classes, context.object_classes):
        return False

    semantic_roles = when.get("semantic_roles", [])
    if semantic_roles and context.semantic_role not in semantic_roles:
        return False

    return True


def _select_rule(side: str, context: RewriteContext) -> Optional[Dict[str, object]]:
    """Return the highest-scoring rewrite rule for one attachment side."""
    best_rule = None
    best_score = -1
    for rule in get_rewrite_rules():
        rewrites = rule.get("rewrites", {})
        if side not in rewrites:
            continue
        if not _rule_matches(rule, context):
            continue
        score = int(rule.get("score", 0))
        if score > best_score:
            best_score = score
            best_rule = rule
    return best_rule


def _generate_generic_readings(record: AmbiguityRecord) -> Tuple[str, str]:
    """Generate neutral disambiguating readings from the base templates."""
    templates = get_templates()
    prep = record.preposition.text.lower()

    if prep in templates:
        high_template = templates[prep]["high"]
        low_template = templates[prep]["low"]
    else:
        high_template = templates["_default"]["high"]
        low_template = templates["_default"]["low"]

    variables = _build_variables(record)

    try:
        high = _render_template(high_template, variables)
    except KeyError:
        high = f"{variables['pp']}, {variables['embedded_clause']}"

    try:
        low = _render_template(low_template, variables)
    except KeyError:
        low = f"{variables['clause']} {variables['prep']} {variables['pp_obj']}"

    return high, low


def generate_suggestions(record: AmbiguityRecord) -> SuggestionSet:
    """Generate generic readings plus technically tuned rewrite suggestions."""
    reading_high, reading_low = _generate_generic_readings(record)
    rewrite_high = reading_high
    rewrite_low = reading_low
    high_rule_id = None
    low_rule_id = None

    context = _build_context(record)
    variables = _build_variables(record)

    high_rule = _select_rule("high", context)
    if high_rule is not None:
        rewrite_high = _render_template(high_rule["rewrites"]["high"], variables)
        high_rule_id = str(high_rule["id"])

    low_rule = _select_rule("low", context)
    if low_rule is not None:
        rewrite_low = _render_template(low_rule["rewrites"]["low"], variables)
        low_rule_id = str(low_rule["id"])

    return SuggestionSet(
        reading_high=reading_high,
        reading_low=reading_low,
        rewrite_high=rewrite_high,
        rewrite_low=rewrite_low,
        high_rule_id=high_rule_id,
        low_rule_id=low_rule_id,
    )


def generate_paraphrases(record: AmbiguityRecord) -> Tuple[str, str]:
    """Generate neutral high/low readings for an ambiguity."""
    suggestions = generate_suggestions(record)
    return suggestions.reading_high, suggestions.reading_low


def generate_rewrites(record: AmbiguityRecord) -> Tuple[str, str]:
    """Generate author-facing rewrite suggestions for an ambiguity."""
    suggestions = generate_suggestions(record)
    return suggestions.rewrite_high, suggestions.rewrite_low
