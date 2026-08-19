#!/usr/bin/env python3
"""Collect a deterministic, privacy-scanned Kriti evidence bundle.

This script is intended to run beside the private Kriti work root on
JarvisLabs. It copies only allowlisted aggregate records, replaces private
absolute path prefixes, records the SHA-256 of every private source record,
and indexes every SHA-256 commitment present in the public copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+\S+|"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*\S+|"
    r"(?:hf|gh[pousr])_[A-Za-z0-9_-]{16,}|"
    r"x-amz-(?:signature|credential)=|"
    r"[?&]token=[A-Za-z0-9_-]{16,})"
)
SECRET_KEY_RE = re.compile(
    r"(?i)^(?:api[_-]?key|credential|secret|access[_-]?token|auth[_-]?token|password)$"
)
ROW_CONTENT_KEY_RE = re.compile(
    r"(?i)^(?:text|transcript|hypothesis|reference|sample_id|speaker_id|audio_path|predictions)$"
)


@dataclass(frozen=True)
class SourceSpec:
    pattern: str
    classification: str
    description: str


SOURCE_SPECS = (
    SourceSpec(
        "processed/ne-commercial-v1/summary.json",
        "credential-gated-reproducible",
        "Commercial release aggregate accounting",
    ),
    SourceSpec(
        "processed/ne-commercial-v1/validation.json",
        "credential-gated-reproducible",
        "Commercial release independent validation result",
    ),
    SourceSpec(
        "processed/ne-commercial-v1/build-manifest.json",
        "credential-gated-reproducible",
        "Commercial release build manifest",
    ),
    SourceSpec(
        "processed/ne-commercial-v1/checksums.sha256",
        "commitment-verifiable",
        "Commercial release artifact commitments",
    ),
    SourceSpec(
        "processed/ne-research-v1/summary.json",
        "credential-gated-reproducible",
        "Research release aggregate accounting",
    ),
    SourceSpec(
        "processed/ne-research-v1/validation.json",
        "credential-gated-reproducible",
        "Research release independent validation result",
    ),
    SourceSpec(
        "processed/ne-research-v1/build-manifest.json",
        "credential-gated-reproducible",
        "Research release build manifest",
    ),
    SourceSpec(
        "processed/ne-research-v1/checksums.sha256",
        "commitment-verifiable",
        "Research release artifact commitments",
    ),
    SourceSpec(
        "reports/*.json",
        "publicly-verifiable",
        "Redacted aggregate report",
    ),
    SourceSpec(
        "training/runs/kriti-qwen3-commercial-v1-20260812a/selection.json",
        "commitment-verifiable",
        "Historical Qwen checkpoint selection record",
    ),
    SourceSpec(
        "training/runs/kriti-qwen3-commercial-v1-20260812a/views/summary.json",
        "commitment-verifiable",
        "Historical Qwen view summary",
    ),
    SourceSpec(
        "training/runs/kriti-qwen3-commercial-v1-20260812a/sealed-test-view/summary.json",
        "commitment-verifiable",
        "Historical Qwen sealed-test view summary",
    ),
    SourceSpec(
        "training/runs/kriti-qwen3-commercial-v1-20260812a/evaluations/*/summary.json",
        "commitment-verifiable",
        "Historical Qwen evaluation summary",
    ),
    SourceSpec(
        "training/benchmarks/kriti-nepali-asr-major-v1/views/summary.json",
        "commitment-verifiable",
        "Historical v1 benchmark view summary",
    ),
    SourceSpec(
        "training/benchmarks/kriti-nepali-asr-major-v1/evaluations/*/summary.json",
        "commitment-verifiable",
        "Historical v1 benchmark system summary",
    ),
    SourceSpec(
        "training/benchmarks/kriti-nepali-asr-major-v1/smoke/*/summary.json",
        "commitment-verifiable",
        "Historical v1 benchmark smoke summary",
    ),
    SourceSpec(
        "training/benchmarks/kriti-nepali-asr-major-v1/rejected-attempts/**/summary.json",
        "commitment-verifiable",
        "Historical v1 rejected-attempt summary",
    ),
    SourceSpec(
        "training/benchmarks/kriti-nepali-asr-major-v2/contracts/experiment.json",
        "commitment-verifiable",
        "Stopped v2 benchmark contract",
    ),
    SourceSpec(
        "training/benchmarks/kriti-nepali-asr-major-v2/evaluations/**/summary.json",
        "commitment-verifiable",
        "Stopped v2 benchmark replicate summary",
    ),
    SourceSpec(
        "training/benchmarks/rejected-campaigns/**/contracts/experiment.json",
        "commitment-verifiable",
        "Rejected v2 benchmark contract",
    ),
    SourceSpec(
        "training/benchmarks/rejected-campaigns/**/evaluations/**/summary.json",
        "commitment-verifiable",
        "Rejected v2 benchmark replicate summary",
    ),
    SourceSpec(
        "training/compression/kriti-nepali-compression-v1/evaluations/**/summary.json",
        "commitment-verifiable",
        "Compression candidate evaluation summary",
    ),
    SourceSpec(
        "training/compression/kriti-nepali-compression-v1/rejected-attempts/**/summary.json",
        "commitment-verifiable",
        "Compression rejected-attempt summary",
    ),
    SourceSpec(
        "training/compression/kriti-nepali-compression-v1/vocabulary-analysis-*/summary.json",
        "commitment-verifiable",
        "Compression vocabulary analysis summary",
    ),
    SourceSpec(
        "training/public-release-validations/**/summary.json",
        "publicly-verifiable",
        "Public release validation summary",
    ),
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def json_pointer(parts: tuple[str, ...]) -> str:
    if not parts:
        return ""
    escaped = [part.replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped)


def sanitize_json(
    value: Any,
    *,
    path: tuple[str, ...],
    source_root: str,
    redactions: list[dict[str, str]],
) -> Any:
    key = path[-1] if path else ""
    if SECRET_KEY_RE.match(key) and value not in (None, "", [], {}):
        raise ValueError(f"secret-bearing key rejected at {json_pointer(path)}")
    if ROW_CONTENT_KEY_RE.match(key) and value not in (None, "", [], {}):
        raise ValueError(f"row-level content key rejected at {json_pointer(path)}")

    if isinstance(value, dict):
        return {
            str(child_key): sanitize_json(
                child_value,
                path=path + (str(child_key),),
                source_root=source_root,
                redactions=redactions,
            )
            for child_key, child_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [
            sanitize_json(
                child,
                path=path + (str(index),),
                source_root=source_root,
                redactions=redactions,
            )
            for index, child in enumerate(value)
        ]
    if not isinstance(value, str):
        return value

    if SECRET_VALUE_RE.search(value):
        raise ValueError(f"secret-like value rejected at {json_pointer(path)}")
    if "?" in value and value.startswith(("http://", "https://")):
        raise ValueError(f"query-bearing URL rejected at {json_pointer(path)}")

    replacements = (
        (source_root.rstrip("/"), "$KRITI_ROOT"),
        ("/home/kriti", "$REMOTE_CONTROL_ROOT"),
        ("/home/", "$REMOTE_HOME/"),
    )
    sanitized = value
    for old, new in replacements:
        if old in sanitized:
            sanitized = sanitized.replace(old, new)
            redactions.append({"json_pointer": json_pointer(path), "replacement": new})
    return sanitized


def find_commitments(value: Any, path: tuple[str, ...] = ()) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in sorted(value.items(), key=lambda item: str(item[0])):
            found.extend(find_commitments(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_commitments(child, path + (str(index),)))
    elif isinstance(value, str) and SHA256_RE.fullmatch(value):
        found.append({"json_pointer": json_pointer(path), "sha256": value})
    return found


def parse_checksum_commitments(payload: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        digest, separator, name = line.partition("  ")
        if not separator or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"invalid checksum line {line_number}")
        normalized = PurePosixPath(name)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"unsafe checksum name on line {line_number}")
        found.append(
            {
                "json_pointer": f"line:{line_number}:{name}",
                "sha256": digest,
            }
        )
    return found


def resolve_sources(root: Path) -> list[tuple[Path, SourceSpec]]:
    resolved: dict[Path, SourceSpec] = {}
    for spec in SOURCE_SPECS:
        for path in sorted(root.glob(spec.pattern)):
            if path.is_file():
                resolved.setdefault(path, spec)
    return sorted(resolved.items(), key=lambda item: item[0].relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    args = parser.parse_args()

    source_root = args.source_root.resolve(strict=True)
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    args.output.mkdir(parents=True)
    records_root = args.output / "records"
    records_root.mkdir()

    sources = resolve_sources(source_root)
    if not sources:
        raise SystemExit("no allowlisted evidence records found")

    records: list[dict[str, Any]] = []
    commitments: list[dict[str, str]] = []
    for source_path, spec in sources:
        relative = source_path.relative_to(source_root).as_posix()
        source_bytes = source_path.read_bytes()
        if len(source_bytes) > 2_000_000:
            raise ValueError(f"record exceeds 2 MB allowlist ceiling: {relative}")

        redactions: list[dict[str, str]] = []
        if source_path.suffix == ".json":
            parsed = json.loads(source_bytes)
            sanitized = sanitize_json(
                parsed,
                path=(),
                source_root=source_root.as_posix(),
                redactions=redactions,
            )
            public_bytes = (
                json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            record_commitments = find_commitments(sanitized)
        elif source_path.name.endswith(".sha256"):
            text = source_bytes.decode("utf-8")
            if SECRET_VALUE_RE.search(text):
                raise ValueError(f"secret-like checksum record rejected: {relative}")
            public_bytes = (text.rstrip("\n") + "\n").encode("utf-8")
            record_commitments = parse_checksum_commitments(public_bytes.decode("utf-8"))
        else:
            raise ValueError(f"unsupported evidence type: {relative}")

        destination = records_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(public_bytes)
        public_path = destination.relative_to(args.output).as_posix()

        records.append(
            {
                "classification": spec.classification,
                "description": spec.description,
                "public_bytes": len(public_bytes),
                "public_path": public_path,
                "public_sha256": sha256_bytes(public_bytes),
                "redactions": redactions,
                "source_bytes": len(source_bytes),
                "source_sha256": sha256_bytes(source_bytes),
                "source_uri": f"kriti-private://{relative}",
            }
        )
        for commitment in record_commitments:
            commitments.append(
                {
                    "record": public_path,
                    "location": commitment["json_pointer"],
                    "sha256": commitment["sha256"],
                }
            )

    records.sort(key=lambda item: item["public_path"])
    commitments.sort(key=lambda item: (item["sha256"], item["record"], item["location"]))
    unique_commitments: list[dict[str, str]] = []
    seen_commitments: set[tuple[str, str, str]] = set()
    for item in commitments:
        identity = (item["sha256"], item["record"], item["location"])
        if identity not in seen_commitments:
            seen_commitments.add(identity)
            unique_commitments.append(item)

    index = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": args.recorded_at,
        "source_root": "$KRITI_ROOT",
        "records": records,
    }
    commitments_document = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": "sha256",
        "meaning": (
            "Each item locates a SHA-256 commitment in an allowlisted aggregate record. "
            "A digest is public evidence of identity, not proof that a private subject is "
            "publicly downloadable."
        ),
        "commitments": unique_commitments,
    }
    (args.output / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output / "commitments.json").write_text(
        json.dumps(commitments_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": args.recorded_at,
        "records_collected": len(records),
        "commitments_indexed": len(unique_commitments),
        "privacy_scan": {
            "query_bearing_urls_allowed": 0,
            "row_level_content_allowed": 0,
            "secret_bearing_values_allowed": 0,
        },
    }
    (args.output / "collection-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(Path(__file__), args.output / "collect_evidence.py")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
