#!/usr/bin/env python3
"""Verify public Kriti evidence, row identity, and redistributable metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from metrics import metric_set

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
EXPECTED_SOURCE_COUNTS = {
    "fleurs_ne_np": 304,
    "indicvoices_nepali": 2_569,
    "openslr54": 757,
}
PUBLIC_SOURCES = {"fleurs_ne_np", "openslr54"}


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON objects: {path}")
    return rows


def verify_checksum_manifest(root: Path, manifest: Path) -> int:
    seen: set[str] = set()
    count = 0
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        digest, separator, name = line.partition("  ")
        if not separator or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"invalid checksum line {manifest}:{line_number}")
        if name.startswith(("/", "../")) or "/../" in name or name in seen:
            raise ValueError(f"unsafe or duplicate checksum subject: {name}")
        seen.add(name)
        subject = (root / name).resolve(strict=True)
        subject.relative_to(root.resolve())
        if sha256(subject) != digest:
            raise ValueError(f"checksum mismatch: {subject}")
        count += 1
    return count


def verify_aggregate_snapshot(snapshot: Path) -> dict[str, int]:
    checksummed = verify_checksum_manifest(snapshot, snapshot / "SHA256SUMS")
    index = read_json(snapshot / "index.json")
    commitments = read_json(snapshot / "commitments.json")
    records = index.get("records")
    if not isinstance(records, list) or len(records) != 182:
        raise ValueError("unexpected aggregate record count")
    for record in records:
        path = snapshot / record["public_path"]
        if path.stat().st_size != record["public_bytes"]:
            raise ValueError(f"public byte count mismatch: {path}")
        if sha256(path) != record["public_sha256"]:
            raise ValueError(f"public record mismatch: {path}")
        if not SHA256_RE.fullmatch(record["source_sha256"]):
            raise ValueError(f"invalid private source commitment: {path}")
    commitment_rows = commitments.get("commitments")
    if not isinstance(commitment_rows, list) or len(commitment_rows) != 730:
        raise ValueError("unexpected commitment count")
    if any(not SHA256_RE.fullmatch(item.get("sha256", "")) for item in commitment_rows):
        raise ValueError("invalid indexed commitment")
    return {
        "aggregate_records": len(records),
        "commitments": len(commitment_rows),
        "checksummed": checksummed,
    }


def verify_prediction_evidence(predictions_root: Path) -> dict[str, int]:
    checksummed = verify_checksum_manifest(predictions_root, predictions_root / "SHA256SUMS")
    index = read_json(predictions_root / "export-index.json")
    metrics = read_json(predictions_root / "metrics" / "per-source.json")
    if index["privacy"] != {
        "gated_prediction_rows_published": 0,
        "gated_reference_rows_published": 0,
        "gated_roster_fields": ["access", "ordinal", "sample_id", "source_id"],
    }:
        raise ValueError("gated-data publication boundary changed")
    for item in index["files"]:
        path = predictions_root / item["path"]
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"prediction evidence mismatch: {path}")

    roster = read_jsonl(predictions_root / "view" / "ordered-sample-ids.jsonl")
    if [row["ordinal"] for row in roster] != list(range(3_630)):
        raise ValueError("view ordinals are not complete and ordered")
    if len({row["sample_id"] for row in roster}) != 3_630:
        raise ValueError("sample IDs are not unique")
    if Counter(row["source_id"] for row in roster) != Counter(EXPECTED_SOURCE_COUNTS):
        raise ValueError("view source composition mismatch")
    for row in roster:
        expected_access = "public" if row["source_id"] in PUBLIC_SOURCES else "gated"
        if set(row) != {"access", "ordinal", "sample_id", "source_id"}:
            raise ValueError("roster contains an unapproved field")
        if row["access"] != expected_access:
            raise ValueError("roster access classification mismatch")

    systems = metrics.get("systems")
    if not isinstance(systems, list) or len(systems) != 19:
        raise ValueError("unexpected completed-system count")
    system_by_key = {system["key"]: system for system in systems}
    if len(system_by_key) != 19:
        raise ValueError("duplicate system key")
    canonical_references: dict[str, list[tuple[int, str, str]]] = {}
    prediction_rows = 0
    metric_sets = 0
    for key, system in sorted(system_by_key.items()):
        for source_id in sorted(PUBLIC_SOURCES):
            path = predictions_root / "predictions" / key / f"{source_id}.jsonl"
            rows = read_jsonl(path)
            if len(rows) != EXPECTED_SOURCE_COUNTS[source_id]:
                raise ValueError(f"public prediction count mismatch: {path}")
            expected_roster = [row for row in roster if row["source_id"] == source_id]
            actual_identity = [(row["ordinal"], row["sample_id"], row["source_id"]) for row in rows]
            roster_identity = [
                (row["ordinal"], row["sample_id"], row["source_id"]) for row in expected_roster
            ]
            if actual_identity != roster_identity:
                raise ValueError(f"public prediction identity mismatch: {path}")
            references = [(row["ordinal"], row["sample_id"], row["reference"]) for row in rows]
            if source_id in canonical_references and references != canonical_references[source_id]:
                raise ValueError(f"reference mismatch across systems: {source_id}")
            canonical_references.setdefault(source_id, references)
            recomputed = metric_set(
                [str(row["reference"]) for row in rows],
                [str(row["hypothesis"]) for row in rows],
            )
            if recomputed != system["per_source"][source_id]:
                raise ValueError(f"per-source metric mismatch: {key}/{source_id}")
            prediction_rows += len(rows)
            metric_sets += 1
    if prediction_rows != 19 * (304 + 757) or metric_sets != 38:
        raise ValueError("public prediction coverage mismatch")
    return {
        "checksummed": checksummed,
        "metric_sets_recomputed": metric_sets,
        "public_prediction_rows": prediction_rows,
        "sample_ids": len(roster),
        "systems": len(systems),
    }


def verify_independent_reproduction(root: Path) -> dict[str, int | str]:
    reproduction = root / "evidence" / "reproduction-20260819"
    checksummed = verify_checksum_manifest(reproduction, reproduction / "SHA256SUMS")
    summary = read_json(reproduction / "summary.json")
    environment = read_json(reproduction / "environment.json")
    metrics = read_json(root / "evidence" / "predictions-20260819" / "metrics" / "per-source.json")
    kriti = next(system for system in metrics["systems"] if system["key"] == "kriti")
    if summary["overall"] != kriti["overall"] or summary["per_source"] != kriti["per_source"]:
        raise ValueError("independent reproduction metrics differ from the published record")
    if summary["view_sha256"] != metrics["view_sha256"]:
        raise ValueError("independent reproduction view commitment mismatch")
    if summary["predictions_sha256"] not in kriti["replicate_prediction_sha256"]:
        raise ValueError("independent reproduction prediction commitment mismatch")
    if summary["valid"] is not True or summary["protected_test_accessed"] is not False:
        raise ValueError("independent reproduction validity boundary changed")
    exact_checks = {
        "overall_exact_match": True,
        "per_source_exact_match": True,
        "predictions_sha256_match": True,
        "view_sha256_match": True,
    }
    if any(summary["checks"].get(key) is not value for key, value in exact_checks.items()):
        raise ValueError("independent reproduction exact-match gate failed")
    execution = environment["execution"]
    if execution != {
        "batch_size": 32,
        "fresh_public_checkout": True,
        "fresh_tokenless_model_cache": True,
        "managed_run_id": "r_38e10f2c",
        "protected_test_accessed": False,
        "source_commit": "791d19cbd2fd220017ba831643986b87ae294774",
        "status": "succeeded",
        "verified_at_utc": "2026-08-19T04:42:25Z",
    }:
        raise ValueError("independent reproduction execution record changed")
    if environment["lock_validation"] != {
        "core_imports": True,
        "empty_environment": True,
        "managed_run_id": "r_de379c28",
        "runtime_packages": 177,
        "status": "succeeded",
    }:
        raise ValueError("independent reproduction lock-validation record changed")
    lock = (root / "requirements-replay-linux-py310.lock").read_text(encoding="utf-8")
    packages = [line for line in lock.splitlines() if line]
    if len(packages) != 177 or len(packages) != len(set(packages)):
        raise ValueError("independent reproduction environment inventory changed")
    for requirement in (
        "jiwer==4.0.0",
        "numpy==1.26.4",
        "pytorch-lightning==2.5.6",
        "rapidfuzz==3.14.5",
        "torch==2.13.0",
    ):
        if requirement not in packages:
            raise ValueError(f"independent reproduction requirement missing: {requirement}")
    return {
        "checksummed": checksummed,
        "managed_run_id": execution["managed_run_id"],
        "runtime_packages": len(packages),
        "records": summary["overall"]["records"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    result = {
        "aggregate": verify_aggregate_snapshot(root / "evidence" / "snapshot-20260819"),
        "predictions": verify_prediction_evidence(root / "evidence" / "predictions-20260819"),
        "reproduction": verify_independent_reproduction(root),
        "valid": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
