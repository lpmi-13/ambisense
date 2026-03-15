"""Template-based paraphrase generator for PP-attachment ambiguities."""

import json
from pathlib import Path
from typing import Dict, Tuple

from ambisense.detector import AmbiguityRecord


def load_templates() -> Dict[str, Dict[str, str]]:
    """Load paraphrase templates from the data file."""
    data_path = Path(__file__).parent / "data" / "templates.json"
    with open(data_path) as f:
        return json.load(f)


_TEMPLATES = None


def get_templates() -> Dict[str, Dict[str, str]]:
    """Get the cached templates."""
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = load_templates()
    return _TEMPLATES


def generate_paraphrases(record: AmbiguityRecord) -> Tuple[str, str]:
    """Generate high and low attachment paraphrases for an ambiguity.

    Returns (high_paraphrase, low_paraphrase).
    """
    templates = get_templates()
    prep = record.preposition.text.lower()

    if prep in templates:
        high_template = templates[prep]["high"]
        low_template = templates[prep]["low"]
    else:
        high_template = templates["_default"]["high"]
        low_template = templates["_default"]["low"]

    verb_text = record.verb.text
    np_text = record.np_without_det
    det_text = record.det_text
    pp_obj = record.pp_obj_text
    prep_text = record.preposition.text

    variables = {
        "verb": verb_text,
        "np": np_text,
        "det": det_text,
        "pp_obj": pp_obj,
        "prep": prep_text,
        "pp": record.pp_text,
    }

    try:
        high = high_template.format(**variables)
    except KeyError:
        high = f"{record.pp_text} {verb_text} {det_text} {np_text}"

    try:
        low = low_template.format(**variables)
    except KeyError:
        low = f"{verb_text} {det_text} {np_text} {prep_text} {pp_obj}"

    return high, low
