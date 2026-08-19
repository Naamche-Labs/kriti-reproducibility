# Kriti reproducibility record

This repository is the independently verifiable evidence and replay record for
Kriti's **stopped 19-system development-set snapshot**. It exists separately
from the model repository and Hugging Face release so their user-facing files
stay small.

The short version: a private manifest hash was not sufficient. This record now
publishes the complete ordered pseudonymous sample-ID/source roster, exact
per-source metrics for every completed system, and row-level references and
predictions wherever redistribution permits.

## Verify the public record

```bash
git clone https://github.com/harrrshall/kriti-reproducibility
cd kriti-reproducibility
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python tools/verify_evidence.py
```

Expected terminal fields are:

```json
{
  "aggregate_records": 182,
  "commitments": 730,
  "metric_sets_recomputed": 38,
  "public_prediction_rows": 20159,
  "sample_ids": 3630,
  "systems": 19,
  "valid": true
}
```

The verifier hashes every published evidence file, validates all 3,630 ordered
sample IDs and source labels, checks the privacy boundary, aligns public rows
against the roster, confirms references are identical across systems, and
recomputes 38 public-source metric sets from the published predictions.

## What is published

| Evidence | Coverage | Location |
|---|---:|---|
| Ordered sample-ID/source roster | 3,630 / 3,630 rows | [`ordered-sample-ids.jsonl`](evidence/predictions-20260819/view/ordered-sample-ids.jsonl) |
| Exact overall and per-source metrics | 19 / 19 completed systems | [`per-source.json`](evidence/predictions-20260819/metrics/per-source.json) |
| FLEURS references + predictions | 304 × 19 rows | [`predictions/`](evidence/predictions-20260819/predictions/) |
| OpenSLR54 references + predictions | 757 × 19 rows | [`predictions/`](evidence/predictions-20260819/predictions/) |
| Full-view prediction commitments | two fresh loads × 19 systems | [`per-source.json`](evidence/predictions-20260819/metrics/per-source.json) |
| Redacted run/data summaries | 182 records | [`snapshot-20260819/`](evidence/snapshot-20260819/) |

The frozen view contains 304 FLEURS rows, 2,569 IndicVoices rows, and 757
OpenSLR54 rows. IndicVoices is therefore 70.77% of the 3,630-row view—not a
rounded claim hidden behind a hash.

## Kriti result

The primary metric is punctuation-insensitive WER. Kriti produced:

| Scope | Rows | PI WER | PI CER | Raw WER | Raw CER |
|---|---:|---:|---:|---:|---:|
| Overall | 3,630 | 24.0773% | 8.2877% | 24.6854% | 8.4042% |
| FLEURS | 304 | 24.9133% | 8.4931% | 30.5437% | 9.4295% |
| IndicVoices | 2,569 | 25.0312% | 8.7002% | 25.0335% | 8.7011% |
| OpenSLR54 | 757 | 5.1433% | 0.9734% | 5.7311% | 1.0598% |

The complete 19-system table is in [RESULTS.md](RESULTS.md). Both fresh model
loads produced prediction SHA-256
`1a42d4b0b527f2c21a4a28dfa84e7a2d769762bc4a6d80c59a12821e85b89f0f`.
The exact numerator and denominator counts—not only decimals—are in the JSON.

## Honest reproducibility boundary

Anyone can reproduce the public evidence verification above without dataset or
model credentials. Anyone can also recompute all FLEURS and OpenSLR54 scores
from row-level predictions.

The complete 3,630-row inference replay is **credential-gated reproducibility**
because IndicVoices requires users to accept access conditions before obtaining
its files. IndicVoices declares CC BY 4.0, but this record conservatively does
not republish its row content outside that access flow. For those 2,569 rows
this repository publishes only pseudonymous sample IDs, source labels,
aggregate metrics, and full-prediction commitments. No gated reference,
hypothesis, audio path, speaker field, or metadata is published.

An authorized researcher can rebuild the byte-identical view and run the exact
public model with [`tools/reproduce_kriti.py`](tools/reproduce_kriti.py). The
full procedure and the limits of each verification level are in
[REPRODUCING.md](REPRODUCING.md).

This snapshot is not an untouched-test result. The view guided model selection,
the planned campaign was stopped after 19 fully replicated systems, and 14
planned systems were never ranked. It is not a completed 33-system benchmark,
a universal-domain result, a production-readiness result, or a world-best
claim.

## Integrity and provenance

Every evidence directory has a `SHA256SUMS` inventory. Tagged release archives
are built deterministically from the Git commit and receive a GitHub artifact
attestation. Verify a downloaded release with:

```bash
sha256sum -c SHA256SUMS
gh attestation verify kriti-reproducibility-v1.0.0.tar.gz \
  --repo harrrshall/kriti-reproducibility
```

See [DATA_AND_LICENSES.md](DATA_AND_LICENSES.md) before redistributing evidence.
Repository code is MIT licensed; embedded source text retains its upstream
license.
