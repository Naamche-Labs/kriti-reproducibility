# Data, privacy, and licenses

## Published row-level evidence

- FLEURS Nepali references are from `google/fleurs` and retain CC BY 4.0.
- OpenSLR SLR54 references retain CC BY-SA 4.0.
- Hypotheses are generated model outputs paired with those references.
- Sample IDs are stable pseudonymous identifiers used to bind row order across
  systems and runs.

Follow the upstream attribution and share-alike requirements when
redistributing these files. Repository code is MIT licensed; that license does
not override dataset terms.

## Gated evidence

AI4Bharat IndicVoices declares CC BY 4.0 and requires users to accept conditions
and share contact information before accessing its files. This repository
conservatively keeps that access flow intact: it does not contain IndicVoices
audio, transcripts, predictions, file paths, speakers, or other row metadata.
Its roster entries contain exactly four fields: `ordinal`, `sample_id`,
`source_id`, and `access`. The verifier rejects additional fields or any changed
access classification.

The published aggregate metrics and SHA-256 commitments permit auditing and
authorized byte-for-byte replay, but they do not make the gated data public.

## Redacted operational summaries

The aggregate snapshot contains allowlisted JSON summaries and checksum files.
Private absolute paths are replaced; signed query strings, credentials, raw
audio, transcripts, row content, model weights, and private prediction files
are excluded. `source_sha256` values bind each redacted record to its private
source without claiming that the commitment alone reproduces the source.
