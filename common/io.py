"""Small file I/O helpers shared by experiment, inference, and evaluation code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Protocol


class JsonSerializable(Protocol):
    def to_json_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    yaml = require_yaml()
    with Path(config_path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def read_json(input_path: str | Path) -> dict[str, Any]:
    with Path(input_path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(data: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def read_jsonl(input_path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(input_path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def write_jsonl(records: Iterable[JsonSerializable], output_path: str | Path, append: bool = False) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record.to_json_dict(), ensure_ascii=False) + "\n")


def write_text(text: str, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def require_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required for loading YAML config files. Install project dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yaml
