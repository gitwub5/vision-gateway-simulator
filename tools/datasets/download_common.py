"""Shared helpers for dataset download scripts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


def download_url(url: str, output_path: Path, force: bool = False) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        print(f"Already exists, skipping download: {output_path}")
        return output_path
    print(f"Downloading {url}")
    print(f"-> {output_path}")
    urllib.request.urlretrieve(url, output_path)
    return output_path


def download_google_drive_file(file_id: str, output_path: Path, force: bool = False) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        print(f"Already exists, skipping download: {output_path}")
        return output_path

    gdown = shutil.which("gdown")
    if gdown:
        command = [gdown, file_id, "-O", str(output_path)]
    else:
        command = [sys.executable, "-m", "gdown", file_id, "-O", str(output_path)]
    try:
        subprocess.run(command, check=True)
    except (subprocess.CalledProcessError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "`gdown` is required for Google Drive dataset downloads. "
            "Install it with `pip install gdown`, or download manually from "
            f"https://drive.google.com/file/d/{file_id}/view and place it at {output_path}."
        ) from exc
    return output_path


def extract_zip(archive_path: Path, output_dir: Path, force: bool = False) -> Path:
    marker_path = output_dir / ".extract_complete"
    if marker_path.exists() and not force:
        print(f"Already extracted, skipping: {output_dir}")
        return output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {archive_path}")
    print(f"-> {output_dir}")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(output_dir)
    marker_path.write_text(str(archive_path), encoding="utf-8")
    return output_dir


def extract_zip_prefix(
    archive_path: Path,
    output_dir: Path,
    prefix: str,
    force: bool = False,
) -> Path:
    marker_name = f".extract_{archive_path.stem}_{prefix.strip('/').replace('/', '_')}_complete"
    marker_path = output_dir / marker_name
    if marker_path.exists() and not force:
        print(f"Already extracted, skipping prefix {prefix}: {output_dir}")
        return output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_prefix = prefix.rstrip("/") + "/"
    print(f"Extracting {normalized_prefix} from {archive_path}")
    print(f"-> {output_dir}")
    with zipfile.ZipFile(archive_path) as archive:
        members = [name for name in archive.namelist() if name.startswith(normalized_prefix)]
        if not members:
            raise FileNotFoundError(f"No zip members found with prefix {normalized_prefix}")
        for member in members:
            archive.extract(member, output_dir)
    marker_path.write_text(str(archive_path), encoding="utf-8")
    return output_dir


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote manifest: {path}")
