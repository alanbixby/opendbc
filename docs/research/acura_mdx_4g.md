# Acura MDX 4G MMR: research only

Branch: `radar-acura-mdx-4g`, based on `hyundai-radar-tracks`.
Final head SHA is recorded in the external `work/honda/MDX_REPORT.md` after commit.

## Decision

**The decode fails the validation bar. No MDX RadarInterface, fingerprint gating,
radarUnavailable change, longitudinal change, or safety change is included.**
This branch contains an explicitly research-only DBC, real-frame extraction tests,
and this report. No route gains production RadarData points.

All seven segments (0–6) of public route
`ad9840558640c31d/0000001a--d6cd4871c2` were downloaded/read. Bus 1 carries
sixteen 64-byte CAN-FD messages, even IDs `0x62, 0x64, ..., 0x80`, at approximately
15 Hz, alongside 16-byte `0x60`. Most slots are empty. Nonzero candidate IDs range
from 1 to 63. Empty slots retain nonzero payload, so a nonzero-payload test is wrong.

The earlier description of a combined counter in bytes 2–3 is corrected:
byte 2 increments modulo 256, while the low nibble of byte 3 separately increments
modulo 16. All slot streams in segments 1–6 advance by one in both fields on every
captured transition. Segment 0 has discontinuities/resets; it must not be treated
as an uninterrupted integrity test. Header bytes 0–1 look checksum-like but no
algorithm or coverage is established. The DBC does not activate checksum validation.

## Layout

Intel numbering throughout. Raw extraction is reliable; physical interpretations
below are hypotheses. The DBC deliberately exposes raw values, without physical
units, to avoid presenting fitted hypotheses as a validated decoder.

| Signal | Start | Length | Endian/sign | Candidate scale / offset | Confidence |
|---|---:|---:|---|---|---|
| Header/checksum-like word | 0 | 16 | little unsigned | raw | Header location high; checksum algorithm unknown |
| Sequence | 16 | 8 | little unsigned | 1 / 0 | High for observed increment behavior |
| Separate sequence | 24 | 4 | little unsigned | 1 / 0 | High for observed increment behavior |
| Header high nibble | 28 | 4 | little unsigned | raw | Meaning unknown |
| Object identifier candidate | 32 | 8 | little unsigned | 1 / 0 | Medium; zero-empty hypothesis only, not full validity |
| Byte 5 | 40 | 8 | little unsigned | raw | Meaning unknown |
| Longitudinal position candidate | 48 | 16 | little unsigned | 0.04 / -160 m | Low; width/scale/offset unresolved |
| Lateral position candidate | 64 | 16 | little unsigned | 0.01 / -245.76 m | Medium for sign on selected leads; width unresolved |
| Relative velocity candidate | 80 | 11 | little unsigned | 0.08 / -122.88 m/s | Low; fails temporal validation |
| Remaining payload | 96–511 | — | unknown | — | Unresolved, retained in original captures |

The lateral expression is equivalent to signed lower-13-bit * 0.01 only in the
observed neighborhood of 0x6000; do not assume that equivalence across wrap points.
In particular, the previous “signed bit 64” description did not establish width.

## Per-segment exploratory replay

These are **raw candidate** scores, not output of a newly enabled RadarInterface.
The scorer uses the exact candidate physical expressions above, marks byte-4 zero
empty, resets track identity whenever the identifier changes in a slot, expires
slots after 0.2 s, and snapshots on 0x80. It preserves large jumps/outliers rather
than removing them to improve scores. It uses the supplied `replay_radar.score`
kinematic (~0.5 s) and vision criteria, including comparison to **-modelV2.leadsV3.y**.
Lead probability must exceed 0.7, model x must be below 80 m, and model age below 0.2 s.
No derivative-derived substitute velocity is used.

| Segment | Frames | Points/frame | kin_corr | kin_err m/s | stat_frac | Confident lead frames | lead_match | lat_n | lat_err / flipped m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 882 | 2.84 | 0.212 | 0.564 | 0.032 | 850 | 0.591 | 281 | 0.12 / 3.06 |
| 1 | 900 | 2.23 | 0.267 | 0.678 | 0.036 | 893 | 0.821 | 508 | 0.34 / 4.53 |
| 2 | 900 | 2.85 | 0.167 | 0.795 | 0.023 | 522 | 0.444 | 230 | 0.31 / 2.73 |
| 3 | 901 | 1.99 | 0.041 | 0.73 | 0.016 | 787 | 0.438 | 271 | 0.43 / 5.47 |
| 4 | 900 | 1.36 | 0.84 | 0.47 | 0.005 | 683 | 0.291 | 178 | 0.79 / 5.0 |
| 5 | 900 | 1.62 | 0.805 | 1.055 | 0.007 | 259 | 0.008 | 2 | 1.11 / 1.81 |
| 6 | 878 | 3.04 | -0.009 | 0.761 | 0.032 | 126 | 0.111 | 14 | 1.44 / 8.75 |

The candidate lateral sign is strongly supported on associated off-centre leads
in segments 0–4. Segments 5–6 have very few associations; they cannot independently
establish a general lateral decode. Segment 1 barely meets lead matching, while
other segments do not. No segment reaches kin_corr >= 0.95.

Before and after this research branch, actual Honda RadarInterface replay has
radarUnavailable=True and zero points in every segment. kin_corr, kin_err,
stat_frac and lateral errors are undefined; lead_match=0 throughout. Baseline
frame counts for segments 0–6 are 1227, 1200, 1200, 1200, 1200, 1200, 1170.
Different baseline/candidate rates (20 vs 15 Hz) mean their sample counts differ.

## Additional checks and open questions

A broad field search covered little/big endian windows of 8–24 bits over bits
32–489, signed and unsigned, using persistent-ID ~0.53 s endpoint pairs. It excluded
nonpositive distances, >0.7 s gaps and |distance derivative| >=40 m/s. With the
candidate distance expression it retained 9,636 pairs. Best fitted speed correlation
was 0.8089 near bit 80, with median error ~0.70 m/s even after fitting scale/offset.
That filtered exploratory result must not replace the less selective replay table.
The search regresses endpoint-average candidate velocity, whereas the replay scorer
uses interval-average velocity. Absolute speed and noncontiguous encodings remain
possible; no claim is made that every encoding was exhausted.

Fitting leading-slot raw distance separately to confident vision leads also fails
to identify a common calibration: slopes range about 0.041–0.068 in segments 0–4,
and correlations collapse to ~0.41–0.44 in segments 5–6. An alternative 0.05 m/count
position and 0.1 m/s/count velocity trial does not resolve temporal consistency.
Do not select a different calibration per segment to manufacture a passing result.
Large same-ID jumps, intermittent IDs and high raw position bits require a better
validity/state decode and object association before production use.

The maintainer's “Acura range was unrelated” remark occurs in a Hyundai/Kia/Genesis
inventory. The captures support an object-like list: persistent IDs and positions
correlate with vision, especially lateral motion. They do **not** establish a radar
sensor source or fully validated geometry. The phrase cannot settle physical source
identity, and these findings do not overturn it with a production radar claim.
Possible camera/fused-perception origin remains open.

Bosch openpilot longitudinal normally disables the radar (or blocks camera ACC
on radarless cars). This route uses stock longitudinal, so that explanation does
not account for its visible messages. Current Honda code excludes Bosch CAN-FD
from alpha longitudinal and retains a radar-disable TODO. No changes are made there.

## Reproduction and validation

Scratch evidence is under `/home/bxb/Develop/radar-tracks/work/honda/mdx/`:
`0.npz`–`6.npz` are raw extractions, `headers.json` contains per-slot counters/DLCs,
`search.py`/`search.txt`/`search_pairs.npz` preserve field-search evidence,
`score_candidates.py` and `candidate_metrics.json` contain raw candidate replay,
and `baseline.py`/`baseline-0.json`–`baseline-6.json` replay the actual Honda interface.
The baseline uses the previously supplied `work/honda/replay_honda.py`.
LogReader warned of corrupted events during route replay; metrics describe readable
captured events, not a complete/continuous CAN integrity certification.

Recompute candidates with:

```sh
python /home/bxb/Develop/radar-tracks/work/honda/mdx/score_candidates.py
```

From this opendbc checkout, run baseline and checks with:

```sh
PYTHONPATH=$PWD:/home/bxb/Develop/sunnypilot-ui env -u ARGV0 /home/bxb/Develop/sunnypilot-ui/.venv/bin/python /home/bxb/Develop/radar-tracks/work/honda/mdx/baseline.py
PYTHONPATH=$PWD env -u ARGV0 /home/bxb/Develop/radar-tracks/.venv/bin/python -m pytest -q opendbc/car/honda/tests
/home/bxb/Develop/radar-tracks/.venv/bin/ruff check opendbc/dbc/generator/honda/acura_mdx_4g_objects_research.py opendbc/car/honda/tests/test_mdx_research.py
```

Validation: Honda tests **3 passed**, ruff clean, `git diff --check` clean.
The new real-frame test checks raw extraction from active 0x62 (segment 1) and
empty 0x80 (segment 0), including independent counters and nonzero empty payload.
It does not validate physical units, checksum correctness or object semantics.
No PR was opened. Push destination is exclusively `alanbixby/opendbc`.
