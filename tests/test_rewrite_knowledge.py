"""Tests for generated offline rewrite-knowledge compilation."""

import json

from ambisense.rewrite_knowledge import (
    COMPILED_FILENAME,
    compile_generated_knowledge,
    default_generated_documents,
    ensure_generated_layout,
    load_compiled_rewrite_knowledge,
    load_generated_documents,
    validate_generated_documents,
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TestGeneratedLayout:
    def test_placeholder_documents_are_created(self, tmp_path):
        ensure_generated_layout(tmp_path)

        for filename in default_generated_documents():
            assert (tmp_path / filename).exists()

    def test_placeholder_documents_validate(self, tmp_path):
        ensure_generated_layout(tmp_path)
        documents = load_generated_documents(tmp_path)

        assert validate_generated_documents(documents) == []


class TestCompileGeneratedKnowledge:
    def test_compiler_merges_imported_roles_and_term_classes(self, tmp_path):
        ensure_generated_layout(tmp_path)

        verbnet = default_generated_documents()["verbnet_index.json"]
        verbnet["roles"] = {
            "deploy": {
                "on": "location"
            }
        }

        wordnet = default_generated_documents()["wordnet_types.json"]
        wordnet["term_classes"] = {
            "daemon": ["runtime_workload"],
            "machine": ["host"]
        }

        semlink = default_generated_documents()["semlink_map.json"]
        semlink["role_aliases"] = {
            "locative": "location"
        }
        semlink["frame_mappings"] = {
            "put-9.1": ["Placing"]
        }

        _write_json(tmp_path / "verbnet_index.json", verbnet)
        _write_json(tmp_path / "wordnet_types.json", wordnet)
        _write_json(tmp_path / "semlink_map.json", semlink)

        compiled = compile_generated_knowledge(tmp_path)

        assert compiled["semantic_role_overrides"]["deploy"]["on"] == "location"
        assert compiled["term_class_overrides"]["daemon"] == ["runtime_workload"]
        assert compiled["role_aliases"]["locative"] == "location"
        assert compiled["semlink_frame_mappings"]["put-9.1"] == ["Placing"]
        assert (tmp_path / COMPILED_FILENAME).exists()

    def test_compiled_knowledge_loads_as_runtime_overlay(self, tmp_path):
        ensure_generated_layout(tmp_path)

        compiled_payload = default_generated_documents()[COMPILED_FILENAME]
        compiled_payload["semantic_role_overrides"] = {
            "download": {
                "from": "source"
            }
        }
        compiled_payload["term_class_overrides"] = {
            "node": ["host"]
        }
        compiled_payload["semlink_frame_mappings"] = {
            "put-9.1": ["Placing"]
        }

        _write_json(tmp_path / COMPILED_FILENAME, compiled_payload)
        compiled = load_compiled_rewrite_knowledge(tmp_path)

        assert compiled.semantic_role_overrides["download"]["from"] == "source"
        assert compiled.term_class_overrides["node"] == ["host"]
        assert compiled.semlink_frame_mappings["put-9.1"] == ["Placing"]
