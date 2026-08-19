#!/usr/bin/env python3
"""Acquire the three pinned upstream sources needed to reconstruct the dev view."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
from huggingface_hub import snapshot_download

INDICVOICES_REVISION = "c96f9088f138cf89d419da7e8e643e1f05c00a87"
FLEURS_REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
FLEURS_BASE = f"https://huggingface.co/datasets/google/fleurs/resolve/{FLEURS_REVISION}/data/ne_np"


@dataclass(frozen=True)
class Artifact:
    url: str
    relative_path: str
    expected_bytes: int
    sha256: str | None = None
    md5: str | None = None


FLEURS = (
    Artifact(
        f"{FLEURS_BASE}/dev.tsv",
        "raw/fleurs_ne_np/metadata/dev.tsv",
        327_695,
        sha256="af9cbf48a74e91d313d25452fa4be46e612887503233e34b21d403f91991203b",
    ),
    Artifact(
        f"{FLEURS_BASE}/audio/dev.tar.gz",
        "raw/fleurs_ne_np/archives/dev.tar.gz",
        174_279_504,
        sha256="fc1e048e8a56c2c48e882dbdafc378019c1ef3f5f29b2d700608bf9f2e203908",
    ),
)

OPENSLR_ARCHIVES = {
    "0": (589_002_210, "965785fb110788e9b36c16f6b4ced324"),
    "1": (582_088_242, "5fc295f8fd63c2758ec5f02e00b49f4b"),
    "2": (589_401_540, "9a2178658c6cf4ec650adbc070a55d1d"),
    "3": (574_596_426, "6c01c5b09e2950d493092a0023ce82ce"),
    "4": (583_746_586, "5e35d3a95c854c8c388a4b69593763e2"),
    "5": (572_967_016, "5c4040a87c71f255521007d4f55fb185"),
    "6": (588_104_006, "c3f3831903f2bee417bac0f919a53b67"),
    "7": (588_410_232, "ed2688f835991b6f17f28d8e653290a1"),
    "8": (585_192_213, "4468433edd6e18ddc59e810681bb1815"),
    "9": (578_834_881, "a5d835013dc1c8e09959da5c9483a0a9"),
    "a": (587_798_317, "b6f10c519e30311b4dbb4fb4dbb588bc"),
    "b": (584_397_714, "917d6f0dcf1b15f37e53b848d756c331"),
    "c": (579_440_365, "0d842eab566473066aabcdf927cf14ed"),
    "d": (588_470_094, "249d5a65ddc953ae39848cb3ba44c443"),
    "e": (578_091_869, "e4f9af1028316c42f59ac3ca27131c22"),
    "f": (577_705_651, "607d0ffd83de8ad85ed020a20f819cc5"),
}
OPENSLR = (
    Artifact(
        "https://www.openslr.org/resources/54/utt_spk_text.tsv",
        "raw/openslr54/metadata/utt_spk_text.tsv",
        10_883_770,
        sha256="2e4379f4799a280ef71150bce91dc629cc87e89ae344db1ec1575b00c76740fa",
    ),
    *(
        Artifact(
            f"https://www.openslr.org/resources/54/asr_nepali_{part}.zip",
            f"raw/openslr54/archives/asr_nepali_{part}.zip",
            size,
            md5=md5,
        )
        for part, (size, md5) in OPENSLR_ARCHIVES.items()
    ),
)


def _digests(path: Path) -> tuple[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def _verify(path: Path, artifact: Artifact) -> None:
    if path.stat().st_size != artifact.expected_bytes:
        raise ValueError(f"size mismatch: {path}")
    sha256, md5 = _digests(path)
    if artifact.sha256 is not None and sha256 != artifact.sha256:
        raise ValueError(f"SHA-256 mismatch: {path}")
    if artifact.md5 is not None and md5 != artifact.md5:
        raise ValueError(f"MD5 mismatch: {path}")


def _download(root: Path, artifact: Artifact) -> Path:
    destination = (root / artifact.relative_path).resolve()
    destination.relative_to(root.resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        _verify(destination, artifact)
        return destination
    partial = destination.with_name(destination.name + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with requests.get(
        artifact.url,
        headers=headers,
        stream=True,
        timeout=(20, 120),
        allow_redirects=True,
    ) as response:
        if offset and response.status_code == 200:
            partial.unlink()
            offset = 0
        elif offset and response.status_code != 206:
            raise RuntimeError(f"server rejected resume: {artifact.url}")
        elif not offset and response.status_code not in {200, 206}:
            raise RuntimeError(f"download failed HTTP {response.status_code}: {artifact.url}")
        mode = "ab" if offset else "wb"
        with partial.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                if chunk:
                    handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    _verify(partial, artifact)
    os.replace(partial, destination)
    return destination


def _safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    target.relative_to(root.resolve())
    return target


def _extract_tar(archive: Path, destination: Path) -> None:
    if destination.exists():
        return
    stage = destination.with_name(destination.name + ".partial")
    stage.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle.getmembers():
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise ValueError(f"unsafe tar member type: {member.name}")
            _safe_target(stage, member.name)
        handle.extractall(stage)
    os.replace(stage, destination)


def _extract_zip(archive: Path, destination: Path) -> None:
    marker = destination / f".{archive.stem}.complete"
    if marker.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f"unsafe zip symlink: {member.filename}")
            target = _safe_target(destination, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
    marker.write_text("verified\n", encoding="utf-8")


def _read_access_token(token_file: Path | None) -> str | None:
    token = (
        token_file.read_text(encoding="utf-8").strip()
        if token_file is not None
        else os.environ.get("HF_TOKEN")
    )
    return token or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--source-root", type=Path, required=True)
    parser.add_argument("-t", "--token-file", type=Path)
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=("fleurs_ne_np", "indicvoices_nepali", "openslr54"),
        default=("fleurs_ne_np", "indicvoices_nepali", "openslr54"),
    )
    args = parser.parse_args()
    root = args.source_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    selected = set(args.sources)
    if "fleurs_ne_np" in selected:
        paths = [_download(root, artifact) for artifact in FLEURS]
        archive = next(path for path in paths if path.name == "dev.tar.gz")
        _extract_tar(archive, root / "raw" / "fleurs_ne_np" / "extracted" / archive.name)
    if "openslr54" in selected:
        paths = [_download(root, artifact) for artifact in OPENSLR]
        extracted = root / "raw" / "openslr54" / "extracted"
        for archive in paths:
            if archive.suffix == ".zip":
                _extract_zip(archive, extracted)
    if "indicvoices_nepali" in selected:
        token = _read_access_token(args.token_file)
        if not token:
            raise RuntimeError(
                "a token file or HF_TOKEN is required after accepting IndicVoices access conditions"
            )
        repository = root / "raw" / "indicvoices_nepali" / "repository"
        snapshot_download(
            repo_id="ai4bharat/IndicVoices",
            repo_type="dataset",
            revision=INDICVOICES_REVISION,
            allow_patterns=["nepali/*.parquet"],
            local_dir=repository,
            token=token,
        )
        parquet_files = sorted(repository.rglob("*.parquet"))
        if len(parquet_files) != 74:
            raise ValueError(f"expected 74 IndicVoices Parquet files, found {len(parquet_files)}")
    print("Pinned source acquisition completed and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
