# Radar-track PR media

GIFs/MP4s embedded in the radar-tracks PRs on alanbixby/opendbc and alanbixby/sunnypilot.

Every box is a `RadarData` point produced by opendbc's `RadarInterface` replaying the logged CAN of a forum-submitted
route, projected into the logged qcamera frame with the logged extrinsic calibration and the device's camera
intrinsics. No image recognition is involved. Box size is an assumed 1.8 m × 1.5 m × 4 m; stationary returns are
drawn as short posts. The orange ring is the driving model's own lead (`modelV2.leadsV3[0]`) for comparison.

## Reproduce
`tools/pr_media.py` fetches a segment's qcamera, replays its rlog CAN through a branch's `RadarInterface`
(`tools/dump_radar.py`), picks the window where a published track best matches the vision lead, and renders with
`tools/render_media.py`. Research overlays (corner, MDX, 0x510, 0x630) use the decoders in `tools/research/`.
