# Legacy 0x238 camera-object family

Branch: `radar-238-family`. No PR opened. Push destination: `alanbixby/opendbc` only.

## Result and integration requirement

Both dialects now produce camera-kind points on all 13 formerly unsupported submitted routes (26 cached rlog segments). Four additional dual-source routes (8 segments) were replayed. These are 8- or 10-object lists with **three messages per object**, rather than 24/30 independent radar targets.

**Experimental decoding; the requested kin_corr >= 0.95 is not achieved consistently.** Geometry and lead matching are useful, but velocity/identity/range noise remains, especially sparse long-range detections. Do not present this as a fully validated radar replacement. The 30-message dialect's absolute-speed candidate is explicitly LOW confidence in the DBC. No derivative-generated velocity was used to inflate the kinematic score.

Per parent coordination, this branch deliberately contains **no radar-vs-camera coexistence policy**. Rebase onto `radar-alt-180-family`'s shared freshness/hysteresis policy before opening a PR or using dual-source output: this isolated branch can emit both radar and camera points on the four dual-source vehicles. Camera-only fingerprints retain `radarUnavailable=True`, avoiding a change to longitudinal tuning. `source_kind="camera"` follows the existing 235 family; explicit car.capnp sourceKind/UI labeling comes from the shared branch.

## Layout

Generator: `opendbc/dbc/generator/hyundai/hyundai_radar_238_255.py`. Names with `_B` describe the 24-message dialect. These deliberately overlapping DBC aliases are selected by the detected end address. Geometry is in `0x238 + 3*n`; both remaining messages are companions and never emit separate points.

All fields below are Motorola/big endian. DBC start bits are used (not network bit indices).

| Dialect | Signal | Start | Length | Signed | Scale / offset | Confidence |
|---|---|---:|---:|---|---|---|
| A, 30 messages | LONG_DIST | 7 | 13 | no | 0.05 / 0 m | high geometry; range noise remains |
| A | LAT_DIST | 23 | 12 | no | -0.05 / 102.4 m | high sign/scale; full width unexercised |
| A | OBJECT_SPEED | 39 | 10 | no | 0.2 / -100 m/s | LOW: absolute-speed candidate |
| A | COUNTER_A | 43 | 2 | no | 1 / 0 | high |
| A | OBJECT_ID | 63 | 7 | no | 1 / 0 | medium; upper boundary unexercised |
| B, 24 messages | LONG_DIST_B | 15 | 13 | no | 0.05 / 0 m | high |
| B | REL_SPEED_B | 18 | 11 | no | 0.1 / -100 m/s | high relative-speed scale; per-object residuals remain |
| B | LAT_DIST_B | 45 | 10 | yes | 0.05 / 0 m | medium; full signed width unexercised |
| B | OBJECT_ID_B | 7 | 6 | no | 1 / 0 | medium; upper boundary unexercised |
| B | COUNTER_B | 1 | 2 | no | 1 / 0 | high |

A relative speed is `OBJECT_SPEED - mean(WHL_SPD_FL,FR,RL,RR)/3.6`. Wheel speeds come from bus-0 WHL_SPD11 independently, with a 0.5 s freshness limit; absent/stale wheel speed suppresses A points. B supplies relative speed directly and needs no wheel-speed input. Validity requires positive distance and nonzero identity. Identity changes create a new RadarPoint trackId, preventing slot replacement from becoming an apparent distance jump on an existing track. Confidence does not imply known classification/lifecycle semantics.

Detection requires all 24 eight-byte messages, upgrades to 30 when the full range appears, and distinguishes the overlapping 32-byte 235 family by DLC during live discovery. Counter names include dialect suffixes intentionally: automatic validation of one dialect's counter against the other dialect's payload would incorrectly reject valid CAN.

## Source assessment and companions

The data supports the maintainer's forward-camera interpretation, rather than proving a second physical radar. The family has a roughly 30 ms cadence alongside the physically separate 50 ms 500-family cycle. It exposes few objects (typically 0–5 per frame) while 500 sees dense roadside returns. Its lead geometry agrees with vision; all well-populated vision lateral comparisons prefer the implemented sign. Many turning segments without a confident vision lead also have positive turn_corr near 0.97. The camera-like limited object list, range noise, and independent cadence support `source_kind="camera"`.

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

## Replay evidence: every cached driving segment

These are **camera-source-only after metrics**, including on dual-source vehicles; baseline points are total baseline output (zero on the 13 newly decoded routes). Existing radar output remains independent and will be selected by the shared policy after integration. The source-filtered score avoids a good radar hiding an inaccurate camera decode. None means insufficient evidence. Stat_frac need not be high for a vehicle-oriented camera list. Turn_corr is the parent's vision-free stationary-object lateral-sign test; it is not kin_corr.

| Route/segment | Baseline pts/frame | Camera pts/frame | kin_err | kin_corr | stat_frac | lead_match | lat_err | lat_err_flip | turn_n | turn_corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 224d1e774b6acc2e/0000001d--0ae7d5fa70/10 | 0 | 3.6 | 0.55 | 0.746 | 0.003 | 0.486 | 0.19 | 1.28 | 0 | None |
| 224d1e774b6acc2e/0000001d--0ae7d5fa70/13 | 0 | 1.51 | 0.554 | 0.948 | 0.0 | 0.76 | 0.24 | 5.09 | 0 | None |
| 3e4f79d5bf692518/00000001--f53d01f8e3/1 | 0 | 4.81 | 1.484 | 0.465 | 0.59 | None | None | None | 412 | 0.978 |
| 3e4f79d5bf692518/00000001--f53d01f8e3/2 | 0 | 4.66 | 1.361 | 0.431 | 0.554 | None | None | None | 546 | 0.973 |
| 3e4f79d5bf692518/00000002--b18171f9a9/2 | 0 | 2.73 | 0.886 | 0.759 | 0.155 | 0.851 | 0.31 | 4.83 | 29 | 0.954 |
| 3e4f79d5bf692518/00000002--b18171f9a9/4 | 0 | 4.91 | 1.658 | 0.813 | 0.281 | 0.142 | 1.21 | 2.65 | 87 | 0.975 |
| 4709fe68b0cc9c0a/00000125--ed2a02e7a8/1 | 0 | 1.85 | 1.222 | 0.947 | 0.033 | 0.745 | 0.27 | 1.06 | 14 | 0.966 |
| 4709fe68b0cc9c0a/00000125--ed2a02e7a8/2 | 0 | 0.96 | 1.883 | 0.82 | 0.047 | 0.0 | None | None | 21 | 0.983 |
| 4709fe68b0cc9c0a/0000012b--f29c054b05/1 | 0 | 0.17 | 1.093 | 0.957 | 0.372 | 0.0 | None | None | 82 | 0.901 |
| 4709fe68b0cc9c0a/0000012b--f29c054b05/2 | 0 | 0.27 | 2.216 | 0.953 | 0.075 | None | None | None | 9 | None |
| 4a975fc1d9e71801/00000005--50d176008a/1 | 0 | 1.33 | 1.084 | 0.881 | 0.045 | 0.51 | 0.51 | 3.59 | 4 | None |
| 4a975fc1d9e71801/00000005--50d176008a/2 | 0 | 0.84 | 1.069 | 0.967 | 0.0 | 0.661 | 0.39 | 2.88 | 0 | None |
| 59fa1d41318b87d3/00000002--b47e891d5f/1 | 0 | 2.96 | 0.802 | 0.722 | 0.19 | 0.866 | 0.27 | 2.57 | 109 | 0.973 |
| 59fa1d41318b87d3/00000002--b47e891d5f/2 | 0 | 5.33 | 0.769 | 0.8 | 0.018 | 0.676 | 0.39 | 6.65 | 23 | -0.163 |
| 662bedbf8453b81e/00000124--7dc358f20c/0 | 19.61 | 2.15 | 0.907 | 0.74 | 0.496 | 0.517 | 0.68 | 1.29 | 374 | 0.969 |
| 662bedbf8453b81e/00000124--7dc358f20c/1 | 11.98 | 0.61 | 0.0 | -0.109 | 0.907 | 0.981 | None | None | 97 | 0.887 |
| 7bc0de9da607c543/00000042--302b371266/0 | 0 | 0.39 | 1.607 | 0.401 | 1.0 | 0.0 | None | None | 89 | 0.883 |
| 7bc0de9da607c543/00000042--302b371266/1 | 0 | 2.78 | 0.538 | 0.716 | 0.965 | 0.32 | 1.45 | 2.8 | 36 | 0.892 |
| 810a7ca7cb31ed86/00000001--b6f9cdd134/18 | 0 | 3.06 | 0.663 | 0.946 | 0.152 | 0.005 | 1.1 | 2.5 | 148 | 0.907 |
| 810a7ca7cb31ed86/00000001--b6f9cdd134/20 | 0 | 2.37 | 0.424 | 0.431 | 0.0 | 0.977 | 0.38 | 1.6 | 0 | None |
| 8f52823c702cb300/00000177--177d1aa6ff/1 | 9.35 | 1.89 | 0.628 | 0.915 | 0.0 | 0.861 | 0.32 | 5.09 | 0 | None |
| 8f52823c702cb300/00000177--177d1aa6ff/2 | 13.1 | 3.22 | 0.7 | 0.764 | 0.001 | 0.691 | 0.55 | 0.74 | 0 | None |
| 9f8ef6e94dfcf047/000000f9--99cc2db166/16 | 0 | 0.04 | 1.438 | -0.577 | 1.0 | None | None | None | 22 | -0.672 |
| 9f8ef6e94dfcf047/000000f9--99cc2db166/7 | 0 | 0.94 | 1.923 | 0.521 | 0.108 | None | None | None | 0 | None |
| b27d9eafeb61976e/00000233--03a9c0858c/10 | 5.95 | 1.91 | 0.287 | 0.749 | 0.0 | 0.971 | 0.62 | 2.23 | 0 | None |
| b27d9eafeb61976e/00000233--03a9c0858c/6 | 14.19 | 3.74 | 0.476 | 0.683 | 0.001 | 0.832 | 0.35 | 3.73 | 0 | None |
| c0523d020c46beb3/00000288--0fa094add9/1 | 0 | 2.21 | 0.615 | 0.892 | 0.474 | 0.933 | 0.38 | 3.02 | 84 | 0.989 |
| c0523d020c46beb3/00000288--0fa094add9/3 | 0 | 1.86 | 0.826 | 0.685 | 0.036 | 0.519 | 0.15 | 2.88 | 31 | 0.901 |
| ce7eada09318e376/0000000e--0cc3d1c6cc/0 | 0 | 3.84 | 1.23 | 0.756 | 0.317 | 0.677 | 0.23 | 1.14 | 332 | 0.968 |
| ce7eada09318e376/0000000e--0cc3d1c6cc/3 | 0 | 3.16 | 0.927 | 0.911 | 0.105 | 0.462 | 0.58 | 3.85 | 227 | 0.968 |
| e3ae9e987a2a4e57/0000002b--30a6963e88/2 | 20.68 | 0.94 | 1.425 | 0.32 | 0.556 | None | None | None | 151 | 0.945 |
| e3ae9e987a2a4e57/0000002b--30a6963e88/3 | 18.43 | 1.28 | 2.51 | 0.635 | 0.055 | 0.0 | None | None | 45 | 0.981 |
| f6324c8fb8b6f68d/00000058--5330471811/2 | 0 | 0.19 | 3.539 | 0.27 | 0.0 | None | None | None | 0 | None |
| f6324c8fb8b6f68d/00000058--5330471811/3 | 0 | 0.73 | 5.73 | 0.847 | 0.0 | None | None | None | 0 | None |

The minimum-quality target is unmet on multiple segments, including the extremely sparse Optima/Niro EV f632 captures. This is preserved as an explicit limitation. Some unsupported-route segments have low vision lead match despite correct lateral sign; camera miss/lead association, long-range position error, velocity candidate error, and identity changes need further work. No generic outlier filter was added to conceal those cases.

## Verification and reproducibility

- Full Hyundai test file: 50 passed, 2 skipped, 428 subtests passed (final run).
- Ruff on all changed Python files: passed. `git diff --check`: passed.
- Known captured A and B payloads have explicit expected physical values in tests; end-to-end tests cover both variants, replacement identity, empty removal, runtime range upgrade, and absent ego speed. Detection tests cover all buses and DLC isolation.
- Final replay: 34 segments, 17 routes, maximum three concurrent log parsers; platform overrides from the shared briefing used. All 13 previously empty routes now expose points.
- Raw machine-readable results: `radar-238-validation.json` beside this report. Scratch extraction/search/comparison scripts and the exact replay copies are in `/tmp/radar238/` on the working machine; cached route data was read only.
- The installed Python executable intermittently lost its virtualenv prefix. Tests were run with the supplied Python, explicitly adding the supplied site-packages and lib-dynload directories to PYTHONPATH; no environment or dependency files were modified.

Before PR: rebase onto shared source policy/schema, rerun the full Hyundai file and replay, and review the LOW-confidence A speed field. No upstream push/comment/PR or superproject commit was made.
