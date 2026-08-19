#!/usr/bin/env python3
"""Run and strictly validate a complete authorized Kriti dev-view replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from kriti import KritiASR
from kriti.metrics import metric_set

MODEL_ID = "harrrshall/kriti"
MODEL_REVISION = "762d1c17edaff0a548f3483e37e491fe8cc77971"
EXPECTED_VIEW_SHA256 = "2374cac54831ce9c69282503763d7f1e12ada0404ae34ed471a7538cdae6c61f"
EXPECTED_PREDICTIONS_SHA256 = "1a42d4b0b527f2c21a4a28dfa84e7a2d769762bc4a6d80c59a12821e85b89f0f"
EXPECTED_SOURCE_COUNTS = {
    "fleurs_ne_np": 304,
    "indicvoices_nepali": 2_569,
    "openslr54": 757,
}
EXPECTED_MODEL_SHA256 = "0144854f0cc78f4b6115b75089fad632c39207d5256e53f92da996b9bbe43582"
EXPECTED_HEAD_SHA256 = "5874b6fc6b4f1172dffa249a42f5054ffe196cff9b97854fe180eafc4134e9bb"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if not all(isinstance(row, dict) for row in rows):
        raise RuntimeError(f"expected JSON objects in {path}")
    return rows


def verify_view(view_path: Path, roster_path: Path) -> list[dict[str, Any]]:
    if sha256(view_path) != EXPECTED_VIEW_SHA256:
        raise RuntimeError("view SHA-256 differs from the frozen benchmark")
    rows = read_jsonl(view_path)
    if len(rows) != 3_630:
        raise RuntimeError("view must contain exactly 3,630 rows")
    required = {"sample_id", "source_id", "audio", "reference"}
    if any(not required.issubset(row) for row in rows):
        raise RuntimeError("view row lacks a required field")
    if len({str(row["sample_id"]) for row in rows}) != len(rows):
        raise RuntimeError("view sample IDs are not unique")
    if Counter(str(row["source_id"]) for row in rows) != Counter(EXPECTED_SOURCE_COUNTS):
        raise RuntimeError("view source composition differs from the frozen benchmark")
    roster = read_jsonl(roster_path)
    expected_identity = [(row["sample_id"], row["source_id"]) for row in roster]
    actual_identity = [(row["sample_id"], row["source_id"]) for row in rows]
    if actual_identity != expected_identity:
        raise RuntimeError("ordered view identity differs from the public roster")
    return rows


def exact_metrics() -> dict[str, Any]:
    evidence = Path(__file__).resolve().parents[1] / "evidence" / "predictions-20260819"
    payload = json.loads((evidence / "metrics" / "per-source.json").read_text(encoding="utf-8"))
    return next(system for system in payload["systems"] if system["key"] == "kriti")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.batch_size <= 0:
        raise ValueError("batch size must be positive")
    root = Path(__file__).resolve().parents[1]
    roster = root / "evidence" / "predictions-20260819" / "view" / "ordered-sample-ids.jsonl"
    view = args.view.resolve(strict=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = verify_view(view, roster)

    model = KritiASR.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        device=args.device,
        token=False,
        cache_dir=os.environ.get("HF_HOME"),
    )
    hypotheses = model.transcribe([str(row["audio"]) for row in rows], batch_size=args.batch_size)
    if len(hypotheses) != len(rows):
        raise RuntimeError("inference did not return one prediction per row")

    predictions = output / "predictions.jsonl"
    temporary = output / ".predictions.jsonl.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        for row, hypothesis in zip(rows, hypotheses, strict=True):
            payload = {
                "sample_id": row["sample_id"],
                "source_id": row["source_id"],
                "reference": row["reference"],
                "hypothesis": hypothesis,
                "error_type": "",
            }
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(temporary, predictions)

    overall = metric_set(
        [str(row["reference"]) for row in rows],
        [str(hypothesis) for hypothesis in hypotheses],
    )
    per_source: dict[str, dict[str, float | int]] = {}
    for source_id in EXPECTED_SOURCE_COUNTS:
        indices = [index for index, row in enumerate(rows) if row["source_id"] == source_id]
        per_source[source_id] = metric_set(
            [str(rows[index]["reference"]) for index in indices],
            [str(hypotheses[index]) for index in indices],
        )

    expected = exact_metrics()
    prediction_hash = sha256(predictions)
    checks = {
        "artifact_hashes_enforced_by_loader": {
            "kriti.nemo": EXPECTED_MODEL_SHA256,
            "punctuation_head.json": EXPECTED_HEAD_SHA256,
        },
        "overall_exact_match": overall == expected["overall"],
        "per_source_exact_match": per_source == expected["per_source"],
        "predictions_sha256_match": prediction_hash == EXPECTED_PREDICTIONS_SHA256,
        "view_sha256_match": sha256(view) == EXPECTED_VIEW_SHA256,
    }
    report = {
        "schema_version": 1,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "view_sha256": sha256(view),
        "predictions_sha256": prediction_hash,
        "overall": overall,
        "per_source": per_source,
        "checks": checks,
        "protected_test_accessed": False,
        "valid": all(
            checks[name]
            for name in (
                "overall_exact_match",
                "per_source_exact_match",
                "predictions_sha256_match",
                "view_sha256_match",
            )
        ),
    }
    if not report["valid"]:
        raise RuntimeError(json.dumps(report, sort_keys=True))
    (output / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
