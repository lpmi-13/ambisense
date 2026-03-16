"""Offline resource download and extraction helpers for rewrite knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tarfile
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.request import urlopen


@dataclass(frozen=True)
class OfflineResourceSpec:
    """Download and extraction metadata for one upstream offline resource."""

    key: str
    display_name: str
    homepage_url: str
    download_url: Optional[str]
    archive_name: Optional[str]
    import_subpath: Optional[str]
    manual_only: bool = False
    manual_instructions: Optional[str] = None


OFFLINE_RESOURCE_SPECS: Dict[str, OfflineResourceSpec] = {
    "verbnet": OfflineResourceSpec(
        key="verbnet",
        display_name="VerbNet 3.3",
        homepage_url="https://verbs.colorado.edu/~mpalmer/projects/verbnet/downloads.html",
        download_url="https://verbs.colorado.edu/verb-index/vn/verbnet-3.3.tar.gz",
        archive_name="verbnet-3.3.tar.gz",
        import_subpath=None,
    ),
    "framenet": OfflineResourceSpec(
        key="framenet",
        display_name="FrameNet 1.7",
        homepage_url="https://framenet.icsi.berkeley.edu/framenet_data",
        download_url=None,
        archive_name=None,
        import_subpath=None,
        manual_only=True,
        manual_instructions="Download the XML release manually from https://framenet.icsi.berkeley.edu/framenet_request_data and then pass it to tools/import_offline_resources.py with --framenet.",
    ),
    "semlink": OfflineResourceSpec(
        key="semlink",
        display_name="SemLink 2.0",
        homepage_url="https://github.com/cu-clear/semlink",
        download_url="https://codeload.github.com/cu-clear/semlink/tar.gz/refs/heads/master",
        archive_name="semlink-master.tar.gz",
        import_subpath="instances",
    ),
    "wordnet": OfflineResourceSpec(
        key="wordnet",
        display_name="WordNet 3.0",
        homepage_url="https://wordnet.princeton.edu/homepage",
        download_url="https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz",
        archive_name="WordNet-3.0.tar.gz",
        import_subpath="dict",
    ),
}


@dataclass(frozen=True)
class DownloadedOfflineResource:
    """Local archive, extracted root, and importer entrypoint for a resource."""

    spec: OfflineResourceSpec
    archive_path: Path
    extract_dir: Path
    import_path: Path


def get_offline_resource_specs() -> Dict[str, OfflineResourceSpec]:
    """Return supported offline resource specs keyed by short name."""
    return OFFLINE_RESOURCE_SPECS


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    """Extract a tarball while rejecting path traversal members."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as tar:
        for member in tar.getmembers():
            member_path = destination / member.name
            resolved = member_path.resolve()
            if not str(resolved).startswith(str(destination.resolve())):
                raise ValueError(f"Unsafe archive member: {member.name}")
        tar.extractall(destination)


def _download_url_to_path(url: str, destination: Path) -> None:
    """Download a URL to a destination path using stdlib urllib."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response, open(destination, "wb") as fh:  # noqa: S310
        shutil.copyfileobj(response, fh)


def _archive_suffix(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".tar.gz"):
        return ".tar.gz"
    if path.endswith(".tgz"):
        return ".tgz"
    if path.endswith(".tar"):
        return ".tar"
    return ".archive"


def _locate_import_path(extract_dir: Path, import_subpath: Optional[str]) -> Path:
    """Resolve the import entrypoint within an extracted resource tree."""
    if import_subpath is None:
        return extract_dir

    direct = extract_dir / import_subpath
    if direct.exists():
        return direct

    for candidate in sorted(extract_dir.rglob(import_subpath)):
        if candidate.is_dir():
            return candidate

    return direct


def fetch_offline_resource(
    resource_key: str,
    cache_dir: Path,
    force: bool = False,
    url_override: Optional[str] = None,
) -> DownloadedOfflineResource:
    """Download and extract one supported offline resource."""
    spec = OFFLINE_RESOURCE_SPECS[resource_key]
    if spec.manual_only or spec.download_url is None or spec.archive_name is None:
        raise ValueError(spec.manual_instructions or f"{spec.display_name} must be downloaded manually.")

    resource_dir = cache_dir / resource_key
    archive_dir = resource_dir / "archives"
    extracted_parent = resource_dir / "extracted"
    archive_path = archive_dir / spec.archive_name
    extract_dir = extracted_parent

    if force and resource_dir.exists():
        shutil.rmtree(resource_dir)

    download_url = url_override or spec.download_url
    if not archive_path.exists():
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        _download_url_to_path(download_url, archive_path)

    if not extract_dir.exists():
        _safe_extract_tar(archive_path, extract_dir)

    import_path = _locate_import_path(extract_dir, spec.import_subpath)
    return DownloadedOfflineResource(
        spec=spec,
        archive_path=archive_path,
        extract_dir=extract_dir,
        import_path=import_path,
    )
