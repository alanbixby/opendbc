# Legacy 0x238 camera-object family

Branch: `radar-238-family`. No PR opened. Push destination: `alanbixby/opendbc` only.

## Result and shared-policy integration

Both dialects now produce camera-kind points on all 13 formerly unsupported submitted routes. This revision merges shared base `e3c4eb8a70b2ce1c437ec12ad87703d10f91a260`: camera and radar publish **alongside one another**, with `RadarTrackSource.sourceKind` (camera=1, radar=0). There is no separate radar preference or hysteresis for 238. Camera-only cars retain `radarUnavailable=True`; the four 500+238 vehicles retain `False`. Per-parser freshness expires stale points at publication time, and unrelated CAN never creates extra output ticks.

The original review found that positive distance/nonzero identity admitted unvalidated objects. Publication now requires a latched dialect and per-object kinematic confirmation. The original Niro EV 220.3-to-164.5 m jump is rejected by the 120 m cap; an independent same-ID 80-to-30 m test exercises immediate kinematic retirement within the cap. Confirmation gates the native speed; it never substitutes a derivative for vRel.

The reviewed absolute-speed interpretation of A is supported by simultaneous 500 radar: subtracting ego speed reduces median velocity disagreement from 23.8 to 0.51 m/s. B agrees to 0.160 m/s in the peer's measurement. The peer also found bus-0 wheel speed on every route, maximum gap 54 ms and 0.004–0.021 m/s disagreement with vEgo. These are signal-decoding checks, separate from the noisy raw-object quality addressed by this gate.

**Residual limits remain.** After gating, 18 of 27 segments with finite kinematic correlations meet 0.95; seven have insufficient/constant data. The median finite segment correlation is 0.969. Sparse Optima/Niro estimates, some camera-distance drift, and weak turn-sign subsets remain; none are hidden in the table. The gate is an operational confidence heuristic, not a recovered native lifecycle/classification enum.

## Layout

Generator: `opendbc/dbc/generator/hyundai/hyundai_radar_238_255.py`. Names with `_B` describe the 24-message dialect. These deliberately overlapping DBC aliases are selected by the detected end address. Geometry is in `0x238 + 3*n`; both remaining messages are companions and never emit separate points.

All fields below are Motorola/big endian. DBC start bits are used (not network bit indices).

| Dialect | Signal | Start | Length | Signed | Scale / offset | Confidence |
|---|---|---:|---:|---|---|---|
| A, 30 messages | LONG_DIST | 7 | 13 | no | 0.05 / 0 m | high geometry; range noise remains |
| A | LAT_DIST | 23 | 12 | no | -0.05 / 102.4 m | high sign/scale; full width unexercised |
| A | OBJECT_SPEED | 39 | 10 | no | 0.2 / -100 m/s | validated absolute speed; native geometry still needs confirmation |
| A | COUNTER_A | 43 | 2 | no | 1 / 0 | high |
| A | OBJECT_ID | 63 | 7 | no | 1 / 0 | medium; upper boundary unexercised |
| B, 24 messages | LONG_DIST_B | 15 | 13 | no | 0.05 / 0 m | high |
| B | REL_SPEED_B | 18 | 11 | no | 0.1 / -100 m/s | high relative-speed scale; per-object residuals remain |
| B | LAT_DIST_B | 45 | 10 | yes | 0.05 / 0 m | medium; full signed width unexercised |
| B | OBJECT_ID_B | 7 | 6 | no | 1 / 0 | medium; upper boundary unexercised |
| B | COUNTER_B | 1 | 2 | no | 1 / 0 | high |

A relative speed is `OBJECT_SPEED - mean(WHL_SPD_FL,FR,RL,RR)/3.6`. Wheel speeds come from bus-0 WHL_SPD11 independently, with a 0.5 s freshness limit; absent/stale wheel speed suppresses A points. B supplies relative speed directly and needs no wheel-speed input. Candidate validity requires positive distance and nonzero identity; publication additionally requires the confirmation rules below. Identity changes create a new RadarPoint trackId, preventing slot replacement from becoming an apparent distance jump on an existing track. Confidence does not imply known classification/lifecycle semantics.

Detection requires all 24 eight-byte messages, upgrades to 30 when the full range appears, and distinguishes the overlapping 32-byte 235 family by DLC during live discovery. Counter names include dialect suffixes intentionally: automatic validation of one dialect's counter against the other dialect's payload would incorrectly reject valid CAN.

## Source assessment and companions

The data supports the maintainer's forward-camera interpretation, rather than proving a second physical radar. The family has a roughly 30 ms cadence alongside the independently decoded 50 ms 500-family cycle. It exposes few objects (typically 0–5 per frame) while 500 sees dense roadside returns. Its lead geometry agrees with vision; all well-populated vision lateral comparisons prefer the implemented sign. Many turning segments without a confident vision lead also have positive turn_corr near 0.97. The camera-like limited object list, range noise, and independent cadence support `source_kind="camera"`.

**Unproven:** native object classifications, sensor transmitter identity, pedestrian-vs-sign selection, FOV/occlusion behavior, and behavior with a lead behind the camera. No video or controlled covering test was performed. Sparse/low-variance segments can give weak or negative correlation; those are retained below, not hidden.

The 250–255 extension is two additional three-message object slots. In the Sonata Hybrid capture, 25A/25B/25C activity accompanies the populated object groups, while 25D/25E are empty; these appear to be object companions, not independently validated extra geometry. The 201–205, 20A–20D, 266–26A, and 26D–26F groups share the approximately 33 Hz cadence and carry changing status/auxiliary data. No object-count/header/extra-track interpretation was validated, so they are not promoted to geometric tracks or misleadingly named fields. Their roles remain open. A direct linear ego-speed field search across these companion groups found no reliable match, so the A speed conversion uses independently decoded wheel speed instead.

## Cross-source comparison

Nearest-object matching uses distance/lateral/velocity together, retaining pairs within 5 m / 3 m / 4 m/s. These are conditional residuals, not a claim that every native object matches radar. Both cached segments per vehicle were included. Radar positions use the existing polar-to-Cartesian 500 decode. Velocity A uses recorded carState vEgo for this independent comparison; runtime uses wheel speed.

| Vehicle | Native samples | Matched at zero lag | Median abs delta distance (m) | Median abs delta lateral (m) | Median abs delta velocity (m/s) | Native / radar period (ms) |
|---|---:|---:|---:|---:|---:|---|
| Sonata | 10272 | 5627 | 1.217 | 0.262 | 0.457 | 30.05 / 50.09 |
| Niro EV b27d | 11270 | 8732 | 0.974 | 0.629 | 0.240 | 29.88 / 50.08 |
| Palisade | 5357 | 2747 | 1.383 | 0.595 | 0.460 | 29.84 / 50.13 |
| Sonata Hybrid | 6520 | 3117 | 1.419 | 0.402 | 0.569 | 29.97 / 50.06 |

An exploratory lag sweep from -0.30 to +0.30 s maximized the gated pair count at -0.24 s (Sonata), +0.12 s (Niro EV), +0.21 s (Palisade), and +0.09 s (Sonata Hybrid), but only improved matched counts by 0.4–3%. These inconsistent, weak optima do **not** establish a fixed camera/radar latency. No compensation is applied. A persistent matched-object latency study remains open.

## Confirmation and startup rules

The rules are local to RADAR_238_255. A candidate is in range only at 0 < d <= 120 m with nonzero ID. A point is published after **K=3 consecutive observations** of the same identity, separated by 15–45 ms. Duplicate timestamps do not advance confirmation. Every update must satisfy:

- Adjacent distance derivative versus mean of previous/current native vRel: absolute error <= 6 m/s.
- Lateral step <= 0.5 m + 8 m/s * dt (about 0.74 m at 30 ms).
- Once a history spans >=180 ms, its distance derivative versus native mean vRel must agree within 3 m/s. History is limited to 450 ms.

An inconsistent update, identity replacement, observation gap outside 15–45 ms, empty geometry, or out-of-range estimate retires the published point and starts confirmation again. A source outage also expires points through the shared freshness path. Reconfirmation allocates a new trackId. These tests select data using native speed and can therefore improve kinematic scores by construction; retained vision lead matches and the independent 500 comparisons remain important controls.

A is established by the complete 30-message range. B is latched only at the next cycle start after three completely observed 24-message cycles without extension evidence. An initial partial cycle does not count. A live cycle-end message cannot preserve a payload older than 45 ms for an individual object. Seeing even one A-extension address prevents/revokes a B latch until the full A range is observed. Unlatched parsers cannot become an active source. A also requires independently decoded wheel speed no older than 500 ms (inclusive); 500 ms + 1 ns fails eligibility and reconfirmation is required after wheel-speed recovery. B needs no ego input.

The 120 m cap removes the review's long-range Niro failure and leaves 40 m beyond the harness's <80 m confident-vision-lead evaluation range. Exploratory raw-observation sweeps compared K=3/5/8, adjacent residual limits 4/6/8 m/s, and 80/120/150 m ranges. Full 34-segment runtime replays then compared K=3 and K=5 at the selected 6 m/s and 120 m settings:

| Configuration | Camera points/output, frame weighted | Retained versus before | Median segment kin_err | Median finite segment kin_corr | Lead match, lead-frame weighted |
|---|---:|---:|---:|---:|---:|
| Before, 19ae9a9e | 2.135 | 100.0% | 0.998 | 0.752 | 0.747 |
| K=3, selected | 1.212 | 56.8% | 0.327 | 0.969 | 0.723 |
| K=5 | 0.840 | 39.3% | 0.316 | 0.968 | 0.701 |

K=5 loses substantially more points and lead matches for little additional median error reduction; K=3 was selected. Roughly 43% of raw points are removed, while weighted lead match falls about 2.4 percentage points. Scores below include confirmation startup, cap losses, and resets; no warm-up samples were deleted from evaluation.

## Before/after replay: all 34 originally requested segments

Every entry is **camera-source-only**, including on the four 500+238 vehicles. Each cell is before (19ae9a9e) → after (K=3 on shared e3c4eb8a). Missing/nonfinite statistics are shown as a dash, not a successful zero-error result. turn_corr is the parent's stationary-object lateral-sign test; it is distinct from kin_corr. The complete runtime result dictionaries are archived in `radar-238-validation.json`.

| Route/segment | Points/output | kin_err | kin_corr | stat_frac | lead_match | lat_err | lat_err_flip | turn_n | turn_corr |
|---|---|---|---|---|---|---|---|---|---|
| 224d1e774b6acc2e/0000001d--0ae7d5fa70/10 | 3.6 → 2.47 | 0.55 → 0.334 | 0.746 → 0.986 | 0.003 → 0.001 | 0.486 → 0.452 | 0.19 → 0.21 | 1.28 → 1.26 | 0 → 0 | — → — |
| 224d1e774b6acc2e/0000001d--0ae7d5fa70/13 | 1.51 → 1.11 | 0.554 → 0.407 | 0.948 → 0.924 | 0.0 → 0.0 | 0.76 → 0.738 | 0.24 → 0.24 | 5.09 → 5.12 | 0 → 0 | — → — |
| 3e4f79d5bf692518/00000001--f53d01f8e3/1 | 4.81 → 1.97 | 1.484 → 0.423 | 0.465 → — | 0.59 → 0.588 | — → — | — → — | — → — | 412 → 0 | 0.978 → — |
| 3e4f79d5bf692518/00000001--f53d01f8e3/2 | 4.66 → 2.04 | 1.361 → 0.254 | 0.431 → 0.988 | 0.554 → 0.556 | — → — | — → — | — → — | 546 → 0 | 0.973 → — |
| 3e4f79d5bf692518/00000002--b18171f9a9/2 | 2.73 → 1.65 | 0.886 → 0.359 | 0.759 → 0.969 | 0.155 → 0.098 | 0.851 → 0.84 | 0.31 → 0.31 | 4.83 → 4.81 | 29 → 0 | 0.954 → — |
| 3e4f79d5bf692518/00000002--b18171f9a9/4 | 4.91 → 2.17 | 1.658 → 0.384 | 0.813 → 0.972 | 0.281 → 0.146 | 0.142 → 0.096 | 1.21 → 1.26 | 2.65 → 2.6 | 87 → 0 | 0.975 → — |
| 4709fe68b0cc9c0a/00000125--ed2a02e7a8/1 | 1.85 → 0.6 | 1.222 → 0.315 | 0.947 → 0.975 | 0.033 → 0.034 | 0.745 → 0.66 | 0.27 → 0.28 | 1.06 → 1.14 | 14 → 0 | 0.966 → — |
| 4709fe68b0cc9c0a/00000125--ed2a02e7a8/2 | 0.96 → 0.39 | 1.883 → 0.259 | 0.82 → 0.665 | 0.047 → 0.047 | 0.0 → 0.0 | — → — | — → — | 21 → 0 | 0.983 → — |
| 4709fe68b0cc9c0a/0000012b--f29c054b05/1 | 0.17 → 0.09 | 1.093 → 0.169 | 0.957 → — | 0.372 → 0.459 | 0.0 → 0.0 | — → — | — → — | 82 → 0 | 0.901 → — |
| 4709fe68b0cc9c0a/0000012b--f29c054b05/2 | 0.27 → 0.04 | 2.216 → — | 0.953 → — | 0.075 → 0.213 | — → — | — → — | — → — | 9 → 0 | — → — |
| 4a975fc1d9e71801/00000005--50d176008a/1 | 1.33 → 0.76 | 1.084 → 0.205 | 0.881 → 0.974 | 0.045 → 0.024 | 0.51 → 0.472 | 0.51 → 0.44 | 3.59 → 3.35 | 4 → 0 | — → — |
| 4a975fc1d9e71801/00000005--50d176008a/2 | 0.84 → 0.5 | 1.069 → 0.167 | 0.967 → 0.977 | 0.0 → 0.0 | 0.661 → 0.616 | 0.39 → 0.38 | 2.88 → 2.79 | 0 → 0 | — → — |
| 59fa1d41318b87d3/00000002--b47e891d5f/1 | 2.96 → 1.78 | 0.802 → 0.331 | 0.722 → 0.93 | 0.19 → 0.147 | 0.866 → 0.828 | 0.27 → 0.26 | 2.57 → 2.51 | 109 → 0 | 0.973 → — |
| 59fa1d41318b87d3/00000002--b47e891d5f/2 | 5.33 → 3.8 | 0.769 → 0.429 | 0.8 → 0.979 | 0.018 → 0.011 | 0.676 → 0.645 | 0.39 → 0.39 | 6.65 → 6.69 | 23 → 7 | -0.163 → — |
| 662bedbf8453b81e/00000124--7dc358f20c/0 | 2.15 → 1.32 | 0.907 → 0.288 | 0.74 → 0.986 | 0.496 → 0.489 | 0.517 → 0.444 | 0.68 → 0.71 | 1.29 → 1.36 | 374 → 44 | 0.969 → -0.127 |
| 662bedbf8453b81e/00000124--7dc358f20c/1 | 0.61 → 0.53 | 0.0 → 0.0 | -0.109 → 0.984 | 0.907 → 0.935 | 0.981 → 0.977 | — → — | — → — | 97 → 28 | 0.887 → 0.767 |
| 7bc0de9da607c543/00000042--302b371266/0 | 0.39 → 0.22 | 1.607 → 0.942 | 0.401 → 0.838 | 1.0 → 1.0 | 0.0 → 0.0 | — → — | — → — | 89 → 14 | 0.883 → 0.947 |
| 7bc0de9da607c543/00000042--302b371266/1 | 2.78 → 2.17 | 0.538 → 0.333 | 0.716 → 0.891 | 0.965 → 0.963 | 0.32 → 0.303 | 1.45 → 1.45 | 2.8 → 2.8 | 36 → 19 | 0.892 → 0.842 |
| 810a7ca7cb31ed86/00000001--b6f9cdd134/18 | 3.06 → 1.31 | 0.663 → 0.379 | 0.946 → 0.993 | 0.152 → 0.176 | 0.005 → 0.0 | 1.1 → — | 2.5 → — | 148 → 0 | 0.907 → — |
| 810a7ca7cb31ed86/00000001--b6f9cdd134/20 | 2.37 → 1.15 | 0.424 → 0.216 | 0.431 → 0.966 | 0.0 → 0.0 | 0.977 → 0.976 | 0.38 → 0.38 | 1.6 → 1.6 | 0 → 0 | — → — |
| 8f52823c702cb300/00000177--177d1aa6ff/1 | 1.89 → 1.42 | 0.628 → 0.378 | 0.915 → 0.96 | 0.0 → 0.0 | 0.861 → 0.844 | 0.32 → 0.31 | 5.09 → 5.04 | 0 → 0 | — → — |
| 8f52823c702cb300/00000177--177d1aa6ff/2 | 3.22 → 1.16 | 0.7 → 0.373 | 0.764 → 0.988 | 0.001 → 0.0 | 0.691 → 0.688 | 0.55 → 0.55 | 0.74 → 0.74 | 0 → 0 | — → — |
| 9f8ef6e94dfcf047/000000f9--99cc2db166/16 | 0.04 → 0.01 | 1.438 → — | -0.577 → — | 1.0 → 1.0 | — → — | — → — | — → — | 22 → 0 | -0.672 → — |
| 9f8ef6e94dfcf047/000000f9--99cc2db166/7 | 0.94 → 0.23 | 1.923 → 0.247 | 0.521 → 0.817 | 0.108 → 0.075 | — → — | — → — | — → — | 0 → 0 | — → — |
| b27d9eafeb61976e/00000233--03a9c0858c/10 | 1.91 → 1.77 | 0.287 → 0.211 | 0.749 → 0.944 | 0.0 → 0.0 | 0.971 → 0.949 | 0.62 → 0.6 | 2.23 → 2.23 | 0 → 0 | — → — |
| b27d9eafeb61976e/00000233--03a9c0858c/6 | 3.74 → 2.76 | 0.476 → 0.263 | 0.683 → 0.983 | 0.001 → 0.0 | 0.832 → 0.806 | 0.35 → 0.35 | 3.73 → 3.82 | 0 → 0 | — → — |
| c0523d020c46beb3/00000288--0fa094add9/1 | 2.21 → 1.75 | 0.615 → 0.322 | 0.892 → 0.968 | 0.474 → 0.429 | 0.933 → 0.917 | 0.38 → 0.38 | 3.02 → 3.03 | 84 → 9 | 0.989 → — |
| c0523d020c46beb3/00000288--0fa094add9/3 | 1.86 → 1.29 | 0.826 → 0.395 | 0.685 → 0.861 | 0.036 → 0.019 | 0.519 → 0.51 | 0.15 → 0.14 | 2.88 → 2.97 | 31 → 0 | 0.901 → — |
| ce7eada09318e376/0000000e--0cc3d1c6cc/0 | 3.84 → 2.05 | 1.23 → 0.25 | 0.756 → 0.978 | 0.317 → 0.354 | 0.677 → 0.608 | 0.23 → 0.24 | 1.14 → 1.14 | 332 → 10 | 0.968 → 0.922 |
| ce7eada09318e376/0000000e--0cc3d1c6cc/3 | 3.16 → 1.55 | 0.927 → 0.339 | 0.911 → 0.966 | 0.105 → 0.113 | 0.462 → 0.399 | 0.58 → 0.55 | 3.85 → 3.85 | 227 → 16 | 0.968 → 0.993 |
| e3ae9e987a2a4e57/0000002b--30a6963e88/2 | 0.94 → 0.54 | 1.425 → 1.0 | 0.32 → 0.6 | 0.556 → 0.537 | — → — | — → — | — → — | 151 → 0 | 0.945 → — |
| e3ae9e987a2a4e57/0000002b--30a6963e88/3 | 1.28 → 0.45 | 2.51 → 0.16 | 0.635 → — | 0.055 → 0.054 | 0.0 → 0.0 | — → — | — → — | 45 → 0 | 0.981 → — |
| f6324c8fb8b6f68d/00000058--5330471811/2 | 0.19 → 0.05 | 3.539 → — | 0.27 → — | 0.0 → 0.0 | — → — | — → — | — → — | 0 → 0 | — → — |
| f6324c8fb8b6f68d/00000058--5330471811/3 | 0.73 → 0.05 | 5.73 → — | 0.847 → — | 0.0 → 0.0 | — → — | — → — | — → — | 0 → 0 | — → — |

## Both sources on the four dual-source cars

These are per-source mean points per published output, from the source-filtered scorer (so startup zeros are included). Shared publication remains cycle-driven. All eight rows have `radarUnavailable=False`; all 26 camera-only rows have `True`. Both source kinds with nonzero point counts are tested directly in RadarInterface.

| Route/segment | 238 camera points/output | 500 radar points/output |
|---|---:|---:|
| 662bedbf8453b81e/00000124--7dc358f20c/0 | 1.32 | 19.62 |
| 662bedbf8453b81e/00000124--7dc358f20c/1 | 0.53 | 12.15 |
| 8f52823c702cb300/00000177--177d1aa6ff/1 | 1.42 | 9.35 |
| 8f52823c702cb300/00000177--177d1aa6ff/2 | 1.16 | 13.13 |
| b27d9eafeb61976e/00000233--03a9c0858c/10 | 1.77 | 5.95 |
| b27d9eafeb61976e/00000233--03a9c0858c/6 | 2.76 | 14.21 |
| e3ae9e987a2a4e57/0000002b--30a6963e88/2 | 0.54 | 20.69 |
| e3ae9e987a2a4e57/0000002b--30a6963e88/3 | 0.45 | 18.45 |

## Held-out Sonata Hybrid segment 1

This additional segment was not used to choose K/thresholds and is separate from the 34-row aggregate. The same frozen K=3 gate improves camera kinematics while preserving independent positive lateral evidence:

| Points/output | kin_err | kin_corr | turn_n | turn_corr |
|---|---|---|---|---|
| 1.09 → 0.71 | 0.872 → 0.278 | 0.477 → 0.968 | 583 → 80 | 0.977 → 0.99 |

## Negative-turn investigations and remaining limitations

- **Stinger segment 2:** the original -0.163 correlation came from 23 heavily overlapping windows in one 79-observation track, at 4.5–8.25 m. Every measured dy/dt and predicted derivative had the **same positive sign** (23/23). Their magnitudes vary in opposite directions: measured 1.10–1.55 versus predicted 0.55–1.02 m/s. Median derivative residual is 0.53 m/s with the current sign versus 2.13 m/s flipped. This is not evidence for flipping the lateral field. Confirmation leaves only seven turn windows, below the harness's ten-sample reporting minimum; turn_corr is unavailable.
- **Optima segment 16:** -0.672 came from two short tracks (33 and 37 observations), with only 22 overlapping windows. Predicted derivatives lie near -0.31 to -0.55 m/s, while measured derivatives range -1.78 to +0.22 m/s; only 12/22 signs agree. Current/flipped median residuals are 0.53/0.60 m/s, a weak distinction. All 22 windows are excluded by confirmation, leaving no turn_corr. This was sparse/noisy evidence rather than a reproducible family-wide sign reversal; the precise object/scene cause remains unproven.
- **Palisade segment 0 after gating:** the selection changes the turn sample set from 374 windows at +0.969 to 44 windows at -0.127 across four confirmed runs. The retained derivatives are weak (-0.21 to +0.56 m/s), and the flipped residual is smaller (0.25 versus 0.63 m/s). This is an unresolved subset failure of the stationary-turn assumption/object quality, not a reason to reverse the shared field: the same segment's independent vision lateral residual still favors the implemented sign (0.71 versus 1.36 m), and held-out Sonata Hybrid/B Niro evidence supports it. It remains explicitly visible in the table.
- Some constant-speed or very sparse segments cannot produce a useful correlation. Sonata Hybrid segment 2 still has camera kin_corr 0.600 and median error 1.000 m/s. The gate rejects grossly inconsistent estimates but does not guarantee the original >=0.95 target on every route. Native classification/quality/age remain undecoded; the confirmation criteria must not be described as a hardware validity bit.

## Verification and reproducibility

- Shared base merged: `e3c4eb8a70b2ce1c437ec12ad87703d10f91a260`. The 238 source follows shared co-publication, sourceKind labeling, and publication-time expiry; no 238 selection/hysteresis policy was added.
- Full Hyundai file after merge: **67 passed, 2 skipped, 448 subtests passed**. Ruff on all changed Python files and `git diff --check` pass.
- Added runtime tests cover exact reported Niro payloads, same-ID in-range impossible jumps, lateral jumps, reconfirmation/new track IDs, split-batch A startup, B's bounded complete-cycle latch, partial extension evidence, duplicate timestamps, the inclusive 500 ms/stale-at-500-ms+1-ns wheel boundary, and simultaneous 500+238 sourceKind/count/freshness behavior.
- Final runtime replay: all 34 segments at K=3 and at K=5 after merging the shared base; four log parsers maximum across the paired experiments. Extra held-out Sonata Hybrid segment 1 was replayed independently.
- No raw log/cache data was changed. Scratch scripts and traces remain under `/tmp/radar238/`; machine-readable before/after/K=5 metrics and turn-window diagnostics are included beside this report.
- The supplied Python sometimes reports the T3 AppImage as its executable. The temporary test wrapper pins the supplied venv executable and explicitly adds its site-packages/lib-dynload paths; no environment/dependency files were modified.
- No upstream writes, PR creation, or superproject commits. Branch push destination remains only `alanbixby/opendbc`.
