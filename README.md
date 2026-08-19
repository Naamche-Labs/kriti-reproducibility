# kriti benchmark reproducibility

this repository is the verification and replay record for the stopped
nineteen system nepali speech recognition development snapshot. it contains a
public evidence audit and an authorized workflow that reconstructs the exact
3,630 row view from pinned upstream data and reruns kriti.

this is development set selection evidence. it is not an untouched test set,
a completed thirty three system campaign, a universal domain result, or a
production readiness claim.

## what is reproducible

* repository integrity: a public laptop with python 3.10 or newer can verify
  every published checksum and evidence contract
* nineteen system evidence: a public laptop can verify every system, sample id,
  source score, and replicate commitment
* public source metrics: a public laptop can recompute 38 metric sets from
  20,159 published prediction rows
* exact benchmark view: an accepted indicvoices user on an authorized linux
  data plane can rebuild the ordered 304 fleurs, 2,569 indicvoices, and 757
  openslr54 rows
* exact kriti inference: a cuda gpu can rerun all 3,630 predictions and match
  every overall and per source metric
* two load determinism: two separate authorized processes can produce byte
  identical prediction files
* repository tests: a public laptop can run the unit tests, lint, formatting,
  compilation, and evidence verification

the public verifier does not rerun the other eighteen models. their complete
model specific runtimes and inference adapters are not published here. it
verifies their frozen records and recomputes every redistributable source
score. only kriti has a complete upstream to inference replay in this
repository.

## frozen benchmark

* fleurs nepali: 304 public rows
* indicvoices nepali: 2,569 rows requiring accepted access
* openslr54: 757 public rows
* total: 3,630 rows, of which 70.77 percent are gated

kriti has the following exact metrics:

* overall, 3,630 rows: pi wer `0.2407729005728886`, pi cer
  `0.08287672638469905`, raw wer `0.24685364976627114`, raw cer
  `0.08404221560257552`
* fleurs, 304 rows: pi wer `0.2491329479768786`, pi cer
  `0.08493094807994872`, raw wer `0.3054368932038835`, raw cer
  `0.09429486080146345`
* indicvoices, 2,569 rows: pi wer `0.25031150816974257`, pi cer
  `0.08700243670925087`, raw wer `0.2503350182202892`, raw cer
  `0.08701065495293`
* openslr54, 757 rows: pi wer `0.05143338954468803`, pi cer
  `0.009733850656864747`, raw wer `0.05731142014327855`, raw cer
  `0.010597826086956521`

the model is `harrrshall/kriti` at immutable revision
`762d1c17edaff0a548f3483e37e491fe8cc77971`. the expected prediction file
sha 256 is
`1a42d4b0b527f2c21a4a28dfa84e7a2d769762bc4a6d80c59a12821e85b89f0f`.

## public verification

clone the repository and record the commit that you tested:

```bash
git clone https://github.com/naamche-labs/kriti-reproducibility
cd kriti-reproducibility
git rev-parse head
```

create a clean environment and run the verifier:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python tools/verify_evidence.py -r .
```

the final json object must contain these values:

```json
{
  "aggregate": {
    "aggregate_records": 182,
    "commitments": 730
  },
  "predictions": {
    "metric_sets_recomputed": 38,
    "public_prediction_rows": 20159,
    "sample_ids": 3630,
    "systems": 19
  },
  "reproduction": {
    "records": 3630,
    "runtime_packages": 177
  },
  "upstream_reconstruction": {
    "records": 3630,
    "resolved_indicvoices_rows": 2569
  },
  "valid": true
}
```

the verifier performs these checks:

1. every published checksum subject matches its manifest
2. the ordered roster contains exactly 3,630 unique sample ids
3. all ordinals, source labels, and source counts match the frozen contract
4. no gated reference, prediction, audio hash, or upstream locator is public
5. all nineteen overall and per source metric records are present
6. two full view prediction commitments are present for every system
7. every public prediction row aligns with the ordered roster
8. public references agree across systems
9. wer and cer are recomputed for nineteen systems on fleurs and openslr54
10. the replay and reconstruction records match their public contracts
11. the 177 package replay lock and 24 package reconstruction lock match their recorded inventories

### inspect every system record

this prints each rank, system key, model id, immutable revision, decoder,
overall pi wer, all three source pi wer values, and both replicate hashes:

```bash
python - <<'py'
import json

with open(
    "evidence/predictions-20260819/metrics/per-source.json",
    encoding="utf-8",
) as handle:
    payload = json.load(handle)

for system in payload["systems"]:
    print(
        system["rank"],
        system["key"],
        system["model_id"],
        system["revision"],
        system["decoder"],
        system["overall"]["punctuation_insensitive_wer"],
        {
            source: metrics["punctuation_insensitive_wer"]
            for source, metrics in system["per_source"].items()
        },
        system["replicate_prediction_sha256"],
    )
py
```

for indicvoices and therefore the combined score, a public user verifies the
checksummed metric record and prediction commitments. an accepted data user
can additionally reconstruct the gated rows and recompute the complete kriti
result with the authorized workflow below.

## public repository tests

run every lightweight local gate from the repository root:

```bash
python -m pip install -r requirements-reconstruct.txt
python -m unittest discover -s tests -v
ruff check tools tests
ruff format tools tests
python -m py_compile tools/*.py tests/*.py
python tools/verify_evidence.py -r .
git status -s
```

the unit suite must report five passing tests. ruff must report clean lint and
already formatted files. compilation must exit successfully. the verifier
must report `"valid": true`. on a clean checkout, the final status command
must print nothing.

verify the exact reconstruction lock in a separate environment:

```bash
uv venv -p 3.10 ../kriti-reconstruction-lock-check
uv pip sync -p ../kriti-reconstruction-lock-check/bin/python \
  requirements-reconstruct-linux-py310.lock
../kriti-reconstruction-lock-check/bin/python tools/acquire_view_sources.py -h
../kriti-reconstruction-lock-check/bin/python tools/reconstruct_view.py -h
```

the sync installs 24 unique pinned packages. the two help commands must exit
without downloading any dataset.

## why the pseudonymous ids are independently resolvable

the public roster does not reveal gated indicvoices row locators, audio
hashes, or references. revealing those fields would cross the dataset access
boundary. the reconstruction no longer depends on a private prepared
manifest.

the public reconstruction code scans the pinned upstream revision inside the
accepted user's own data environment. for each indicvoices candidate it
derives a deterministic source identity from the repository relative parquet
path, physical row index, upstream path, and audio sha 256. it then derives the
public sample id with the published uuid version 5 function and joins that id
to the public ordered roster.

this gives an accepted user an executable resolver without publishing gated
metadata. the reconstruction fails if a row is missing, extra, reordered, or
changed. it also verifies the decoded audio, normalized reference, frame count,
source composition, selector commitment, semantic view commitment, and
portable view commitment.

the identity and normalization implementations are in
[`tools/reconstruction_common.py`](tools/reconstruction_common.py). the full
scan and join are in [`tools/reconstruct_view.py`](tools/reconstruct_view.py).

## authorized view reconstruction

run this section only on an authorized linux data plane. do not download or
process the corpora on a control plane laptop. the operator needs:

* python 3.10 and uv 0.11.9
* at least 50 gb of free storage
* accepted indicvoices access under the operator's own account
* ffmpeg `4.4.2-0ubuntu0.22.04.1` with libsoxr
* permission to retain the private working data under the upstream terms

the pinned upstream revisions are:

* fleurs revision: `70bb2e84b976b7e960aa89f1c648e09c59f894dd`
* indicvoices revision: `c96f9088f138cf89d419da7e8e643e1f05c00a87`
* openslr54 revision: checksummed release files

create the exact reconstruction environment and keep all private data outside
the repository:

```bash
kriti_work_root="$(pwd)/../kriti-private-work"
mkdir -p "$kriti_work_root"
uv venv -p 3.10 "$kriti_work_root/reconstruct-venv"
uv pip sync -p "$kriti_work_root/reconstruct-venv/bin/python" \
  requirements-reconstruct-linux-py310.lock
ffmpeg -hide_banner -version | head -n 1
```

the version line must be exactly:

```text
ffmpeg version 4.4.2-0ubuntu0.22.04.1
```

after the operator has accepted indicvoices access, acquire and validate the
pinned sources. the token is read from a terminal variable and passed through
a file descriptor, so the command does not write it to disk:

```bash
read -rsp "accepted access token: " token
echo
"$kriti_work_root/reconstruct-venv/bin/python" tools/acquire_view_sources.py \
  -s "$kriti_work_root/authorized-sources" \
  -t /dev/fd/3 3<<<"$token"
unset token
```

the acquisition verifies the exact fleurs files, all openslr54 archives, and
74 indicvoices parquet files at the pinned revision. it downloads upstream
data, so it must run only in the authorized data environment.

reconstruct the view:

```bash
"$kriti_work_root/reconstruct-venv/bin/python" tools/reconstruct_view.py \
  -s "$kriti_work_root/authorized-sources" \
  -o "$kriti_work_root/reconstructed-view"
```

the script scans exactly these upstream row counts:

* fleurs: 305 scanned and 304 selected
* indicvoices: 249,422 scanned and 2,569 selected
* openslr54: 157,905 scanned and 757 selected

it succeeds only when all of these commitments match:

* selector sha 256:
  `03c330561e75ae4aa8b62c15dac1c7aee6a22bae1687ac706b1261769a84c3b3`
* semantic view sha 256:
  `aa536153717af74ecb308661959b96e3daa16385310b6031d892440e8d8c2add`
* portable view sha 256:
  `d26afb661b581fbc9fd7fb9f7f594de6bc54d16d023050beb102531b8a8d7611`
* private provenance sha 256:
  `de52c091e2341ed18ae0ee0d36743bc7834d825f3e256107dcd78deb1086d340`

the resulting `view.jsonl`, `provenance.jsonl`, audio, references, and source
files are private working artifacts. do not commit, upload, or publish them.

## exact kriti inference replay

use a linux host with a cuda gpu. the verified replay environment used python
3.10.20, uv 0.11.9, torch 2.13.0, an nvidia l4, driver 595.58.03, cuda 13.0,
and cudnn 92000. sync the exact 177 package runtime inventory:

```bash
uv venv -p 3.10 "$kriti_work_root/replay-venv"
uv pip sync -p "$kriti_work_root/replay-venv/bin/python" \
  requirements-replay-linux-py310.lock
```

run the first replay in a new output directory and a new public model cache:

```bash
"$kriti_work_root/replay-venv/bin/python" tools/reproduce_kriti.py \
  -v "$kriti_work_root/reconstructed-view/view.jsonl" \
  -p "$kriti_work_root/reconstructed-view/provenance.jsonl" \
  -o "$kriti_work_root/replay-a" \
  -c "$kriti_work_root/model-cache-a" \
  -d cuda \
  -b 32
```

the loader pins the model revision and enforces these artifact hashes before
inference:

* `kriti.nemo` sha 256:
  `0144854f0cc78f4b6115b75089fad632c39207d5256e53f92da996b9bbe43582`
* `punctuation_head.json` sha 256:
  `5874b6fc6b4f1172dffa249a42f5054ffe196cff9b97854fe180eafc4134e9bb`

the script independently checks the view, runs all 3,630 rows, calculates the
overall and three per source metric dictionaries, and writes predictions
atomically. it exits unsuccessfully if any exact metric or hash differs. a
successful summary has `"valid": true` and the metric values listed above.

### two load determinism

start a second process with a separate output directory and model cache:

```bash
"$kriti_work_root/replay-venv/bin/python" tools/reproduce_kriti.py \
  -v "$kriti_work_root/reconstructed-view/view.jsonl" \
  -p "$kriti_work_root/reconstructed-view/provenance.jsonl" \
  -o "$kriti_work_root/replay-b" \
  -c "$kriti_work_root/model-cache-b" \
  -d cuda \
  -b 32
cmp "$kriti_work_root/replay-a/predictions.jsonl" \
  "$kriti_work_root/replay-b/predictions.jsonl"
sha256sum "$kriti_work_root/replay-a/predictions.jsonl" \
  "$kriti_work_root/replay-b/predictions.jsonl"
```

`cmp` must exit successfully. both printed hashes must be
`1a42d4b0b527f2c21a4a28dfa84e7a2d769762bc4a6d80c59a12821e85b89f0f`.

## recorded independent validation

the checked evidence records an independent replay named `r_38e10f2c`. it used
a fresh public checkout, an isolated 177 package environment, and a fresh
tokenless model cache. it decoded all 3,630 development rows, matched the exact
prediction hash and every metric, and did not access the protected test view.

the checked evidence records an upstream reconstruction run named
`r_1588a51d`. it received no private development manifest, scanned the pinned
sources, resolved all 2,569 indicvoices rows, rebuilt all 3,630 rows, and found
zero row differences from the frozen release.

the checked evidence also records a separate inference run named
`r_a343d43f`. it used the reconstructed view, a fresh public model cache, no
model token, and no protected test view. all prediction hashes, overall
metrics, per source metrics, semantic view checks, and portable view checks
matched exactly.

these records are evidence of completed runs. they do not remove the need for
an independent operator to execute the commands above when making an
independent reproduction claim.

## evidence map

* [nineteen system metrics](evidence/predictions-20260819/metrics/per-source.json)
* [ordered public roster](evidence/predictions-20260819/view/ordered-sample-ids.jsonl)
* [public prediction index](evidence/predictions-20260819/export-index.json)
* [reconstruction contract](evidence/reconstruction-20260819/contract.json)
* [recorded upstream reconstruction](evidence/reconstruction-20260819/reconstruction.json)
* [recorded reconstructed inference](evidence/reconstruction-20260819/inference.json)
* [independent replay summary](evidence/reproduction-20260819/summary.json)
* [independent replay environment](evidence/reproduction-20260819/environment.json)

## exact reproducibility boundary

any public user can verify the repository, roster, all nineteen published
records, and every redistributable metric on an ordinary laptop. that user
cannot recompute gated indicvoices metrics without accepting the dataset terms.

an accepted indicvoices user with an authorized linux gpu environment can
reconstruct the exact view from upstream data without receiving the private
manifest and can rerun the complete kriti result. the pseudonymous ids are
locally resolvable through the public deterministic scan, but they are not a
public disclosure of gated source records.

the repository does not support fresh inference replays for the other eighteen
models. therefore the precise claim is that the complete kriti result is
independently reproducible by an authorized data user, while the full nineteen
system evidence record and all public source metric calculations are publicly
reproducible.
