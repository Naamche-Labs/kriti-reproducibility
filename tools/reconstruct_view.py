#!/usr/bin/env python3
"""Reconstruct the exact Kriti dev selection from pinned upstream source files.

Run this only in an authorized data environment. The generated view, audio, and
references are private working artifacts and must not be committed here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from reconstruction_common import (
    audio_payload,
    indicvoices_identity,
    normalize_reference,
    pcm_summary,
    semantic_view_sha256,
    sha256_bytes,
    sha256_file,
    stable_sample_id,
)

EXPECTED_SOURCE_COUNTS = {
    "fleurs_ne_np": 304,
    "indicvoices_nepali": 2_569,
    "openslr54": 757,
}
EXPECTED_SCANNED_COUNTS = {
    "fleurs_ne_np": 305,
    "indicvoices_nepali": 249_422,
    "openslr54": 157_905,
}
TARGET_PREFIX = "language Nepali<asr_text>"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _load_roster(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        roster = [json.loads(line) for line in handle]
    if len(roster) != 3_630 or [row["ordinal"] for row in roster] != list(range(3_630)):
        raise ValueError("public roster is not the exact ordered 3,630-row record")
    if Counter(row["source_id"] for row in roster) != Counter(EXPECTED_SOURCE_COUNTS):
        raise ValueError("public roster source counts differ")
    by_id = {str(row["sample_id"]): row for row in roster}
    if len(by_id) != len(roster):
        raise ValueError("public roster sample IDs are not unique")
    return roster, by_id


def _audio_index(root: Path, extensions: set[str]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if path.stem in index:
            raise ValueError(f"duplicate upstream audio stem: {path.stem}")
        index[path.stem] = path
    return index


def _ffmpeg_version() -> str:
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.splitlines()[0]


def _normalize_fleurs(source: Path, destination: Path) -> None:
    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        "-af",
        "aresample=osr=16000:resampler=soxr:precision=28",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        "-c:a",
        "flac",
        "-compression_level",
        "5",
        "-threads",
        "1",
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:a",
        "+bitexact",
        "-y",
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if completed.returncode:
        raise RuntimeError(f"FFmpeg failed for {source.name}: {completed.stderr[-800:]}")


def _materialize(
    *,
    source: Path,
    destination: Path,
    normalize_with_ffmpeg: bool,
) -> tuple[str, str, int]:
    source_sha256 = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if normalize_with_ffmpeg:
        _normalize_fleurs(source, destination)
    else:
        shutil.copyfile(source, destination)
    pcm_sha256, num_frames = pcm_summary(destination)
    return source_sha256, pcm_sha256, num_frames


def _row(
    *,
    roster_row: dict[str, Any],
    reference: str,
    relative_audio: str,
    source_audio_sha256: str,
    pcm_sha256: str,
    num_frames: int,
    selector: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    semantic = {
        "ordinal": int(roster_row["ordinal"]),
        "sample_id": str(roster_row["sample_id"]),
        "source_id": str(roster_row["source_id"]),
        "source_audio_sha256": source_audio_sha256,
        "pcm_sha256": pcm_sha256,
        "num_frames": num_frames,
        "reference": reference,
    }
    view = {
        "audio": relative_audio,
        "text": f"{TARGET_PREFIX}{reference}",
        "reference": reference,
        "sample_id": semantic["sample_id"],
        "source_id": semantic["source_id"],
        "num_frames": num_frames,
    }
    selector_record = {
        "ordinal": semantic["ordinal"],
        "sample_id": semantic["sample_id"],
        "source_id": semantic["source_id"],
        "source_audio_sha256": source_audio_sha256,
        **selector,
    }
    return semantic, view, selector_record


def _reconstruct_fleurs(
    raw_root: Path,
    stage: Path,
    roster_by_id: dict[str, dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]], int]:
    metadata = raw_root / "metadata" / "dev.tsv"
    audio = _audio_index(raw_root / "extracted", {".wav"})
    output = []
    scanned = 0
    with metadata.open(encoding="utf-8", newline="") as handle:
        for row_number, values in enumerate(
            csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE), start=1
        ):
            if len(values) != 7:
                raise ValueError(f"invalid FLEURS dev TSV row {row_number}")
            _, filename, raw_text, _, _, _, _ = values
            record_id = Path(filename).stem
            sample_id = stable_sample_id("fleurs_ne_np", record_id)
            scanned += 1
            roster_row = roster_by_id.get(sample_id)
            if roster_row is None:
                continue
            source = audio[record_id]
            relative_audio = f"audio/{sample_id}.flac"
            source_sha, pcm_sha, frames = _materialize(
                source=source,
                destination=stage / relative_audio,
                normalize_with_ffmpeg=True,
            )
            output.append(
                _row(
                    roster_row=roster_row,
                    reference=normalize_reference(raw_text),
                    relative_audio=relative_audio,
                    source_audio_sha256=source_sha,
                    pcm_sha256=pcm_sha,
                    num_frames=frames,
                    selector={"upstream_record_id": record_id},
                )
            )
    return output, scanned


def _reconstruct_openslr54(
    raw_root: Path,
    stage: Path,
    roster_by_id: dict[str, dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]], int]:
    metadata = raw_root / "metadata" / "utt_spk_text.tsv"
    audio = _audio_index(raw_root / "extracted", {".flac"})
    output = []
    scanned = 0
    with metadata.open(encoding="utf-8", newline="") as handle:
        for row_number, values in enumerate(
            csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE), start=1
        ):
            if len(values) != 3:
                raise ValueError(f"invalid OpenSLR54 TSV row {row_number}")
            record_id, _, raw_text = values
            sample_id = stable_sample_id("openslr54", record_id)
            scanned += 1
            roster_row = roster_by_id.get(sample_id)
            if roster_row is None:
                continue
            source = audio[record_id]
            relative_audio = f"audio/{sample_id}.flac"
            source_sha, pcm_sha, frames = _materialize(
                source=source,
                destination=stage / relative_audio,
                normalize_with_ffmpeg=False,
            )
            output.append(
                _row(
                    roster_row=roster_row,
                    reference=normalize_reference(raw_text),
                    relative_audio=relative_audio,
                    source_audio_sha256=source_sha,
                    pcm_sha256=pcm_sha,
                    num_frames=frames,
                    selector={"upstream_record_id": record_id},
                )
            )
    return output, scanned


def _reconstruct_indicvoices(
    repository: Path,
    stage: Path,
    roster_by_id: dict[str, dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]], int]:
    parquet_files = sorted(repository.rglob("*.parquet"))
    if len(parquet_files) != 74:
        raise ValueError(f"expected 74 IndicVoices Parquet files, found {len(parquet_files)}")
    output = []
    total_rows = 0
    for parquet_path in parquet_files:
        relative_path = parquet_path.relative_to(repository).as_posix()
        parquet = pq.ParquetFile(parquet_path)
        required = {"audio_filepath", "verbatim"}
        if not required <= set(parquet.schema_arrow.names):
            raise ValueError(f"IndicVoices file lacks required columns: {relative_path}")
        parquet_row_index = 0
        for batch in parquet.iter_batches(batch_size=128, columns=["audio_filepath", "verbatim"]):
            for upstream_row in batch.to_pylist():
                payload, upstream_path = audio_payload(upstream_row["audio_filepath"])
                audio_sha = sha256_bytes(payload)
                _, sample_id = indicvoices_identity(
                    repository_relative_path=relative_path,
                    parquet_row_index=parquet_row_index,
                    upstream_path=upstream_path,
                    audio_sha256=audio_sha,
                )
                roster_row = roster_by_id.get(sample_id)
                if roster_row is not None:
                    suffix = Path(upstream_path).suffix.lower() if upstream_path else ".flac"
                    if suffix not in {".flac", ".wav", ".mp3", ".ogg", ".opus", ".m4a"}:
                        suffix = ".flac"
                    with tempfile.NamedTemporaryFile(
                        dir=stage,
                        prefix=".indic-source-",
                        suffix=suffix,
                        delete=False,
                    ) as temporary:
                        temporary.write(payload)
                        source = Path(temporary.name)
                    try:
                        relative_audio = f"audio/{sample_id}.flac"
                        source_sha, pcm_sha, frames = _materialize(
                            source=source,
                            destination=stage / relative_audio,
                            normalize_with_ffmpeg=False,
                        )
                    finally:
                        source.unlink(missing_ok=True)
                    if source_sha != audio_sha:
                        raise ValueError(
                            "IndicVoices embedded-audio hash changed while materializing"
                        )
                    output.append(
                        _row(
                            roster_row=roster_row,
                            reference=normalize_reference(str(upstream_row["verbatim"])),
                            relative_audio=relative_audio,
                            source_audio_sha256=source_sha,
                            pcm_sha256=pcm_sha,
                            num_frames=frames,
                            selector={
                                "parquet_row_index": parquet_row_index,
                                "repository_relative_path": relative_path,
                            },
                        )
                    )
                parquet_row_index += 1
                total_rows += 1
    return output, total_rows


def _selector_sha256(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(b"kriti-upstream-selector-v1\0")
    for row in sorted(rows, key=lambda item: int(item["ordinal"])):
        digest.update(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--source-root", type=Path, required=True)
    parser.add_argument("-o", "--output-dir", type=Path, required=True)
    parser.add_argument(
        "-r",
        "--roster",
        type=Path,
        default=root / "evidence" / "predictions-20260819" / "view" / "ordered-sample-ids.jsonl",
    )
    parser.add_argument(
        "-c",
        "--contract",
        type=Path,
        default=root / "evidence" / "reconstruction-20260819" / "contract.json",
    )
    args = parser.parse_args()
    source_root = args.source_root.resolve(strict=True)
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite reconstruction: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    roster, roster_by_id = _load_roster(args.roster.resolve(strict=True))
    contract = _read_json(args.contract.resolve(strict=True))
    results = []
    scanned: dict[str, int] = {}
    ffmpeg_version = _ffmpeg_version()
    fleurs, scanned["fleurs_ne_np"] = _reconstruct_fleurs(
        source_root / "raw" / "fleurs_ne_np", stage, roster_by_id
    )
    results.extend(fleurs)
    openslr, scanned["openslr54"] = _reconstruct_openslr54(
        source_root / "raw" / "openslr54", stage, roster_by_id
    )
    results.extend(openslr)
    indic, scanned["indicvoices_nepali"] = _reconstruct_indicvoices(
        source_root / "raw" / "indicvoices_nepali" / "repository", stage, roster_by_id
    )
    results.extend(indic)
    if scanned != EXPECTED_SCANNED_COUNTS:
        raise ValueError(f"upstream row counts differ: {scanned}")
    semantic_rows = [item[0] for item in results]
    view_by_id = {item[1]["sample_id"]: item[1] for item in results}
    selector_rows = [item[2] for item in results]
    if len(view_by_id) != 3_630 or set(view_by_id) != set(roster_by_id):
        missing = len(set(roster_by_id) - set(view_by_id))
        extra = len(set(view_by_id) - set(roster_by_id))
        raise ValueError(f"reconstructed selection differs: missing={missing} extra={extra}")
    source_counts = Counter(row["source_id"] for row in semantic_rows)
    if source_counts != Counter(EXPECTED_SOURCE_COUNTS):
        raise ValueError(f"reconstructed source counts differ: {source_counts}")
    view_path = stage / "view.jsonl"
    provenance_path = stage / "provenance.jsonl"
    with view_path.open("w", encoding="utf-8", newline="\n") as handle:
        for roster_row in roster:
            handle.write(
                json.dumps(
                    view_by_id[roster_row["sample_id"]],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
    with provenance_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in sorted(semantic_rows, key=lambda item: int(item["ordinal"])):
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            )
    summary = {
        "schema_version": 1,
        "contract": "kriti-authorized-upstream-reconstruction-v1",
        "records": len(semantic_rows),
        "source_records": dict(sorted(source_counts.items())),
        "upstream_rows_scanned": dict(sorted(scanned.items())),
        "semantic_view_sha256": semantic_view_sha256(semantic_rows),
        "selector_sha256": _selector_sha256(selector_rows),
        "portable_view_sha256": sha256_file(view_path),
        "private_provenance_sha256": sha256_file(provenance_path),
        "ffmpeg_version": ffmpeg_version,
        "indicvoices_identity": "parquet-path+physical-row-index+upstream-path+audio-sha256/v1",
        "private_artifacts_published": False,
        "valid": True,
    }
    for field in (
        "semantic_view_sha256",
        "selector_sha256",
        "portable_view_sha256",
        "private_provenance_sha256",
    ):
        if summary[field] != contract[field]:
            raise ValueError(f"reconstructed {field} differs from the public contract")
    if summary["source_records"] != contract["source_records"]:
        raise ValueError("reconstructed source counts differ from the public contract")
    (stage / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(stage, output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
