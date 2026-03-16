"""Tests for offline resource importer helpers."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from ambisense.rewrite_importers import (
    import_framenet,
    import_semlink,
    import_verbnet,
    import_wordnet,
    write_generated_resource,
)


ROOT = Path(__file__).resolve().parents[1]
IMPORT_SCRIPT = ROOT / "tools" / "import_offline_resources.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_import_verbnet_extracts_preposition_roles(tmp_path):
    source = tmp_path / "verbnet"
    _write(
        source / "deploy.xml",
        """
        <VNCLASS ID="deploy-1">
          <MEMBERS>
            <MEMBER name="deploy" />
          </MEMBERS>
          <THEMROLES>
            <THEMROLE type="Location" />
          </THEMROLES>
          <FRAMES>
            <FRAME>
              <SYNTAX>
                <VERB value="deploy" />
                <PREP value="on" />
              </SYNTAX>
            </FRAME>
          </FRAMES>
        </VNCLASS>
        """,
    )

    payload = import_verbnet(source)

    assert payload["roles"]["deploy"]["on"] == "location"


def test_import_framenet_extracts_frames_and_elements(tmp_path):
    source = tmp_path / "framenet"
    _write(
        source / "placing.xml",
        """
        <frame name="Placing">
          <FE name="Goal" />
          <FE name="Theme" />
          <lexUnit name="deploy.v" />
        </frame>
        """,
    )

    payload = import_framenet(source)

    assert payload["frames"]["deploy"]["frames"] == ["Placing"]
    assert payload["frames"]["deploy"]["frame_elements"] == ["goal", "theme"]


def test_import_semlink_extracts_role_aliases_and_frame_mappings(tmp_path):
    source = tmp_path / "semlink"
    _write(
        source / "map.xml",
        """
        <mappings>
          <predicate vncls="put-9.1" fnframe="Placing" vnrole="Goal" fnrole="Goal" />
        </mappings>
        """,
    )

    payload = import_semlink(source)

    assert payload["role_aliases"]["goal"] == "destination"
    assert payload["frame_mappings"]["put-9.1"] == ["Placing"]


def test_import_semlink_json_extracts_frame_mappings_and_role_aliases(tmp_path):
    source = tmp_path / "semlink"
    _write(
        source / "instances" / "vn-fn2.json",
        """
        {
          "26.5-shake": ["Moving_in_place", "Body_movement"]
        }
        """,
    )
    _write(
        source / "instances" / "pb-vn2.json",
        """
        {
          "shake.01": {
            "26.5": {
              "ARG0": "agent",
              "ARG1": "source",
              "ARG2": "goal"
            }
          }
        }
        """,
    )

    payload = import_semlink(source)

    assert payload["frame_mappings"]["26.5-shake"] == ["Body_movement", "Moving_in_place"]
    assert payload["role_aliases"]["source"] == "source"
    assert payload["role_aliases"]["goal"] == "destination"


def test_import_wordnet_classifies_seed_terms_from_simplified_exports(tmp_path):
    source = tmp_path / "wordnet"
    _write(
        source / "synsets.txt",
        """
        100,repository
        200,storage depository
        300,server
        400,computer_system machine
        """,
    )
    _write(
        source / "hypernyms.txt",
        """
        100,200
        300,400
        """,
    )
    seeds = tmp_path / "seed_terms.txt"
    _write(
        seeds,
        """
        repository
        server
        """,
    )

    payload = import_wordnet(source, seed_terms_path=seeds)

    assert payload["term_classes"]["repository"] == ["artifact_store"]
    assert payload["term_classes"]["server"] == ["host"]


def test_import_wordnet_supports_official_dict_layout(tmp_path):
    source = tmp_path / "WordNet-3.0" / "dict"
    _write(
        source / "data.noun",
        """
        00001740 03 n 01 server 0 001 @ 00002098 n 0000 | a server
        00002098 03 n 02 computer_system 0 machine 0 000 | a machine
        """,
    )
    seeds = tmp_path / "seed_terms.txt"
    _write(seeds, "server")

    payload = import_wordnet(tmp_path / "WordNet-3.0", seed_terms_path=seeds)

    assert payload["term_classes"]["server"] == ["host"]


def test_write_generated_resource_emits_pretty_json(tmp_path):
    destination = tmp_path / "generated" / "verbnet_index.json"
    payload = {"schema_version": 1, "resource": "verbnet", "roles": {"deploy": {"on": "location"}}}

    write_generated_resource(payload, destination)

    written = destination.read_text(encoding="utf-8")
    assert written.endswith("\n")
    assert json.loads(written) == payload


def test_import_cli_writes_generated_resources_and_compiles_overlay(tmp_path):
    verbnet = tmp_path / "verbnet"
    framenet = tmp_path / "framenet"
    semlink = tmp_path / "semlink"
    wordnet = tmp_path / "wordnet"
    generated = tmp_path / "generated"
    seeds = tmp_path / "seed_terms.txt"

    _write(
        verbnet / "deploy.xml",
        """
        <VNCLASS ID="deploy-1">
          <MEMBERS>
            <MEMBER name="deploy" />
          </MEMBERS>
          <THEMROLES>
            <THEMROLE type="Location" />
          </THEMROLES>
          <FRAMES>
            <FRAME>
              <SYNTAX>
                <PREP value="on" />
              </SYNTAX>
            </FRAME>
          </FRAMES>
        </VNCLASS>
        """,
    )
    _write(
        framenet / "placing.xml",
        """
        <frame name="Placing">
          <FE name="Goal" />
          <lexUnit name="deploy.v" />
        </frame>
        """,
    )
    _write(
        semlink / "map.xml",
        """
        <mappings>
          <predicate vncls="put-9.1" fnframe="Placing" vnrole="Goal" fnrole="Goal" />
        </mappings>
        """,
    )
    _write(
        wordnet / "synsets.txt",
        """
        100,server
        200,computer_system machine
        """,
    )
    _write(
        wordnet / "hypernyms.txt",
        """
        100,200
        """,
    )
    _write(
        seeds,
        """
        server
        """,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(IMPORT_SCRIPT),
            "--verbnet",
            str(verbnet),
            "--framenet",
            str(framenet),
            "--semlink",
            str(semlink),
            "--wordnet",
            str(wordnet),
            "--seed-terms",
            str(seeds),
            "--generated-dir",
            str(generated),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    compiled = json.loads((generated / "compiled_rewrite_knowledge.json").read_text(encoding="utf-8"))
    assert compiled["semantic_role_overrides"]["deploy"]["on"] == "location"
    assert compiled["frame_annotations"]["deploy"]["frames"] == ["Placing"]
    assert compiled["role_aliases"]["goal"] == "destination"
    assert compiled["semlink_frame_mappings"]["put-9.1"] == ["Placing"]
    assert compiled["term_class_overrides"]["server"] == ["host"]
