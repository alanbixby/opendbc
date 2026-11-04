# Research radar video examples

All paths in this note are relative to this directory. Every stem below has GIF,
MP4 and PNG versions. Times are seconds from the segment's first logged qcamera
frame. Each clip covers eight logged seconds, sampled at roughly 7 fps; the
renderer quantizes sampling to every third 20 Hz camera frame.

Purple rings are research candidates, never published RadarData tracks. The
salmon hollow oval is the logged vision lead, not an image detector added here.
Blue boxes are production RadarInterface outputs where present. Markers are
projected ground footprints: they are not fitted image bounding boxes. Terrain,
radar reflection location and candidate calibration can move a footprint relative
to a visible bumper. No image recognition, visual fitting or per-window decoding
adjustments were used.

## PR #2 — pr2_corner_signed

- Route: `102161de13e822d1/0000000d--f74a52a624`, segment **2**, **4–12 s**.
- Main layer: empty, timestamped `pr2_2_empty.pkl`.
- Purple: bus-0 24-byte CORNER_A/B_OBJECT slots, branch signed 13-bit LONG_DIST,
  left-positive LAT_DIST, REL_SPEED; sentinel 204.7 m excluded.
- Red X: identical records decoded with unsigned longitudinal distance
  (`signed + 409.6` for negative signed values). This exactly changes the distance
  signedness while keeping the other fields fixed; unsigned markers beyond the
  panel range are intentionally invisible.
- Dumps: `pr2_2_extra.pkl`, `pr2_2_unsigned.pkl`.

Forward returns overlap visible traffic while corner returns cross behind the
longitudinal origin. At **7.3484 s**, slot **0x280** crosses from **+1.6 m** to
**−0.1 m** at lateral **+6.5 m**: unsigned becomes **409.5 m** and leaves the panel,
while the signed return stays near ego. The PNG captures this example, and a
fixed-slot numeric readout exposes the unsigned overflow. The crossing return is
outside the narrow front camera's view; no unique image-object association is
claimed for it. Slot reuse is possible, so this does not demonstrate persistent
identity throughout the full clip.

The wrapper extends the bird's-eye panel to **−15 m**; it never projects rear
objects into the front camera. Inspected frames at approximately **7.05, 7.35,
7.50 s**, plus the earlier midpoint version.

## PR #3 — pr3_mdx_research

- Route: `ad9840558640c31d/0000001a--d6cd4871c2`, segment **0**, **12–20 s**.
- Platform: `ACURA_MDX_4G_MMR`.
- Main layer: empty, timestamped `pr3_0_empty.pkl`.
- Purple: bus-1 even 0x62–0x80 64-byte research slots, byte-4 object ID nonzero.
  Distance = **Intel unsigned 48|12 × 0.04255 + 0.714 m**; lateral =
  **Intel signed 64|13 × 0.01 m**, left-positive. These come from the report's
  fitted distance candidate and conditionally supported lateral sign.
- Dump: `pr3_0_extra.pkl`. Relative speed is zero as an unused rendering placeholder;
  no velocity interpretation or kinematic correctness is implied.

The principal candidate footprint remains near the visible SUV's rear as the MDX
stops at the intersection; other records appear near roadside geometry. **This
is an unvalidated candidate illustration, not proof that the research radar is
working:** the candidate range remains roughly 3–4 m beyond the vision lead in
this close-range window, and peripheral returns have no confirmed identity.
The original report's held-out failures, unresolved validity, calibration and
velocity remain unresolved. Do not describe this GIF as production radar support.
Inspected final frames at approximately **13.05, 16.05, 18.30 s**. A later moving
window was rejected because the planar projection on changing road grade visibly
missed the vehicle, despite better scalar range agreement; no projection was
retuned to hide that limitation.

## PR #7 — pr7_510_detections

- Route: `a6d25e95d936fdc4/000002ed--89d7944c52`, segment **4**, **16–24 s**.
- Main: `pr7_main.pkl`, production **210–21F bus 1** tracks replayed through
  `radar-audit-existing`, including its compact-Mobis lateral correction.
- Purple: `pr7_4_extra.pkl`, bus-1 **510–51F DLC 64**, four records per message,
  VALID=1 only; longitudinal ×0.01 m, **negated** right-positive lateral ×0.01 m,
  signed 13-bit Doppler ×0.025 m/s.

Purple return footprints cluster at the visible lead and neighboring traffic,
with the blue production boxes and vision lead providing context around 41 m.
Several detections may belong to one object; message/record indices are scan
positions, not persistent IDs. Inspected frames at approximately **17.10, 20.10,
22.35 s**; additional roadside returns are not asserted to be separate vehicles.

## PR #8 — pr8_630_selected

- Route: `ac27c9808ac91710/00000002--e0aab81e4d`, segment **2**, **15–23 s**.
- Main: `pr8_main.pkl`, production **500–53F bus 1** tracks. The audit branch
  supplies the unchanged 500 interpretation used for this replay.
- Purple: `pr8_2_extra.pkl`, bus-1 even **630–63C** messages, distance ×0.05 m,
  200 m empty marker excluded, **negated** right-positive lateral,
  signed 13-bit relative speed ×0.01 m/s.

Purple selections overlap the blue production lead track on the visible car
through the bend, at roughly 22–24 m. Repeated selections can choose the same
500-bank object: they do not establish an additional independent radar track
list or prove the consumer/source ECU. Inspected frames at approximately
**16.05, 19.05, 21.30 s**.

## Reproduction and validation

- Read the parent `../render_media.py` and `../dump_radar.py` first. Both are
  unchanged. `render_research.py` adapts the renderer **in memory**: shorter
  legends, no unclipped trails spilling above the panel, and the necessary
  rearward panel for PR #2. Its temporary frame directory is under `research/tmp`.
- `fetch_video.py` downloads authenticated qcamera files into this directory;
  it never logs credentials or signed URLs. Rlogs stay in the existing cache.
- `decode_candidates.py` generates research DBCs in memory from exact branch
  generator snapshots in `generators/`, then uses CANParser. The original
  revisions are in `branch_heads.json`. Candidate snapshots expire after 0.2 s;
  empty main dumps use the same timestamps.
- `decode_all.py` replays candidates and production layers sequentially using
  existing read-only branch checkouts. PR #8's generator is loaded from its
  pinned snapshot while using the audit branch's compatible CANParser runtime.
  No new worktrees, branch changes, commits, pushes or GitHub actions were made.
- `render_all.py` reproduces final GIF/MP4/PNG assets, including the chosen corner
  crossing still. Run from the media directory with `env -u ARGV0
  PYTHONDONTWRITEBYTECODE=1 python3 research/render_all.py`. The supplied venv
  requires ARGV0 unset in this shell.
- No more than **three** log parsers ran concurrently; final rendering and
  reproduction scripts are sequential. New persistent artifacts are confined
  to this directory.
- Visually inspected at least three frames per example; supporting `pr*_qa_*.png`
  files remain here. Every GIF was decoded through its final frame, every MP4
  fully decoded with ffmpeg, and every GIF is below **5,000,000 bytes**.
- The parent renderer emits ffmpeg broken-pipe diagnostics when it stops reading
  the full camera stream at the end of a chosen window. Rendering succeeds;
  these messages do not indicate damaged output MP4s.

## Final artifact sizes

| File stem | GIF bytes | MP4 bytes | PNG bytes |
|---|---:|---:|---:|
| pr2_corner_signed | 3,130,652 (3.13 MB) | 544,826 (0.54 MB) | 364,057 (0.36 MB) |
| pr3_mdx_research | 3,041,577 (3.04 MB) | 324,757 (0.32 MB) | 230,506 (0.23 MB) |
| pr7_510_detections | 3,413,797 (3.41 MB) | 378,521 (0.38 MB) | 148,138 (0.15 MB) |
| pr8_630_selected | 3,389,641 (3.39 MB) | 492,353 (0.49 MB) | 179,320 (0.18 MB) |
