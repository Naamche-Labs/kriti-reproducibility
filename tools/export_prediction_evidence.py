#!/usr/bin/env python3
"""Export reproducibility evidence without redistributing gated speech text."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_RECORDS = 3_630
EXPECTED_SOURCE_COUNTS = {
    "fleurs_ne_np": 304,
    "indicvoices_nepali": 2_569,
    "openslr54": 757,
}
PUBLIC_SOURCES = {
    "fleurs_ne_np": {
        "license": "CC-BY-4.0",
        "upstream": "google/fleurs",
    },
    "openslr54": {
        "license": "CC-BY-SA-4.0",
        "upstream": "OpenSLR SLR54",
    },
}
GATED_SOURCES = {"indicvoices_nepali"}
REMOTE_KEY_OVERRIDES = {
    "kriti": "kriti-nepali-compact-encoder-domain-v1",
}
SAFE_SAMPLE_ID = re.compile(r"[A-Za-z0-9._:-]{1,160}\Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def read_predictions(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            row = json.loads(line)
            if set(row) != {"error_type", "hypothesis", "reference", "sample_id", "source_id"}:
                raise ValueError(f"unexpected prediction schema at {path}:{line_number}")
            if row["error_type"]:
                raise ValueError(f"failed prediction at {path}:{line_number}")
            if not SAFE_SAMPLE_ID.fullmatch(str(row["sample_id"])):
                raise ValueError(f"unsafe sample ID at {path}:{line_number}")
            rows.append({key: str(value) for key, value in row.items()})
    if len(rows) != EXPECTED_RECORDS:
        raise ValueError(f"unexpected prediction count: {path}")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError(f"duplicate sample ID: {path}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["source_id"]] = counts.get(row["source_id"], 0) + 1
    if counts != EXPECTED_SOURCE_COUNTS:
        raise ValueError(f"unexpected source composition: {path}")
    return rows


def canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
            )


def row_identity(rows: list[dict[str, str]]) -> list[tuple[str, str, str]]:
    return [(row["sample_id"], row["source_id"], row["reference"]) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--completed-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    args = parser.parse_args()

    benchmark_root = args.benchmark_root.resolve(strict=True)
    report = read_json(args.completed_report.resolve(strict=True))
    systems = report.get("completed_systems")
    if (
        report.get("status") != "stopped_by_user"
        or not isinstance(systems, list)
        or len(systems) != 19
    ):
        raise ValueError("the completed-system authority is not the stopped 19-system snapshot")
    if args.output.exists():
        raise ValueError(f"refusing to overwrite output: {args.output}")
    args.output.mkdir(parents=True)

    canonical_identity: list[tuple[str, str, str]] | None = None
    canonical_rows: list[dict[str, str]] | None = None
    metric_records: list[dict[str, Any]] = []
    output_files: list[dict[str, Any]] = []

    for system in systems:
        public_key = str(system["key"])
        remote_key = REMOTE_KEY_OVERRIDES.get(public_key, public_key)
        evaluation_root = benchmark_root / "evaluations" / remote_key
        replicate_paths = [
            evaluation_root / f"replicate-{replicate}" / "predictions.jsonl" for replicate in (1, 2)
        ]
        expected_hashes = list(system["validation"]["replicate_prediction_sha256"])
        actual_hashes = [sha256(path) for path in replicate_paths]
        if actual_hashes != expected_hashes or len(set(actual_hashes)) != 1:
            raise ValueError(f"replicate prediction identity mismatch: {public_key}")

        replicate_rows = [read_predictions(path) for path in replicate_paths]
        if replicate_rows[0] != replicate_rows[1]:
            raise ValueError(f"replicate row mismatch: {public_key}")
        identity = row_identity(replicate_rows[0])
        if canonical_identity is None:
            canonical_identity = identity
            canonical_rows = replicate_rows[0]
        elif identity != canonical_identity:
            raise ValueError(f"view identity/reference mismatch: {public_key}")

        summaries = [
            read_json(evaluation_root / f"replicate-{replicate}" / "summary.json")
            for replicate in (1, 2)
        ]
        for replicate, summary in enumerate(summaries):
            if summary.get("predictions_sha256") != actual_hashes[replicate]:
                raise ValueError(f"summary prediction hash mismatch: {public_key}")
            if summary.get("failures") != 0 or summary.get("limited_evaluation") is not False:
                raise ValueError(f"invalid completed summary: {public_key}")
        if summaries[0].get("overall") != summaries[1].get("overall"):
            raise ValueError(f"replicate overall metrics mismatch: {public_key}")
        if summaries[0].get("per_source") != summaries[1].get("per_source"):
            raise ValueError(f"replicate per-source metrics mismatch: {public_key}")
        if set(summaries[0]["per_source"]) != set(EXPECTED_SOURCE_COUNTS):
            raise ValueError(f"per-source metrics incomplete: {public_key}")

        metric_records.append(
            {
                "backend": system["backend"],
                "decoder": system["decoder"],
                "key": public_key,
                "model_id": system["model_id"],
                "overall": summaries[0]["overall"],
                "per_source": summaries[0]["per_source"],
                "rank": system["rank"],
                "replicate_prediction_sha256": actual_hashes,
                "revision": system["revision"],
            }
        )

        for source_id, source_metadata in PUBLIC_SOURCES.items():
            exported_rows = [
                {
                    "hypothesis": row["hypothesis"],
                    "ordinal": ordinal,
                    "reference": row["reference"],
                    "sample_id": row["sample_id"],
                    "source_id": source_id,
                }
                for ordinal, row in enumerate(replicate_rows[0])
                if row["source_id"] == source_id
            ]
            output_path = args.output / "predictions" / public_key / f"{source_id}.jsonl"
            write_jsonl(output_path, exported_rows)
            output_files.append(
                {
                    "bytes": output_path.stat().st_size,
                    "license": source_metadata["license"],
                    "path": output_path.relative_to(args.output).as_posix(),
                    "records": len(exported_rows),
                    "sha256": sha256(output_path),
                    "source_id": source_id,
                    "system": public_key,
                    "upstream": source_metadata["upstream"],
                }
            )

    if canonical_rows is None:
        raise AssertionError("no canonical rows were established")
    roster = [
        {
            "access": "public" if row["source_id"] in PUBLIC_SOURCES else "gated",
            "ordinal": ordinal,
            "sample_id": row["sample_id"],
            "source_id": row["source_id"],
        }
        for ordinal, row in enumerate(canonical_rows)
    ]
    roster_path = args.output / "view" / "ordered-sample-ids.jsonl"
    write_jsonl(roster_path, roster)
    output_files.append(
        {
            "bytes": roster_path.stat().st_size,
            "path": roster_path.relative_to(args.output).as_posix(),
            "records": len(roster),
            "sha256": sha256(roster_path),
        }
    )

    metrics = {
        "benchmark_id": report["benchmark_id"],
        "records": EXPECTED_RECORDS,
        "source_counts": EXPECTED_SOURCE_COUNTS,
        "systems": metric_records,
        "view_sha256": report["evaluation_contract"]["view_sha256"],
    }
    metrics_path = args.output / "metrics" / "per-source.json"
    write_json(metrics_path, metrics)
    output_files.append(
        {
            "bytes": metrics_path.stat().st_size,
            "path": metrics_path.relative_to(args.output).as_posix(),
            "sha256": sha256(metrics_path),
        }
    )

    index = {
        "schema_version": "1.0",
        "recorded_at": args.recorded_at,
        "benchmark_id": report["benchmark_id"],
        "scope": {
            "full_view_records": EXPECTED_RECORDS,
            "gated_records": EXPECTED_SOURCE_COUNTS["indicvoices_nepali"],
            "public_prediction_records_per_system": sum(
                EXPECTED_SOURCE_COUNTS[source] for source in PUBLIC_SOURCES
            ),
            "systems": len(metric_records),
        },
        "privacy": {
            "gated_prediction_rows_published": 0,
            "gated_reference_rows_published": 0,
            "gated_roster_fields": ["access", "ordinal", "sample_id", "source_id"],
        },
        "files": sorted(output_files, key=lambda item: item["path"]),
    }
    write_json(args.output / "export-index.json", index)
    print(
        json.dumps(
            {
                "files": len(output_files) + 1,
                "full_view_records": len(roster),
                "public_prediction_rows": sum(item.get("records", 0) for item in output_files)
                - len(roster),
                "systems": len(metric_records),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
