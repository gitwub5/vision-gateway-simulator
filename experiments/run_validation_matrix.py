"""Run a registry-backed matrix of ROI proposal validations."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.io import load_yaml_config, write_json, write_text
from roi_generator import load_roi_generator_config
from tools.summarize_roi_proposal_runs import render_markdown, summarize_runs


DEFAULT_REGISTRY = "configs/roi_generator/profiles.yaml"
DEFAULT_RUN_OUTPUT_ROOT = "outputs/roi_proposal_validation"
DEFAULT_MATRIX_OUTPUT_ROOT = "outputs/validation_matrices"
DIAGNOSTICS_LEVELS = {"minimal", "tile_trace", "full"}
RUNNABLE_PROFILE_STATUSES = {"active", "reference_only"}


@dataclass(frozen=True)
class ProfileDefinition:
    name: str
    config: Path
    status: str
    role: str
    reference_feedback_source: str = "none"


@dataclass(frozen=True)
class MatrixExperiment:
    name: str
    dataset: Path
    limit: int
    diagnostics_level: str
    model_config: Path
    profiles: tuple[str, ...]
    skip_visualization: bool


@dataclass(frozen=True)
class PlannedRun:
    profile: str
    role: str
    run_id: str
    run_root: Path
    command: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["run_root"] = str(self.run_root)
        data["command"] = list(self.command)
        return data


def load_profile_registry(path: str | Path) -> dict[str, ProfileDefinition]:
    registry_path = resolve_project_path(path)
    data = load_yaml_config(registry_path)
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported profile registry schema: {data.get('schema_version')}")
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ValueError("Profile registry must define a non-empty profiles mapping.")

    profiles: dict[str, ProfileDefinition] = {}
    for name, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Profile {name} must be a mapping.")
        config = registry_path.parent / str(raw.get("config", ""))
        status = str(raw.get("status", "disabled"))
        feedback_source = str(raw.get("reference_feedback_source", "none"))
        if not config.is_file():
            raise ValueError(f"Profile {name} config does not exist: {config}")
        if feedback_source not in {"none", "ground_truth", "full_frame_yolo"}:
            raise ValueError(f"Profile {name} has unsupported feedback source: {feedback_source}")
        profiles[str(name)] = ProfileDefinition(
            name=str(name),
            config=config,
            status=status,
            role=str(raw.get("role", "candidate")),
            reference_feedback_source=feedback_source,
        )
    return profiles


def load_matrix_experiment(path: str | Path) -> MatrixExperiment:
    experiment_path = resolve_project_path(path)
    data = load_yaml_config(experiment_path)
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported experiment schema: {data.get('schema_version')}")
    diagnostics_level = str(data.get("diagnostics_level", ""))
    if diagnostics_level not in DIAGNOSTICS_LEVELS:
        raise ValueError(
            "Experiment YAML must select diagnostics_level from "
            f"{sorted(DIAGNOSTICS_LEVELS)}."
        )
    profiles = tuple(str(item) for item in data.get("profiles", []))
    if not profiles:
        raise ValueError("Experiment YAML must select at least one profile.")
    limit = int(data.get("limit", 0))
    if limit <= 0:
        raise ValueError("Experiment limit must be a positive integer.")

    dataset = resolve_project_path(str(data.get("dataset", "")))
    model_config = resolve_project_path(
        str(data.get("model_config", "configs/models/yolo_default.yaml"))
    )
    if not dataset.is_file():
        raise ValueError(f"Dataset config does not exist: {dataset}")
    if not model_config.is_file():
        raise ValueError(f"Model config does not exist: {model_config}")
    return MatrixExperiment(
        name=str(data.get("name") or experiment_path.stem),
        dataset=dataset,
        limit=limit,
        diagnostics_level=diagnostics_level,
        model_config=model_config,
        profiles=profiles,
        skip_visualization=bool(data.get("skip_visualization", True)),
    )


def build_matrix_plan(
    experiment: MatrixExperiment,
    registry: dict[str, ProfileDefinition],
    run_output_root: str | Path,
    run_suffix: str,
    selected_profiles: set[str] | None = None,
) -> list[PlannedRun]:
    plan: list[PlannedRun] = []
    for profile_name in experiment.profiles:
        if selected_profiles and profile_name not in selected_profiles:
            continue
        try:
            profile = registry[profile_name]
        except KeyError as exc:
            raise ValueError(f"Experiment references unknown profile: {profile_name}") from exc
        if profile.status not in RUNNABLE_PROFILE_STATUSES:
            raise ValueError(
                f"Experiment profile {profile_name} is not runnable: status={profile.status}"
            )
        feedback_enabled = load_roi_generator_config(profile.config).reference_feedback_enabled
        source_enabled = profile.reference_feedback_source != "none"
        if feedback_enabled != source_enabled:
            raise ValueError(
                f"Profile {profile_name} feedback contract mismatch: "
                f"config enabled={feedback_enabled}, "
                f"source={profile.reference_feedback_source}"
            )
        run_id = f"{experiment.name}_{profile_name}_{run_suffix}"
        run_root = Path(run_output_root) / run_id
        command = [
            sys.executable,
            str(PROJECT_ROOT / "experiments" / "run_roi_proposal_validation.py"),
            "--dataset-config",
            project_relative(experiment.dataset),
            "--roi-generator-config",
            project_relative(profile.config),
            "--model-config",
            project_relative(experiment.model_config),
            "--experiment-name",
            f"{experiment.name}_{profile_name}",
            "--run-id",
            run_id,
            "--output-root",
            str(run_output_root),
            "--limit",
            str(experiment.limit),
            "--diagnostics-level",
            experiment.diagnostics_level,
            "--reference-feedback-source",
            profile.reference_feedback_source,
        ]
        if experiment.skip_visualization:
            command.append("--skip-visualization")
        plan.append(
            PlannedRun(
                profile=profile_name,
                role=profile.role,
                run_id=run_id,
                run_root=run_root,
                command=tuple(command),
            )
        )
    if not plan:
        raise ValueError("No profiles remain after applying the profile filter.")
    return plan


def execute_matrix(
    plan: list[PlannedRun],
    matrix_root: Path,
    experiment_path: Path,
    registry_path: Path,
    experiment: MatrixExperiment,
    dry_run: bool,
) -> dict[str, Any]:
    matrix_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "pipeline_type": "roi_proposal_validation_matrix",
        "experiment_name": experiment.name,
        "experiment_config": project_relative(experiment_path),
        "profile_registry": project_relative(registry_path),
        "diagnostics_level": experiment.diagnostics_level,
        "dataset": project_relative(experiment.dataset),
        "limit": experiment.limit,
        "dry_run": dry_run,
        "runs": [
            {**planned.to_json_dict(), "status": "planned"}
            for planned in plan
        ],
    }
    write_json(manifest, matrix_root / "manifest.json")

    if not dry_run:
        for index, planned in enumerate(plan):
            manifest["runs"][index]["status"] = "running"
            write_json(manifest, matrix_root / "manifest.json")
            try:
                subprocess.run(list(planned.command), cwd=PROJECT_ROOT, check=True)
            except subprocess.CalledProcessError as exc:
                manifest["runs"][index]["status"] = "failed"
                manifest["runs"][index]["return_code"] = exc.returncode
                write_json(manifest, matrix_root / "manifest.json")
                raise
            manifest["runs"][index]["status"] = "completed"
            write_json(manifest, matrix_root / "manifest.json")

    if not dry_run:
        run_specs = [f"{item.profile}={item.run_root}" for item in plan]
        summary = summarize_runs(run_specs)
        write_json(summary, matrix_root / "summary.json")
        write_text(render_markdown(summary), matrix_root / "summary.md")
    return manifest


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def project_relative(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a registry-backed ROI validation matrix.")
    parser.add_argument("--experiment-config", required=True)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--run-output-root", default=DEFAULT_RUN_OUTPUT_ROOT)
    parser.add_argument("--matrix-output-root", default=DEFAULT_MATRIX_OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    experiment_path = resolve_project_path(args.experiment_config)
    registry_path = resolve_project_path(args.registry)
    experiment = load_matrix_experiment(experiment_path)
    registry = load_profile_registry(registry_path)
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    plan = build_matrix_plan(
        experiment=experiment,
        registry=registry,
        run_output_root=args.run_output_root,
        run_suffix=suffix,
        selected_profiles=set(args.profile) if args.profile else None,
    )
    matrix_root = Path(args.matrix_output_root) / f"{experiment.name}_{suffix}"
    manifest = execute_matrix(
        plan=plan,
        matrix_root=matrix_root,
        experiment_path=experiment_path,
        registry_path=registry_path,
        experiment=experiment,
        dry_run=args.dry_run,
    )
    print(json.dumps({"matrix_root": str(matrix_root), **manifest}, indent=2))


if __name__ == "__main__":
    main()
