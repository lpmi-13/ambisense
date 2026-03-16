"""Tests for offline resource fetch helpers."""

from __future__ import annotations

from pathlib import Path
import tarfile

from ambisense.rewrite_fetchers import fetch_offline_resource, get_offline_resource_specs


def _build_tarball(destination: Path, files: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / (destination.stem + "_staging")
    staging.mkdir(parents=True, exist_ok=True)
    try:
        for relative_path, content in files.items():
            path = staging / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        with tarfile.open(destination, "w:gz") as tar:
            tar.add(staging, arcname=".")
    finally:
        for path in sorted(staging.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        staging.rmdir()


def test_fetch_offline_resource_extracts_and_resolves_import_path(tmp_path):
    archive = tmp_path / "verbnet-3.3.tar.gz"
    _build_tarball(
        archive,
        {
            "verbnet3.3/put-9.1.xml": "<VNCLASS />\n",
        },
    )

    downloaded = fetch_offline_resource(
        "verbnet",
        tmp_path / "cache",
        url_override=archive.resolve().as_uri(),
    )

    assert downloaded.archive_path.exists()
    assert downloaded.import_path.is_dir()
    assert (downloaded.import_path / "verbnet3.3" / "put-9.1.xml").exists()


def test_fetch_offline_resource_uses_import_subpath_for_nested_resource(tmp_path):
    archive = tmp_path / "semlink-master.tar.gz"
    _build_tarball(
        archive,
        {
            "semlink-master/instances/vn-fn2.json": "{}\n",
            "semlink-master/instances/pb-vn2.json": "{}\n",
        },
    )

    downloaded = fetch_offline_resource(
        "semlink",
        tmp_path / "cache",
        url_override=archive.resolve().as_uri(),
    )

    assert downloaded.import_path.name == "instances"
    assert (downloaded.import_path / "vn-fn2.json").exists()


def test_resource_specs_mark_framenet_as_manual_only():
    specs = get_offline_resource_specs()

    assert specs["framenet"].manual_only is True
    assert specs["framenet"].download_url is None
