"""Run Phase 1.3-C static zone / camera-prior POC across dataset configs."""

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

DEFAULT_OUTPUT_ROOT = "outputs/static_zone_prior_poc"
DEFAULT_MATRIX_OUTPUT_ROOT = "outputs/static_zone_prior_matrices"


@dataclass(frozen=True)
class StaticZoneMatrixExperiment:
    name: str
    dataset: Path
    limit: int


@dataclass(frozen=True)
class PlannedStaticZoneRun:
    experiment_name: str
    dataset: Path
    run_id: str
    run_root: Path
    command: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dataset"] = project_relative(self.dataset)
        data["run_root"] = str(self.run_root)
        data["command"] = list(self.command)
        return data


def load_static_zone_matrix_experiment(path: str | Path) -> StaticZoneMatrixExperiment:
    experiment_path = resolve_project_path(path)
    data = load_yaml_config(experiment_path)
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported experiment schema: {data.get('schema_version')}")
    dataset = resolve_project_path(str(data.get("dataset", "")))
    if not dataset.is_file():
        raise ValueError(f"Dataset config does not exist: {dataset}")
    limit = int(data.get("limit", 0))
    if limit <= 0:
        raise ValueError("Experiment limit must be a positive integer.")
    return StaticZoneMatrixExperiment(
        name=str(data.get("name") or experiment_path.stem),
        dataset=dataset,
        limit=limit,
    )


def build_static_zone_matrix_plan(
    experiment_configs: list[str | Path],
    run_output_root: str | Path,
    run_suffix: str,
    grid_columns: int,
    grid_rows: int,
) -> list[PlannedStaticZoneRun]:
    plan: list[PlannedStaticZoneRun] = []
    for experiment_config in experiment_configs:
        experiment = load_static_zone_matrix_experiment(experiment_config)
        run_id = f"{experiment.name}_static_zone_prior_{run_suffix}"
        run_root = Path(run_output_root) / run_id
        command = (
            sys.executable,
            str(PROJECT_ROOT / "experiments" / "run_static_zone_prior_poc.py"),
            "--dataset-config",
            project_relative(experiment.dataset),
            "--experiment-name",
            experiment.name,
            "--run-id",
            run_id,
            "--output-root",
            str(run_output_root),
            "--limit",
            str(experiment.limit),
            "--grid-columns",
            str(grid_columns),
            "--grid-rows",
            str(grid_rows),
        )
        plan.append(
            PlannedStaticZoneRun(
                experiment_name=experiment.name,
                dataset=experiment.dataset,
                run_id=run_id,
                run_root=run_root,
                command=command,
            )
        )
    if not plan:
        raise ValueError("At least one experiment config is required.")
    return plan


def execute_static_zone_matrix(
    plan: list[PlannedStaticZoneRun],
    matrix_root: Path,
    experiment_configs: list[str | Path],
    dry_run: bool,
) -> dict[str, Any]:
    matrix_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "pipeline_type": "static_zone_prior_matrix",
        "experiment_configs": [project_relative(resolve_project_path(path)) for path in experiment_configs],
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
        summary = summarize_static_zone_runs(plan)
        write_json(summary, matrix_root / "summary.json")
        write_text(render_static_zone_summary_markdown(summary), matrix_root / "summary.md")
    return manifest


def summarize_static_zone_runs(plan: list[PlannedStaticZoneRun]) -> dict[str, Any]:
    runs = []
    for planned in plan:
        report_path = planned.run_root / "reports" / "static_zone_prior_report.json"
        data = json.loads(report_path.read_text(encoding="utf-8"))
        runs.append(
            {
                "experiment_name": planned.experiment_name,
                "run_root": str(planned.run_root),
                "frame_count": data["frame_count"],
                "target_frame_count": data["target_frame_count"],
                "target_gt_count": data["target_gt_count"],
                "occupied_cell_count": data["occupied_cell_count"],
                "occupied_cell_ratio": data["occupied_cell_ratio"],
                "profiles": data["profiles"],
            }
        )
    return {"schema_version": 1, "runs": runs}


def render_static_zone_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Static Zone / Camera Prior Matrix Summary",
        "",
        (
            "| Dataset | Profile | Selected area | Area reduction | Center GT recall | "
            "BBox GT recall | Center frame recall | BBox frame recall |"
        ),
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in summary["runs"]:
        for profile_name, profile in run["profiles"].items():
            lines.append(
                "| "
                f"`{run['experiment_name']}` | "
                f"`{profile_name}` | "
                f"{_format_ratio(profile['selected_area_ratio'])} | "
                f"{_format_ratio(profile['input_area_reduction'])} | "
                f"{_format_ratio(profile['center_gt_recall'])} | "
                f"{_format_ratio(profile['bbox_gt_recall'])} | "
                f"{_format_ratio(profile['center_target_frame_recall'])} | "
                f"{_format_ratio(profile['bbox_target_frame_recall'])} |"
            )
    lines.append("")
    return "\n".join(lines)


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def project_relative(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(candidate)


def _format_ratio(value: float) -> str:
    return f"{value:.3f} ({value * 100:.1f}%)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3-C static zone prior matrix.")
    parser.add_argument("--experiment-config", action="append", required=True)
    parser.add_argument("--run-output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--matrix-output-root", default=DEFAULT_MATRIX_OUTPUT_ROOT)
    parser.add_argument("--grid-columns", type=int, default=32)
    parser.add_argument("--grid-rows", type=int, default=18)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    plan = build_static_zone_matrix_plan(
        experiment_configs=args.experiment_config,
        run_output_root=args.run_output_root,
        run_suffix=suffix,
        grid_columns=args.grid_columns,
        grid_rows=args.grid_rows,
    )
    matrix_root = Path(args.matrix_output_root) / f"phase1_3_static_zone_prior_{suffix}"
    manifest = execute_static_zone_matrix(
        plan=plan,
        matrix_root=matrix_root,
        experiment_configs=args.experiment_config,
        dry_run=args.dry_run,
    )
    print(json.dumps({"matrix_root": str(matrix_root), **manifest}, indent=2))


if __name__ == "__main__":
    main()
