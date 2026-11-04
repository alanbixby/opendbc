# Acura MDX 4G MMR: second investigation

Branch: `radar-acura-mdx-4g-v2`, based on fork branch `radar-acura-mdx-4g`
(`3129e0f8b5bae5b6d568ba1d1f5f79ef3a9b1652`). Final head is recorded in the
external `work/honda/MDX_REPORT_v2.md` after commit.

## Decision

Research only. No RadarInterface path is enabled. No segment passes the complete
validation bar (kin_corr >= 0.95, kin_err <= about 0.5 m/s, lead_match >= 0.8,
and lateral sign corroboration). No production route gains tracks. No fingerprint,
longitudinal, safety, or other Honda behavior changes. Push destination is exclusively
`alanbixby/opendbc`; no PR or upstream action.

The new result is a much better **12-bit longitudinal candidate**, independently
identified against vision, plus a cycle-timer candidate and stronger lateral-sign
evidence. These are useful research results, not a certified radar decode. Physical
sensor origin (radar, camera, or fused perception) remains unestablished.

All seven cached rlogs for public route
`ad9840558640c31d/0000001a--d6cd4871c2` were examined. Known good Hyundai generators
were read as format baselines. The original report remains historical; the candidate
width discussion below supersedes its 16-bit physical hypotheses.

## Stock ACC ground truth: unavailable on the known signals

`CAR.ACURA_MDX_4G_MMR` uses `HondaBoschCANFDPlatformConfig`, whose powertrain DBC
is `honda_common_canfd_generated`. Its source imports `_honda_common.dbc`,
`_bosch_2018.dbc`, and `_bosch_radar_acc.dbc` among others.

* Bosch `RADAR_HUD` (0x39f) defines `LEAD_DISTANCE` at Motorola 39|8, unsigned,
  factor 1, offset 0. **There are zero captured 0x39f frames in all seven segments**
  on all captured physical buses, including buses 0 and 2.
* `ACC_HUD` (0x30c) is present at 10 Hz on bus 0 (segment counts
  613, 600, 600, 600, 600, 600, 585), with another 62 on bus 2 in segment 0.
  `HUD_LEAD` at Motorola 45|2 is a display enum (none/dashed/solid/off), and
  `HUD_DISTANCE` is the selected following-gap enum, not measured range.
  `PCM_SPEED` is vehicle speed, not relative speed.
* `LEAD_SPEED` exists in `_nidec_common.dbc`, which this platform does not import.
  `_bosch_radar_acc.dbc` defines ACC commands/status, not measured lead speed.

Consequently no regression against an independently decoded stock distance/speed
can be performed from the known DBC signals. A stock ACC engagement does not imply
those HUD signals traverse the captured bus. Unknown CAN-FD ACC messages may still
contain such measurements; no exhaustive search of all other CAN IDs is claimed.

## Independent exhaustive field search

`search_independent.py` uses active 0x62 records, a recent (<0.2 s) confident
vision lead (probability >0.7, x <80 m), and no assumed object-list distance or speed
calibration. It scans every contiguous field fitting in 512 bits, widths 8..16,
both byte orders and both signednesses: **18,036 encodings per target**.
Big-endian start indexes in search outputs count linearly from the payload MSB;
convert to DBC sawtooth numbering before use. Linear calibration is fitted on
segments 0..3 and checked on held-out segments 4..6. Slot 0x62 is only a provisional
lead association; this is a screen, not guaranteed ground truth for every sample.

The best distance family is equivalent to Intel 48|12 unsigned (some tied candidates
include known zero bits in byte 5). Training corr=0.849; held-out corr=0.929,
median error=4.46 m. The fitted scale is 0.04255 m/count, offset 0.714 m. This fit
is **not** a validated calibration. No lateral or velocity encoding exceeds the
screen's absolute training-correlation cutoff of 0.8.

`search_polar.py` repeats this against vision-derived range, azimuth and projected
range rate. The best range field remains Intel 48|12 (training/held-out corr
0.849/0.929, held-out error 4.44 m); no azimuth or range-rate candidate clears 0.8.
Thus this search does not support a simple polar encoding over a Cartesian one.
It cannot exclude other associations, split fields, or nonlinear encodings.

`search_physics.py` independently screens all 18,036 encodings against Cartesian
x derivative, radial derivative, and each plus ego speed. It uses 9,633 endpoint
pairs about 0.53 s apart, requiring byte-4 identity at **every** intervening frame
in that slot, dt 0.4..0.7 s. No distance-derivative outlier rejection is applied.
Its provisional geometry is x=lower12*0.04 and y=signed_lower13*0.01.
The best endpoint-average velocity fit has Cartesian training/held-out corr
0.888/0.691, held-out median error 0.669 m/s; the radial fit is 0.864/0.625,
error 0.854 m/s. Absolute-speed fits are worse (held-out corr about 0.40/0.38).
The top Cartesian field starts at Intel bit 77, so includes three provisional
lateral high bits: a warning against declaring its fitted regression a velocity.
This search uses endpoint averages to rank candidates; replay below uses interval
averages and is the actual validation test. No derivative is substituted for a
measured velocity in replay.

`search_stationary.py` adds the stationary-object test: x derivative near -vEgo
(within 1.5 m/s), vEgo >5, x 3..80 m. This selects 188 training / 92 held-out
pairs without vision, but depends on the provisional x calibration. It regresses
all field encodings against -vEgo and -vEgo*cos(angle). Best training correlations
0.894/0.890 collapse to 0.409/0.362 held out, with errors 1.396/1.179 m/s.
These conditional results supply no independently validated velocity field.

## Layout and structure

All DBC research signals retain scale 1, offset 0 and no physical units.
Existing full raw words are retained alongside overlapping narrower candidates
so future comparisons can distinguish high-bit state from physical magnitude.

| Signal | Intel start/width | Interpretation and confidence |
|---|---|---|
| 0x60 header/checksum-like | 0/16 | Raw only; checksum algorithm unknown |
| 0x60 sequences | 16/8, 24/4 | Independent observed counters; not one counter |
| 0x60 count candidate | 32/8 | Matches nonzero byte-4 count in only 69..92% of complete following cycles; not validated |
| 0x60 timer candidate | 64/32 | Usually advances 66/67 per ~15 Hz cycle, corr with log time >0.9999999 in each segment; likely milliseconds; origin/rollover unknown |
| Slot object candidate | 32/8 | Observed IDs 1..63; 0 usually empty; validity/association unresolved |
| Slot longitudinal candidate | 48/12 unsigned | x = raw*0.04 m tested; removes high-nibble jumps; physical calibration unresolved |
| Slot high longitudinal bits | 60/4 unsigned | Active values include 1,3,6,7,8,9,10; semantics unknown |
| Slot lateral candidate | 64/13 signed | y = raw*0.01 m; sign corroborated conditionally, exact width/calibration unresolved |
| Slot high lateral bits | 77/3 unsigned | Kept separate; unknown |
| Slot velocity candidate | 80/11 unsigned | (raw-1536)*0.08 m/s tested, still fails |
| Slot remaining bytes | 96..511 | Individual raw bytes exposed; no second-object semantics assigned |

The split into two independent 32-byte objects is **not supported** by the empty
slot evidence. In segments 0,1,2,4, every byte 4..63 is the same canonical empty
payload whenever byte 4 is zero (11,608 / 12,398 / 11,834 / 13,180 frames).
Segments 3,5,6 contain only 2/1/2 exceptions among 12,615/12,941/11,377 zero-ID
frames. The second half does not show an independently populated object while the
first half is empty. This is evidence against that particular split, not proof
that all 64 bytes describe exactly one object. Other counts/detections remain open.

## Per-segment validation

Frozen candidate A: x=unsigned_lower12*0.04 m, y=signed_lower13*0.01 m,
v=(word_at_byte10-1536)*0.08 m/s. Every nonzero byte-4 slot is retained; no
high-bit filtering, jump clipping or per-segment fitting. Slot epochs reset on ID
changes, expire at 0.2 s, and snapshot on 0x80. The supplied `replay_radar.score`
uses interval-average velocity and vision y=-modelV2.leadsV3.y. Bicycle-model yaw
uses wheelbase 2.89 m and steer ratio 16.2 from this platform's values.py.

| Segment | Frames | Points/frame | kin_corr | kin_err m/s | lead frames | lead_match | lateral err / flipped m | turn_n | turn_corr |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 0 | 882 | 2.84 | 0.935 | 0.562 | 850 | 0.771 | 0.13 / 3.09 | 4 | None |
| 1 | 900 | 2.23 | 0.904 | 0.678 | 893 | 0.586 | 0.35 / 4.47 | 6 | None |
| 2 | 900 | 2.85 | 0.718 | 0.79 | 522 | 0.389 | 0.31 / 2.69 | 10 | 0.971 |
| 3 | 901 | 1.99 | 0.925 | 0.73 | 787 | 0.672 | 0.4 / 4.75 | 5 | None |
| 4 | 900 | 1.36 | 0.84 | 0.47 | 683 | 0.751 | 0.35 / 3.86 | 0 | None |
| 5 | 900 | 1.62 | 0.805 | 1.055 | 259 | 0.0 | 3.86 / 1.14 | 0 | None |
| 6 | 878 | 3.04 | 0.507 | 0.757 | 126 | 0.278 | 1.49 / 8.75 | 8 | None |

`None` denotes insufficient evidence, not a passing score. Segment 5's four lateral
associations favor the flipped sign; segments 5..6 do not independently establish
lead sign. Do not hide these failures behind the stronger earlier segments.

An additional vision-free, derivative-selected stationary-turn test (same criteria
as the stationary screen, |yaw*x| >0.3, |dy/dt| <6) gives 150 pairs, aggregate
corr(dy/dt,-yaw*x)=**0.846**. Per-segment pair counts/correlations:
0:19/0.778, 1:12/0.911, 2:34/0.534, 3:18/0.981, 4:6/undefined,
5:3/undefined, 6:58/0.527. This corroborates lateral sign without vision, but is
conditional on provisional geometry and stationary selection. The stricter generic
replay turn test in the table uses candidate velocity too; only segment 2 has at
least ten eligible pairs under candidate A.

Frozen candidate B changes x scale to 0.05 and velocity scale to 0.1; it does not
improve correlation (invariant to these joint linear scalings) or solve matching:

| Segment | kin_corr | kin_err m/s | lead_match | turn_n | turn_corr |
|---|---:|---:|---:|---:|---:|
| 0 | 0.935 | 0.702 | 0.465 | 111 | 0.636 |
| 1 | 0.904 | 0.847 | 0.497 | 25 | 0.92 |
| 2 | 0.718 | 0.988 | 0.592 | 34 | 0.906 |
| 3 | 0.925 | 0.912 | 0.216 | 66 | 0.947 |
| 4 | 0.84 | 0.588 | 0.161 | 11 | 0.814 |
| 5 | 0.805 | 1.318 | 0.077 | 0 | None |
| 6 | 0.507 | 0.946 | 0.008 | 24 | 0.473 |

Crossed scales (0.04/0.1 and 0.05/0.08) were also checked; all four complete tables
are in `mdx_v2/metrics.json`. No calibration passes. These exploratory scores
must not be advertised as production RadarData results.

Actual Honda RadarInterface was replayed again against all seven rlogs using this
checkout. Before/after behavior is unchanged: radarUnavailable=True, zero
points/frame, lead_match=0; kin_corr/kin_err/lateral metrics undefined throughout.
Output counts are 1227,1200,1200,1200,1200,1200,1170 (20 Hz fallback vs the
15 Hz exploratory snapshots). The log reader warns of corrupted events on segment
6 during selected-message extraction. Results cover readable events, not a complete
integrity certification.

## Changes and checks

The research DBC now includes 16-byte 0x60, separate low/high candidate position
fields, and the full unexplained payload as raw bytes. Real-frame tests retain the
original active/empty examples and add a captured 0x60 and high-nibble-7 slot from
segment 3. Tests verify extraction, not physical units or checksum correctness.

Honda tests: **4 passed**. Ruff on changed Python files: clean. `git diff --check`:
clean. No production files changed.

Scratch evidence is in `/home/bxb/Develop/radar-tracks/work/honda/mdx_v2/`.
Inputs `../mdx/0.npz`..`6.npz` are unchanged first-attempt raw extractions.
`extract_hud.py` reads the cached rlogs separately and preserves stock-message
extractions in `hud0.npz`..`hud6.npz`. `header_cycles.py` / `header_cycles.json`
contain cycle pairing and timer evidence; `structure.py` / `structure.json` contain
payload distributions; `search_independent.py`, `search_polar.py`,
`search_physics.py`, `search_stationary.py` preserve searches and JSON results.
`physics_pairs.npz` preserves all endpoint samples; `score_v2.py` /
`metrics.json` preserve all four replay hypotheses. `baseline.py` / `baseline-*.json`
record actual interface replay.

Reproduce searches and candidates with the radar-tracks venv, unsetting this shell's
ARGV0; run independent search first, then physics, then stationary. Polar and replay
can run independently. Use OPENBLAS_NUM_THREADS=1 for search speed. Example:

```sh
cd /home/bxb/Develop/radar-tracks/work/honda/mdx_v2
OPENBLAS_NUM_THREADS=1 env -u ARGV0 /home/bxb/Develop/radar-tracks/.venv/bin/python search_independent.py
OPENBLAS_NUM_THREADS=1 env -u ARGV0 /home/bxb/Develop/radar-tracks/.venv/bin/python search_physics.py
OPENBLAS_NUM_THREADS=1 env -u ARGV0 /home/bxb/Develop/radar-tracks/.venv/bin/python search_stationary.py
env -u ARGV0 /home/bxb/Develop/radar-tracks/.venv/bin/python score_v2.py
```

From the opendbc checkout, actual replay and verification:

```sh
PYTHONPATH=$PWD:/home/bxb/Develop/sunnypilot-ui env -u ARGV0 /home/bxb/Develop/sunnypilot-ui/.venv/bin/python /home/bxb/Develop/radar-tracks/work/honda/mdx_v2/baseline.py
PYTHONPATH=$PWD env -u ARGV0 /home/bxb/Develop/radar-tracks/.venv/bin/python -m pytest -q opendbc/car/honda/tests
/home/bxb/Develop/radar-tracks/.venv/bin/ruff check opendbc/dbc/generator/honda/acura_mdx_4g_objects_research.py opendbc/car/honda/tests/test_mdx_research.py
```

Remaining work: find a trustworthy stock/fused lead measurement on unknown CAN-FD
messages, establish slot/object validity and association, resolve position calibration
and velocity, and identify source sensor. Production gating must wait for all required
metrics, including both lateral-sign checks, to pass on independent segments.
