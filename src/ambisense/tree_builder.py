"""Dependency-to-constituency tree conversion with PP re-attachment."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from spacy.tokens import Span, Token

from ambisense.detector import AmbiguityRecord


@dataclass
class TreeNode:
    """A node in a constituency/phrase-structure tree."""
    label: str
    children: List["TreeNode"] = field(default_factory=list)
    is_leaf: bool = False
    text: str = ""
    is_ambiguous: bool = False

    def to_bracket(self) -> str:
        """Render as bracket notation."""
        if self.is_leaf:
            return f"[{self.label} {self.text}]"
        child_strs = " ".join(c.to_bracket() for c in self.children)
        return f"[{self.label} {child_strs}]"

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict."""
        if self.is_leaf:
            return {"label": self.label, "text": self.text}
        return {
            "label": self.label,
            "children": [c.to_dict() for c in self.children],
        }


def leaf(token: Token) -> TreeNode:
    """Create a leaf node from a spaCy token."""
    # Map POS to a more readable constituency label
    pos_map = {
        "NOUN": "N",
        "PROPN": "N",
        "VERB": "V",
        "ADP": "P",
        "DET": "det",
        "ADJ": "ADJ",
        "ADV": "ADV",
        "NUM": "NUM",
        "PRON": "PRON",
        "AUX": "AUX",
        "PART": "PRT",
        "PUNCT": "PUNCT",
    }
    label = pos_map.get(token.pos_, token.pos_)
    return TreeNode(label=label, text=token.text, is_leaf=True)


def build_np_node(
    head: Token, exclude_pps: Optional[List[Token]] = None
) -> TreeNode:
    """Build an NP node from a noun head and its dependents."""
    if exclude_pps is None:
        exclude_pps = []

    children = []
    # Collect all tokens in the subtree, sorted by position
    subtree_tokens = sorted(head.subtree, key=lambda t: t.i)

    # Filter out excluded PPs and their subtrees
    excluded_indices = set()
    for pp in exclude_pps:
        for t in pp.subtree:
            excluded_indices.add(t.i)

    for tok in subtree_tokens:
        if tok.i in excluded_indices:
            continue
        children.append(leaf(tok))

    if not children:
        children = [leaf(head)]

    return TreeNode(label="NP", children=children)


def build_pp_node(prep: Token, is_ambiguous: bool = False) -> TreeNode:
    """Build a PP node from a preposition token."""
    children = [leaf(prep)]

    for child in prep.children:
        if child.dep_ == "pobj":
            children.append(build_np_node(child))
        else:
            children.append(leaf(child))

    node = TreeNode(label="PP", children=children, is_ambiguous=is_ambiguous)
    return node


def dep_to_constituency(
    sent: Span,
    ambiguous_pps: List[Token],
    variant_assignments: Dict[Token, str],
) -> TreeNode:
    """Convert a dependency parse to a constituency tree skeleton.

    Args:
        sent: The spaCy sentence span.
        ambiguous_pps: List of preposition tokens flagged as ambiguous.
        variant_assignments: Maps each ambiguous PP token to "high" or "low".

    Returns:
        A TreeNode representing the constituency tree.
    """
    root_verb = sent.root

    # If root is not a verb, build a simple flat tree
    if root_verb.pos_ != "VERB":
        children = [leaf(t) for t in sent if not t.is_punct]
        return TreeNode(label="S", children=children)

    # Find subject
    subj = None
    for child in root_verb.children:
        if child.dep_ in ("nsubj", "nsubjpass"):
            subj = child
            break

    subj_np = build_np_node(subj) if subj else None

    # Find direct object
    obj = None
    for child in root_verb.children:
        if child.dep_ in ("dobj", "attr", "oprd"):
            obj = child
            break

    obj_np = build_np_node(obj, exclude_pps=ambiguous_pps) if obj else None

    # Build VP children
    vp_children = []

    # Add auxiliaries and adverbs that precede the verb
    for child in sorted(root_verb.children, key=lambda t: t.i):
        if child.dep_ in ("aux", "auxpass", "neg") and child.i < root_verb.i:
            vp_children.append(leaf(child))
        elif child.dep_ in ("advmod", "npadvmod") and child.i < root_verb.i:
            vp_children.append(TreeNode("ADVP", [leaf(child)]))

    # Add the verb itself
    vp_children.append(TreeNode("V", [leaf(root_verb)]))

    # Add post-verb adverbs
    for child in sorted(root_verb.children, key=lambda t: t.i):
        if child.dep_ in ("advmod", "npadvmod") and child.i > root_verb.i:
            if child.i < (obj.i if obj else float("inf")):
                vp_children.append(TreeNode("ADVP", [leaf(child)]))

    # Add object NP
    if obj_np:
        vp_children.append(obj_np)

    # Place ambiguous PPs
    for pp_tok in sorted(ambiguous_pps, key=lambda t: t.i):
        pp_node = build_pp_node(pp_tok, is_ambiguous=True)
        assignment = variant_assignments.get(pp_tok, "high")
        if assignment == "high":
            vp_children.append(pp_node)
        else:
            if obj_np:
                obj_np.children.append(pp_node)
            else:
                vp_children.append(pp_node)

    # Add non-ambiguous PPs and remaining adverbs
    for child in sorted(root_verb.children, key=lambda t: t.i):
        if child in ambiguous_pps:
            continue
        if child.dep_ == "prep":
            vp_children.append(build_pp_node(child))
        elif child.dep_ in ("advmod", "npadvmod") and child.i > root_verb.i:
            if obj and child.i > obj.i:
                vp_children.append(TreeNode("ADVP", [leaf(child)]))
        elif child.dep_ == "dative":
            vp_children.append(build_np_node(child))

    vp = TreeNode(label="VP", children=vp_children)

    # Assemble S
    s_children = []
    if subj_np:
        s_children.append(subj_np)
    s_children.append(vp)

    return TreeNode(label="S", children=s_children)


def build_tree_pair(
    record: AmbiguityRecord,
    all_ambiguous: Optional[List[AmbiguityRecord]] = None,
) -> tuple:
    """Build high and low attachment trees for a single ambiguous PP.

    Other ambiguous PPs (if any) are held at their parser default.

    Returns:
        (high_tree, low_tree) tuple of TreeNode.
    """
    sent = record.sentence
    prep = record.preposition

    # Collect all ambiguous PP tokens
    if all_ambiguous:
        all_pp_tokens = [r.preposition for r in all_ambiguous]
    else:
        all_pp_tokens = [prep]

    # For high attachment: this PP attaches to verb
    high_assignments = {}
    for pp_tok in all_pp_tokens:
        if pp_tok == prep:
            high_assignments[pp_tok] = "high"
        else:
            # Hold at parser default
            rec = next((r for r in all_ambiguous if r.preposition == pp_tok), None)
            if rec:
                high_assignments[pp_tok] = rec.parser_attachment
            else:
                high_assignments[pp_tok] = "high"

    # For low attachment: this PP attaches to noun
    low_assignments = {}
    for pp_tok in all_pp_tokens:
        if pp_tok == prep:
            low_assignments[pp_tok] = "low"
        else:
            rec = next((r for r in all_ambiguous if r.preposition == pp_tok), None)
            if rec:
                low_assignments[pp_tok] = rec.parser_attachment
            else:
                low_assignments[pp_tok] = "high"

    high_tree = dep_to_constituency(sent, all_pp_tokens, high_assignments)
    low_tree = dep_to_constituency(sent, all_pp_tokens, low_assignments)

    return high_tree, low_tree
