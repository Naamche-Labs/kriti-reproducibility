# Reconstructing the frozen development view

This procedure fixes a crucial distinction: a private manifest hash is only a
commitment. It is not enough to let another authorized researcher recover the
same records. The tools here reconstruct the view from pinned upstream sources;
they do not require a copy of the project's private `dev.jsonl`.

Run this procedure only on an authorized data/compute plane with at least 50 GB
of free storage. Never commit the acquired corpora, reconstructed audio,
references, provenance file, or view.

## How the IndicVoices pseudonyms resolve

IndicVoices does not publish a globally unique row ID. Each public `kriti-…`
identifier was derived deterministically from:

1. the Parquet path within pinned IndicVoices revision
   `c96f9088f138cf89d419da7e8e643e1f05c00a87`;
2. the physical row index within that Parquet file;
3. the embedded upstream audio path, when present; and
4. the SHA-256 of the embedded audio bytes.

The resulting source identity is converted to a namespaced UUIDv5 by the public
function in `tools/reconstruction_common.py`. Someone without accepted dataset
access cannot use a pseudonym to retrieve row content. An authorized user can
scan the pinned Parquet files locally, derive every identity, and match exactly
the 2,569 IndicVoices IDs in the public roster.

## Acquire the pinned upstream files

First accept the IndicVoices access conditions using your own Hugging Face
account. Then create an isolated reconstruction environment:

```bash
uv venv --python 3.10 .reconstruct-venv
uv pip sync --python .reconstruct-venv/bin/python \
  requirements-reconstruct-linux-py310.lock
```

The frozen FLEURS normalization used Ubuntu 22.04 FFmpeg
`4.4.2-0ubuntu0.22.04.1` with libsoxr. Install that runtime on the authorized
machine or run in an equivalent pinned Ubuntu 22.04 environment.

Acquire the exact IndicVoices revision, FLEURS development archive, and all
OpenSLR54 archives. Every public artifact is checked against its recorded size
and SHA-256 or upstream MD5 before extraction.

```bash
export HF_TOKEN=YOUR_ACCEPTED_INDICVOICES_TOKEN
.reconstruct-venv/bin/python tools/acquire_view_sources.py \
  --source-root /authorized/authorized-sources
unset HF_TOKEN
```

## Reconstruct and verify the view

```bash
.reconstruct-venv/bin/python tools/reconstruct_view.py \
  --source-root /authorized/authorized-sources \
  --output-dir /authorized/reconstructed-view
```

The reconstruction must independently scan:

- 305 pinned FLEURS development rows;
- 249,422 pinned IndicVoices Nepali rows; and
- 157,905 pinned OpenSLR54 rows.

It must resolve exactly 304, 2,569, and 757 selected rows respectively, with no
missing or extra public IDs. It then checks three independent commitments:

- `selector_sha256`: the ordered upstream-record resolution;
- `semantic_view_sha256`: each ordered sample/source identity, upstream-audio
  hash, decoded PCM hash, frame count, and normalized reference; and
- `portable_view_sha256`: the reconstructed JSONL with relative audio paths.

The frozen values are:

| Commitment | SHA-256 |
|---|---|
| Upstream selector | `03c330561e75ae4aa8b62c15dac1c7aee6a22bae1687ac706b1261769a84c3b3` |
| Semantic view | `aa536153717af74ecb308661959b96e3daa16385310b6031d892440e8d8c2add` |
| Portable view JSONL | `d26afb661b581fbc9fd7fb9f7f594de6bc54d16d023050beb102531b8a8d7611` |

Machine-specific absolute paths are deliberately excluded from these
commitments. The output directory contains private working artifacts:
`view.jsonl`, `provenance.jsonl`, and 3,630 audio files. Keep them outside Git.

## Replay Kriti on the reconstructed view

After successful reconstruction, run the exact inference replay:

```bash
env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN -u HUGGINGFACE_TOKEN \
  HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  .replay-venv/bin/python tools/reproduce_kriti.py \
    --view /authorized/reconstructed-view/view.jsonl \
    --provenance /authorized/reconstructed-view/provenance.jsonl \
    --output-dir /authorized/reproduction-output \
    --device cuda
```

Before model loading, the replay rechecks the portable view hash, decodes every
audio file, verifies every PCM hash and frame count against private provenance,
and recomputes the aggregate semantic commitment. Inference succeeds only if
the resulting prediction hash and every overall/per-source metric exactly match
the public Kriti record.
