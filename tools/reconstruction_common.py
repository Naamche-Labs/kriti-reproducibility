"""Shared deterministic identities and semantic commitments for view reconstruction."""

from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np
import soundfile as sf

SOURCE_ID = "indicvoices_nepali"
SAMPLE_ID_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://kriti.local/schemas/nepali-asr/sample/v1",
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_sample_id(source_id: str, source_record_id: str) -> str:
    """Reproduce the public path-independent Kriti UUIDv5 sample identity."""

    name = json.dumps([source_id, source_record_id], ensure_ascii=False, separators=(",", ":"))
    return f"kriti-{uuid.uuid5(SAMPLE_ID_NAMESPACE, name).hex}"


def indicvoices_identity(
    *,
    repository_relative_path: str,
    parquet_row_index: int,
    upstream_path: str | None,
    audio_sha256: str,
) -> tuple[str, str]:
    """Derive the stable record/sample IDs without publishing gated row metadata."""

    filename = Path(repository_relative_path).name
    split = (
        "valid"
        if filename.startswith("valid-")
        else "train"
        if filename.startswith("train-")
        else Path(repository_relative_path).parent.name
    )
    identity_payload = json.dumps(
        [repository_relative_path, parquet_row_index, upstream_path, audio_sha256],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    source_record_id = f"{split}:{hashlib.sha256(identity_payload).hexdigest()[:32]}"
    return source_record_id, stable_sample_id(SOURCE_ID, source_record_id)


def audio_payload(value: Any) -> tuple[bytes, str | None]:
    if isinstance(value, dict):
        payload = value.get("bytes")
        path = value.get("path")
        if isinstance(payload, memoryview):
            payload = payload.tobytes()
        if isinstance(payload, bytearray):
            payload = bytes(payload)
        if not isinstance(payload, bytes):
            raise ValueError("embedded audio struct has no byte payload")
        return payload, path if isinstance(path, str) else None
    if isinstance(value, memoryview):
        return value.tobytes(), None
    if isinstance(value, bytearray):
        return bytes(value), None
    if isinstance(value, bytes):
        return value, None
    raise ValueError(f"unsupported embedded audio value: {type(value).__name__}")


def normalize_reference(value: str) -> str:
    """Apply the frozen conservative Nepali text normalization profile."""

    if not isinstance(value, str):
        raise TypeError("reference must be a string")
    preserved = {"\u200c", "\u200d"}
    cleaned: list[str] = []
    for character in value:
        category = unicodedata.category(character)
        is_whitespace = character.isspace() or category in {"Zs", "Zl", "Zp"}
        if character == "\ufeff":
            continue
        if character in preserved or is_whitespace or category not in {"Cc", "Cf", "Cs"}:
            cleaned.append(character)
    output: list[str] = []
    in_whitespace = True
    for character in cleaned:
        category = unicodedata.category(character)
        if character.isspace() or category in {"Zs", "Zl", "Zp"}:
            if not in_whitespace:
                output.append(" ")
            in_whitespace = True
        else:
            output.append(character)
            in_whitespace = False
    if output and output[-1] == " ":
        output.pop()
    return unicodedata.normalize("NFC", "".join(output))


def _pcm_summary(handle: sf.SoundFile | BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    frames = 0
    with sf.SoundFile(handle) as audio:
        if audio.samplerate != 16_000 or audio.channels != 1 or audio.subtype != "PCM_16":
            raise ValueError("audio is not canonical 16 kHz mono PCM-16")
        for block in audio.blocks(blocksize=65_536, dtype="int16", always_2d=True):
            mono = np.ascontiguousarray(block[:, 0], dtype=np.int16)
            digest.update(mono.astype("<i2", copy=False).tobytes(order="C"))
            frames += int(mono.size)
    if frames <= 0:
        raise ValueError("audio decoded zero frames")
    return digest.hexdigest(), frames


def pcm_summary(path: Path) -> tuple[str, int]:
    return _pcm_summary(path)


def semantic_view_sha256(rows: list[dict[str, Any]]) -> str:
    """Hash ordered, path-independent row semantics with an explicit domain tag."""

    digest = hashlib.sha256(b"kriti-semantic-view-v1\0")
    for row in sorted(rows, key=lambda item: int(item["ordinal"])):
        payload = {
            "num_frames": int(row["num_frames"]),
            "ordinal": int(row["ordinal"]),
            "pcm_sha256": str(row["pcm_sha256"]),
            "reference": str(row["reference"]),
            "sample_id": str(row["sample_id"]),
            "source_audio_sha256": str(row["source_audio_sha256"]),
            "source_id": str(row["source_id"]),
        }
        digest.update(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()
