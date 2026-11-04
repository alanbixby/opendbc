# Radar-track PR media

GIFs/MP4s embedded in the radar-tracks PRs on alanbixby/opendbc and alanbixby/sunnypilot.

Every box is a `RadarData` point produced by opendbc's `RadarInterface` replaying the logged CAN of a forum-submitted
route, projected into the logged qcamera frame with the logged extrinsic calibration and the device's camera
intrinsics. No image recognition is involved. Box size is an assumed 1.8 m × 1.5 m × 4 m; stationary returns are
drawn as short posts. The orange ring is the driving model's own lead (`modelV2.leadsV3[0]`) for comparison.
