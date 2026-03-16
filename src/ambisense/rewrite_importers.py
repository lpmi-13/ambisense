"""Import offline lexical resources into generated rewrite-knowledge files."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
import csv
import json
from pathlib import Path
import re
from typing import DefaultDict, Dict, Iterable, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

from ambisense.rewrite_knowledge import SCHEMA_VERSION


SUPPORTED_PREPOSITIONS = {
    "about", "at", "by", "for", "from", "in", "of", "on", "through", "to", "with",
}

ROLE_ALIASES = {
    "beneficiary": "beneficiary",
    "benefactive": "beneficiary",
    "destination": "destination",
    "dir": "destination",
    "goal": "destination",
    "instrument": "instrument",
    "loc": "location",
    "local": "location",
    "locale": "location",
    "location": "location",
    "locative": "location",
    "means": "means",
    "message": "topic",
    "path": "path",
    "recipient": "destination",
    "source": "source",
    "theme_topic": "topic",
    "topic": "topic",
}

PREP_ROLE_PREFERENCE = {
    "about": ["topic"],
    "at": ["location"],
    "by": ["means", "instrument"],
    "for": ["beneficiary", "destination"],
    "from": ["source"],
    "in": ["location"],
    "of": ["topic"],
    "on": ["location"],
    "through": ["path", "location", "means"],
    "to": ["destination", "beneficiary"],
    "with": ["instrument", "means"],
}

WORDNET_CLASS_ANCHORS = {
    "artifact": {"artifact", "software", "computer_program", "file", "document"},
    "artifact_store": {"repository", "storehouse", "depository", "storage"},
    "audience": {"person", "people", "organization", "group"},
    "cluster": {"cluster", "group", "collection"},
    "diagnostic": {"error", "message", "warning", "condition"},
    "host": {"computer", "computer_system", "machine", "server", "device"},
    "instrument": {"instrumentality", "instrument", "tool", "device", "implement"},
    "log": {"record", "register", "written_account", "message", "file"},
    "runtime_workload": {"software", "computer_program", "service", "process", "program"},
    "ui_artifact": {"display", "report", "view", "panel", "interface"},
}


def _local_name(tag: str) -> str:
    """Strip XML namespaces from a tag."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _normalized(text: str) -> str:
    """Normalize a resource label to a lookup-friendly string."""
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", text.strip().lower())).strip()


def _tokenized_prepositions(value: str) -> List[str]:
    """Extract normalized preposition tokens from an XML attribute value."""
    tokens = re.findall(r"[A-Za-z]+", value.lower())
    return [token for token in tokens if token in SUPPORTED_PREPOSITIONS]


def _iter_xml_files(source: Path) -> Iterable[Path]:
    """Yield XML files from a file or directory input."""
    if source.is_file():
        yield source
        return
    for path in sorted(source.rglob("*.xml")):
        yield path


def _iter_json_files(source: Path) -> Iterable[Path]:
    """Yield JSON files from a file or directory input."""
    if source.is_file():
        yield source
        return
    for path in sorted(source.rglob("*.json")):
        yield path


def _role_candidates_from_attrs(element: ET.Element) -> Set[str]:
    """Collect coarse role candidates from an XML element's attributes."""
    candidates = set()
    for key, value in element.attrib.items():
        key_lower = key.lower().replace("-", "").replace("_", "")
        if "role" not in key_lower and "theta" not in key_lower and key_lower not in {"type", "value"}:
            continue
        normalized = _normalized(value)
        if normalized in ROLE_ALIASES:
            candidates.add(ROLE_ALIASES[normalized])
    return candidates


def _preferred_role(prep: str, candidates: Set[str]) -> Optional[str]:
    """Choose the best coarse role for a given preposition."""
    preference = PREP_ROLE_PREFERENCE.get(prep, [])
    for role in preference:
        if role in candidates:
            return role
    return sorted(candidates)[0] if candidates else None


def _find_children(parent: ET.Element, name: str) -> List[ET.Element]:
    """Find direct child elements by local tag name."""
    return [child for child in list(parent) if _local_name(child.tag) == name]


def _iter_descendants(parent: ET.Element, name: str) -> Iterable[ET.Element]:
    """Yield descendant elements by local tag name."""
    for element in parent.iter():
        if _local_name(element.tag) == name:
            yield element


def import_verbnet(source: Path) -> dict:
    """Import VerbNet XML into the generated semantic-role override schema."""
    counts: DefaultDict[str, DefaultDict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    def process_class(class_element: ET.Element) -> None:
        members = []
        for members_node in _find_children(class_element, "MEMBERS"):
            for member in _find_children(members_node, "MEMBER"):
                name = member.attrib.get("name", "")
                if name:
                    members.append(_normalized(name))

        class_roles = set()
        for roles_node in _find_children(class_element, "THEMROLES"):
            for role in _find_children(roles_node, "THEMROLE"):
                role_type = role.attrib.get("type", "")
                normalized = _normalized(role_type)
                if normalized in ROLE_ALIASES:
                    class_roles.add(ROLE_ALIASES[normalized])

        for frames_node in _find_children(class_element, "FRAMES"):
            for frame in _find_children(frames_node, "FRAME"):
                preps: Set[str] = set()
                for syntax in _find_children(frame, "SYNTAX"):
                    for syntax_node in syntax.iter():
                        if _local_name(syntax_node.tag) != "PREP":
                            continue
                        for attr_value in syntax_node.attrib.values():
                            preps.update(_tokenized_prepositions(attr_value))

                if not preps:
                    continue

                frame_roles = set(class_roles)
                for pred in _iter_descendants(frame, "PRED"):
                    frame_roles.update(_role_candidates_from_attrs(pred))
                for arg in _iter_descendants(frame, "ARG"):
                    frame_roles.update(_role_candidates_from_attrs(arg))

                for prep in preps:
                    role = _preferred_role(prep, frame_roles)
                    if role is None:
                        continue
                    for member in members:
                        counts[member][prep][role] += 1

        for subclasses_node in _find_children(class_element, "SUBCLASSES"):
            for subclass in _find_children(subclasses_node, "VNSUBCLASS"):
                process_class(subclass)

    for xml_path in _iter_xml_files(source):
        root = ET.parse(xml_path).getroot()
        if _local_name(root.tag) not in {"VNCLASS", "VNSUBCLASS"}:
            continue
        process_class(root)

    roles = {}
    for lemma, prep_counts in counts.items():
        roles[lemma] = {}
        for prep, role_counts in prep_counts.items():
            roles[lemma][prep] = role_counts.most_common(1)[0][0]

    return {
        "schema_version": SCHEMA_VERSION,
        "resource": "verbnet",
        "roles": roles,
    }


def import_framenet(source: Path) -> dict:
    """Import FrameNet XML into the generated frame-annotation schema."""
    frames: DefaultDict[str, Dict[str, Set[str]]] = defaultdict(lambda: {
        "frames": set(),
        "frame_elements": set(),
    })

    for xml_path in _iter_xml_files(source):
        root = ET.parse(xml_path).getroot()
        root_name = _local_name(root.tag)
        frame_name = root.attrib.get("name") or root.attrib.get("frame")

        if root_name == "frame":
            frame_elements = {
                fe.attrib.get("name", "")
                for fe in _iter_descendants(root, "FE")
                if fe.attrib.get("name")
            }
            for lex_unit in _iter_descendants(root, "lexUnit"):
                name = lex_unit.attrib.get("name", "")
                if not name:
                    continue
                lemma = _normalized(name.split(".", 1)[0])
                frames[lemma]["frames"].add(frame_name or "")
                frames[lemma]["frame_elements"].update(_normalized(fe) for fe in frame_elements if fe)

        elif root_name == "lexUnit":
            name = root.attrib.get("name", "")
            if not name:
                continue
            lemma = _normalized(name.split(".", 1)[0])
            frames[lemma]["frames"].add(frame_name or "")

    normalized = {}
    for lemma, entry in frames.items():
        normalized[lemma] = {
            "frames": sorted(frame for frame in entry["frames"] if frame),
            "frame_elements": sorted(entry["frame_elements"]),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "resource": "framenet",
        "frames": normalized,
    }


def import_semlink(source: Path) -> dict:
    """Import SemLink XML or SemLink 2 JSON mappings into the generated schema."""
    role_aliases: Dict[str, str] = {}
    frame_mappings: DefaultDict[str, Set[str]] = defaultdict(set)

    def maybe_alias(role: str) -> None:
        normalized = _normalized(role)
        coarse = ROLE_ALIASES.get(normalized)
        if coarse is not None:
            role_aliases[normalized] = coarse

    json_paths = list(_iter_json_files(source))
    json_names = {path.name for path in json_paths}

    if {"pb-vn2.json", "vn-fn2.json"} & json_names:
        for json_path in json_paths:
            with open(json_path, encoding="utf-8") as fh:
                payload = json.load(fh)

            if json_path.name == "vn-fn2.json" and isinstance(payload, dict):
                for vn_class, frames in payload.items():
                    if not isinstance(frames, list):
                        continue
                    for frame in frames:
                        if isinstance(frame, str) and frame:
                            frame_mappings[vn_class].add(frame)

            elif json_path.name == "pb-vn2.json" and isinstance(payload, dict):
                for role_set_mapping in payload.values():
                    if not isinstance(role_set_mapping, dict):
                        continue
                    for vn_mapping in role_set_mapping.values():
                        if not isinstance(vn_mapping, dict):
                            continue
                        for role_name in vn_mapping.values():
                            if isinstance(role_name, str):
                                maybe_alias(role_name)
    else:
        for xml_path in _iter_xml_files(source):
            root = ET.parse(xml_path).getroot()
            for element in root.iter():
                attrs = {key.lower().replace("-", "").replace("_", ""): value for key, value in element.attrib.items()}

                for key, value in attrs.items():
                    if "role" in key or "theta" in key or key in {"fe", "frameelement"}:
                        maybe_alias(value)

                vn_class = attrs.get("vncls") or attrs.get("vnclass")
                fn_frame = attrs.get("fnframe")
                if vn_class and fn_frame:
                    frame_mappings[vn_class].add(fn_frame)

    return {
        "schema_version": SCHEMA_VERSION,
        "resource": "semlink",
        "role_aliases": dict(sorted(role_aliases.items())),
        "frame_mappings": {key: sorted(values) for key, values in sorted(frame_mappings.items())},
    }


def _load_seed_terms(seed_terms_path: Optional[Path]) -> Set[str]:
    """Load optional seed terms for WordNet classification."""
    if seed_terms_path is None:
        from ambisense.paraphraser import load_domain_lexicon

        return set(load_domain_lexicon()["terms"])

    seeds = set()
    with open(seed_terms_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                seeds.add(_normalized(line))
    return seeds


def _resolve_wordnet_source(source: Path) -> Path:
    """Resolve a WordNet input path to the directory that contains noun data files."""
    candidates = [source]
    if source.is_dir():
        candidates.append(source / "dict")
        for child in sorted(source.iterdir()):
            if child.is_dir():
                candidates.append(child)
                candidates.append(child / "dict")

    for candidate in candidates:
        if (candidate / "synsets.txt").exists() and (candidate / "hypernyms.txt").exists():
            return candidate
        if (candidate / "data.noun").exists():
            return candidate

    return source


def _parse_wordnet_csv(source: Path) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Parse simplified synsets/hypernyms CSV files."""
    synsets_path = source / "synsets.txt"
    hypernyms_path = source / "hypernyms.txt"

    synsets: Dict[str, List[str]] = {}
    parents: Dict[str, List[str]] = defaultdict(list)

    with open(synsets_path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 2:
                continue
            synset_id = row[0]
            lemmas = [_normalized(part) for part in row[1].split() if part]
            synsets[synset_id] = lemmas

    with open(hypernyms_path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 2:
                continue
            parents[row[0]] = row[1:]

    return synsets, parents


def _parse_wordnet_wndb(source: Path) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Parse official WordNet `data.noun` files."""
    data_path = source / "data.noun"
    synsets: Dict[str, List[str]] = {}
    parents: Dict[str, List[str]] = defaultdict(list)

    with open(data_path, encoding="utf-8") as fh:
        for line in fh:
            if not line or line.startswith("  "):
                continue
            fields = line.split("|", 1)[0].strip().split()
            if len(fields) < 4:
                continue
            offset = fields[0]
            word_count = int(fields[3], 16)
            cursor = 4
            lemmas = []
            for _ in range(word_count):
                lemmas.append(_normalized(fields[cursor]))
                cursor += 2
            synsets[offset] = lemmas

            pointer_count = int(fields[cursor])
            cursor += 1
            for _ in range(pointer_count):
                ptr_symbol = fields[cursor]
                target_offset = fields[cursor + 1]
                cursor += 4
                if ptr_symbol in {"@", "@i"}:
                    parents[offset].append(target_offset)

    return synsets, parents


def _wordnet_ancestors(
    synset_id: str,
    parents: Dict[str, List[str]],
    synsets: Dict[str, List[str]],
) -> Set[str]:
    """Collect ancestor lemmas for one synset."""
    seen = set()
    lemmas = set()
    queue = deque([synset_id])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        lemmas.update(synsets.get(current, []))
        queue.extend(parents.get(current, []))
    return lemmas


def import_wordnet(source: Path, seed_terms_path: Optional[Path] = None) -> dict:
    """Import WordNet noun data into the generated term-class schema."""
    resolved_source = _resolve_wordnet_source(source)
    if (resolved_source / "synsets.txt").exists() and (resolved_source / "hypernyms.txt").exists():
        synsets, parents = _parse_wordnet_csv(resolved_source)
    elif (resolved_source / "data.noun").exists():
        synsets, parents = _parse_wordnet_wndb(resolved_source)
    else:
        raise FileNotFoundError(
            "Expected either synsets.txt/hypernyms.txt or data.noun under the WordNet source path."
        )

    lemma_to_synsets: DefaultDict[str, Set[str]] = defaultdict(set)
    for synset_id, lemmas in synsets.items():
        for lemma in lemmas:
            lemma_to_synsets[lemma].add(synset_id)

    term_classes: Dict[str, List[str]] = {}
    for term in sorted(_load_seed_terms(seed_terms_path)):
        variants = {term, term.replace(" ", "_")}
        matching_synsets = set()
        for variant in variants:
            matching_synsets.update(lemma_to_synsets.get(_normalized(variant), set()))
        if not matching_synsets:
            continue

        ancestor_lemmas = set()
        for synset_id in matching_synsets:
            ancestor_lemmas.update(_wordnet_ancestors(synset_id, parents, synsets))

        classes = []
        for class_name, anchors in WORDNET_CLASS_ANCHORS.items():
            normalized_anchors = {_normalized(anchor) for anchor in anchors}
            if normalized_anchors & ancestor_lemmas:
                classes.append(class_name)

        if classes:
            term_classes[term] = sorted(set(classes))

    return {
        "schema_version": SCHEMA_VERSION,
        "resource": "wordnet",
        "term_classes": term_classes,
    }


def write_generated_resource(payload: dict, destination: Path) -> None:
    """Write a generated resource payload as pretty JSON."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
