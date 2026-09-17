"""Run Phase 1.3-F compression signal prototype across dataset configs."""

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

DEFAULT_OUTPUT_ROOT = "outputs/compression_signal_poc"
DEFAULT_MATRIX_OUTPUT_ROOT = "outputs/compression_signal_matrices"


@dataclass(frozen=True)
class CompressionSignalMatrixExperiment:
    name: str
    dataset: Path
    limit: int


@dataclass(frozen=True)
class PlannedCompressionSignalRun:
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


def load_compression_signal_matrix_experiment(path: str | Path) -> CompressionSignalMatrixExperiment:
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
    return CompressionSignalMatrixExperiment(
        name=str(data.get("name") or experiment_path.stem),
        dataset=dataset,
        limit=limit,
    )


def build_compression_signal_matrix_plan(
    experiment_configs: list[str | Path],
    run_output_root: str | Path,
    run_suffix: str,
) -> list[PlannedCompressionSignalRun]:
    plan: list[PlannedCompressionSignalRun] = []
    for experiment_config in experiment_configs:
        experiment = load_compression_signal_matrix_experiment(experiment_config)
        run_id = f"{experiment.name}_compression_signal_{run_suffix}"
        run_root = Path(run_output_root) / run_id
        command = (
            sys.executable,
            str(PROJECT_ROOT / "experiments" / "run_compression_signal_poc.py"),
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
        )
        plan.append(
            PlannedCompressionSignalRun(
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


def execute_compression_signal_matrix(
    plan: list[PlannedCompressionSignalRun],
    matrix_root: Path,
    experiment_configs: list[str | Path],
    dry_run: bool,
) -> dict[str, Any]:
    matrix_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "pipeline_type": "compression_signal_matrix",
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
        summary = summarize_compression_signal_runs(plan)
        write_json(summary, matrix_root / "summary.json")
        write_text(render_compression_signal_summary_markdown(summary), matrix_root / "summary.md")
    return manifest


def summarize_compression_signal_runs(plan: list[PlannedCompressionSignalRun]) -> dict[str, Any]:
    runs = []
    for planned in plan:
        report_path = planned.run_root / "reports" / "compression_signal_report.json"
        data = json.loads(report_path.read_text(encoding="utf-8"))
        runs.append(
            {
                "experiment_name": planned.experiment_name,
                "run_root": str(planned.run_root),
                "dataset_type": data["dataset_type"],
                "status": data["status"],
                "reason": data["reason"],
                "frame_count": data["frame_count"],
                "key_frame_rate": data["key_frame_rate"],
                "average_packet_size": data["average_packet_size"],
                "packet_size_coefficient_of_variation": data["packet_size_coefficient_of_variation"],
                "pict_type_counts": data["pict_type_counts"],
            }
        )
    return {"schema_version": 1, "runs": runs}


def render_compression_signal_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Compression Signal Matrix Summary",
        "",
        (
            "| Dataset | Type | Status | Frames | Key-frame rate | Avg packet size | "
            "Packet CV | Reason |"
        ),
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for run in summary["runs"]:
        lines.append(
            "| "
            f"`{run['experiment_name']}` | "
            f"`{run['dataset_type']}` | "
            f"`{run['status']}` | "
            f"{run['frame_count']} | "
            f"{run['key_frame_rate']:.3f} | "
            f"{run['average_packet_size']:.3f} | "
            f"{run['packet_size_coefficient_of_variation']:.3f} | "
            f"{run['reason']} |"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1.3-F compression signal matrix.")
    parser.add_argument("--experiment-config", action="append", required=True)
    parser.add_argument("--run-output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--matrix-output-root", default=DEFAULT_MATRIX_OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suffix = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    plan = build_compression_signal_matrix_plan(args.experiment_config, args.run_output_root, suffix)
    matrix_root = Path(args.matrix_output_root) / f"phase1_3_compression_signal_{suffix}"
    manifest = execute_compression_signal_matrix(
        plan=plan,
        matrix_root=matrix_root,
        experiment_configs=args.experiment_config,
        dry_run=args.dry_run,
    )
    print(json.dumps({"matrix_root": str(matrix_root), **manifest}, indent=2))


if __name__ == "__main__":
    main()
