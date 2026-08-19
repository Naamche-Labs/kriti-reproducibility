# Reproducing the Kriti result

There are two different reproducibility levels. They should not be conflated.

## Level A: public evidence replay

This level needs only Python 3.10 or newer. It proves that the published files
are intact, the roster is complete and internally consistent, no gated content
crossed the declared boundary, and all redistributable per-source scores match
the row-level predictions.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python tools/verify_evidence.py
```

The verifier must end with `"valid": true`. CI runs the same command from a
fresh checkout.

## Level B: authorized complete inference replay

This level additionally needs accepted access to AI4Bharat IndicVoices and a
GPU. Do not put corpus audio, transcripts, private paths, or full predictions in
this repository. The released Kriti model itself is public and does not require
a Hugging Face token.

The input must be the frozen development JSONL with this exact contract:

- SHA-256: `2374cac54831ce9c69282503763d7f1e12ada0404ae34ed471a7538cdae6c61f`
- 3,630 unique ordered rows
- required fields: `sample_id`, `source_id`, `audio`, `reference`
- source counts: FLEURS 304, IndicVoices 2,569, OpenSLR54 757
- ordered `(sample_id, source_id)` pairs identical to the public roster
- protected test data absent

Create an isolated runtime on the authorized data/compute plane. The following
uses `uv` and the exact 177-package Linux/Python 3.10 inventory from the
successful independent replay:

```bash
uv venv --python 3.10 .replay-venv
uv pip sync --python .replay-venv/bin/python \
  requirements-replay-linux-py310.lock
env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN -u HUGGINGFACE_TOKEN \
  HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  .replay-venv/bin/python tools/reproduce_kriti.py \
    --view /authorized/path/dev.jsonl \
    --output-dir /authorized/path/reproduction-output \
    --device cuda
```

The script refuses a view with a different byte hash, order, identity, or
source composition. It loads `harrrshall/kriti` at immutable Hugging Face
revision `762d1c17edaff0a548f3483e37e491fe8cc77971`; the model package verifies
the two downloaded artifact hashes before inference. It writes predictions
atomically and then independently calculates overall and per-source metrics.

For an exact successful replay, the script requires:

- 3,630 predictions and zero inference omissions
- prediction SHA-256 `1a42d4b0b527f2c21a4a28dfa84e7a2d769762bc4a6d80c59a12821e85b89f0f`
- punctuation-insensitive WER `0.2407729005728886`
- punctuation-insensitive CER `0.08287672638469905`
- raw WER `0.24685364976627114`
- raw CER `0.08404221560257552`
- exact FLEURS, IndicVoices, and OpenSLR54 metric dictionaries matching the
  published record

Run twice in separate fresh processes if reproducing the two-replicate
determinism claim. Use different output directories; both prediction hashes
must be identical.

The portable top-level dependency constraints remain in
[`requirements-replay.txt`](requirements-replay.txt); the Linux/Python 3.10
inventory is the exact successfully observed environment, not a claim that
other supported environments cannot reproduce the output.

## What a successful result means

Level A is fully public and independently executable. Level B is independently
executable by authorized data users but cannot be public-input reproduction
while 70.77% of the view is gated. A hash for private content is an integrity
commitment, not public reproducibility; the row roster, source-level results,
redistributable predictions, executable replay, and explicit access boundary
are all necessary parts of this record.

Neither level turns this selection-dev snapshot into an untouched-test or
generalization result.
