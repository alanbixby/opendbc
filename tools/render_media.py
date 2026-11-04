#!/usr/bin/env python3
"""Render a "radar tracks on video" GIF/MP4 for a PR: projected track boxes on the road camera + bird's-eye panel.

No image recognition: every box is a RadarData point (from opendbc's RadarInterface replaying the logged CAN)
projected into the logged qcamera frame with the logged extrinsic calibration and the device's camera intrinsics.

  PYTHONPATH=/home/bxb/Develop/sunnypilot-ui python render_media.py --rlog seg.rlog.zst --qcam qcamera.ts \
     --dump after.pkl [--ref-dump before.pkl] [--extra extra.pkl] --start 12 --dur 10 --title "..." --out out.gif
"""
from __future__ import annotations

import argparse
import bisect
import math
import os
import pickle
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RADAR_TO_CAMERA = 1.52
FONT_DIR = "/home/bxb/Develop/sunnypilot-ui/openpilot/selfdrive/assets/fonts"

BG = (13, 17, 23)
PANEL = (22, 27, 34)
GRID = (48, 54, 61)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
RADAR = (88, 166, 255)       # radar track
RADAR_STAT = (110, 118, 129)  # stationary radar return
CAMERA = (245, 158, 11)       # camera-object source
LEAD = (56, 139, 253)         # lead-matched track
VISION = (255, 123, 114)      # model (vision) lead ring
BEFORE = (248, 81, 73)        # before-fix overlay
EXTRA = (163, 113, 247)       # research overlay


def font(size, weight="Regular"):
  try:
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{weight}.ttf"), size)
  except OSError:
    return ImageFont.load_default()


def load_log(path):
  from openpilot.tools.lib.logreader import LogReader
  d = {"v": [], "model": [], "calib": None, "device": None, "sensor": None, "enc": {}, "platform": None}
  for m in LogReader(path):
    w = m.which()
    if w == "carState":
      d["v"].append((m.logMonoTime, m.carState.vEgo))
    elif w == "modelV2":
      try:
        ld = m.modelV2.leadsV3[0]
        d["model"].append((m.logMonoTime, ld.prob, ld.x[0], ld.y[0], ld.v[0]))
      except Exception:  # noqa: BLE001
        pass
    elif w == "extrinsicsCalibration" and d["calib"] is None:
      c = m.extrinsicsCalibration
      if len(c.rpyCalib) == 3:
        h = list(c.height)
        d["calib"] = (list(c.rpyCalib), h[0] if h else 1.22)
    elif w == "initData" and d["device"] is None:
      d["device"] = str(m.initData.deviceType)
    elif w == "narrowRoadCameraState" and d["sensor"] is None:
      d["sensor"] = str(m.narrowRoadCameraState.sensor)
    elif w == "qNarrowRoadEncodeIdx":
      e = m.qNarrowRoadEncodeIdx
      d["enc"][int(e.segmentId)] = int(e.timestampSof) or m.logMonoTime
    elif w == "carParams" and d["platform"] is None:
      d["platform"] = m.carParams.carFingerprint
  return d


class Projector:
  def __init__(self, device, sensor, rpy, height, qw, qh):
    from openpilot.common.transformations.camera import DEVICE_CAMERAS, get_view_frame_from_road_frame
    key = (device, sensor)
    if key not in DEVICE_CAMERAS:
      key = (device, "ar0231") if (device, "ar0231") in DEVICE_CAMERAS else ("tici", "ar0231")
    cam = DEVICE_CAMERAS[key].narrow_road
    self.KE = cam.intrinsics @ get_view_frame_from_road_frame(rpy[0], rpy[1], rpy[2], height)
    self.sx, self.sy = qw / cam.width, qh / cam.height

  def __call__(self, x, y, z):
    p = self.KE @ np.array([x, y, z, 1.0])
    if p[2] <= 0.5:
      return None
    return (p[0] / p[2] * self.sx, p[1] / p[2] * self.sy)


def latest(ts, vals, t, max_age=0.25e9):
  i = bisect.bisect_right(ts, t) - 1
  if i < 0 or t - ts[i] > max_age:
    return None
  return vals[i]


def decode_frames(qcam, w, h):
  proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", qcam, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
  n = w * h * 3
  k = 0
  while True:
    buf = proc.stdout.read(n)
    if len(buf) < n:
      break
    yield k, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    k += 1
  proc.wait()


def source_kind_map(sources):
  return {(s, e, b): kind for s, e, b, _, kind in sources}


def kind_of(point, sources):
  _, _, _, _, _, addr, bus = point
  for s, e, b, _, kind in sources:
    if b == bus and s <= addr <= e:
      return kind
  return 0


def match_lead(points, model, v_ego):
  if model is None:
    return None
  _, prob, mx, my, mv = model
  if prob < 0.5 or mx > 90:
    return None
  best = None
  for p in points:
    d, y, v = p[1], p[2], p[3]
    if abs(d - (mx - RADAR_TO_CAMERA)) < 3 + 0.05 * mx and abs(y - (-my)) < 1.8 and abs(v - (mv - v_ego)) < 3.0:
      if best is None or abs(d - (mx - RADAR_TO_CAMERA)) < abs(best[1] - (mx - RADAR_TO_CAMERA)):
        best = p
  return best


def draw_box(dr, proj, x, y, w, h, length, color, width=2, scale=1.0):
  corners = {}
  for dx in (0, length):
    for dy in (-w / 2, w / 2):
      for dz in (0, h):
        q = proj(x + dx, y + dy, dz)
        if q is None:
          return False
        corners[(dx, dy, dz)] = (q[0] * scale, q[1] * scale)
  rear = [corners[(0, -w / 2, 0)], corners[(0, w / 2, 0)], corners[(0, w / 2, h)], corners[(0, -w / 2, h)]]
  dr.line(rear + [rear[0]], fill=color, width=width)
  faded = tuple(int(c * 0.55) for c in color)
  for dy in (-w / 2, w / 2):
    for dz in (0, h):
      dr.line([corners[(0, dy, dz)], corners[(length, dy, dz)]], fill=faded, width=1)
  far = [corners[(length, -w / 2, 0)], corners[(length, w / 2, 0)], corners[(length, w / 2, h)], corners[(length, -w / 2, h)]]
  dr.line(far + [far[0]], fill=faded, width=1)
  return rear


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--rlog", required=True)
  ap.add_argument("--qcam", required=True)
  ap.add_argument("--dump", required=True)
  ap.add_argument("--ref-dump", help="before-fix dump drawn in red")
  ap.add_argument("--ref-label", default="before fix")
  ap.add_argument("--dump-label", default="")
  ap.add_argument("--extra", help="research overlay dump (same format) drawn in purple")
  ap.add_argument("--extra-label", default="research candidate")
  ap.add_argument("--start", type=float, default=0.0, help="seconds from first frame")
  ap.add_argument("--dur", type=float, default=10.0)
  ap.add_argument("--fps", type=int, default=8)
  ap.add_argument("--range", type=float, default=60.0, help="bird's-eye range (m)")
  ap.add_argument("--title", required=True)
  ap.add_argument("--subtitle", default="")
  ap.add_argument("--out", required=True)
  ap.add_argument("--scale", type=float, default=1.45)
  a = ap.parse_args()

  log = load_log(a.rlog)
  dump = pickle.load(open(a.dump, "rb"))
  ref = pickle.load(open(a.ref_dump, "rb")) if a.ref_dump else None
  extra = pickle.load(open(a.extra, "rb")) if a.extra else None
  out_ts = [o[0] for o in dump["outputs"]]
  ref_ts = [o[0] for o in ref["outputs"]] if ref else []
  ex_ts = [o[0] for o in extra["outputs"]] if extra else []
  v_ts, v_vals = [x[0] for x in log["v"]], [x[1] for x in log["v"]]
  m_ts = [x[0] for x in log["model"]]

  probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", a.qcam], capture_output=True, text=True).stdout.strip().splitlines()[0].split(",")
  qw, qh = int(probe[0]), int(probe[1])
  rpy, height = log["calib"] or ([0.0, 0.0, 0.0], 1.22)
  proj = Projector(log["device"], log["sensor"], rpy, height, qw, qh)

  S = a.scale
  VW, VH = int(qw * S), int(qh * S)
  PW = 400
  HEAD, FOOT = 58, 34
  W, H = VW + PW, VH + HEAD + FOOT
  f_title, f_sub, f_lbl, f_small = font(20, "SemiBold"), font(13), font(13, "SemiBold"), font(11)

  enc = log["enc"]
  first_t = enc[min(enc)] if enc else None
  step = max(1, round(20 / a.fps))
  trails: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=int(a.fps * 1.5)))
  tmp = tempfile.mkdtemp(prefix="radar_media_")
  n_out = 0
  for k, frame in decode_frames(a.qcam, qw, qh):
    t = enc.get(k)
    if t is None or first_t is None:
      continue
    rel = (t - first_t) / 1e9
    if rel < a.start:
      continue
    if rel > a.start + a.dur:
      break
    if k % step:
      continue
    v_ego = latest(v_ts, v_vals, t, 1e9) or 0.0
    model = latest(m_ts, log["model"], t, 0.3e9)
    out = latest(out_ts, dump["outputs"], t)
    points, sources = (out[1], out[2]) if out else ([], [])
    lead = match_lead(points, model, v_ego)
    ref_out = latest(ref_ts, ref["outputs"], t) if ref else None
    ex_out = latest(ex_ts, extra["outputs"], t) if extra else None

    img = Image.new("RGB", (W, H), BG)
    vid = Image.fromarray(frame).resize((VW, VH), Image.BILINEAR)
    img.paste(vid, (0, HEAD))
    ov = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)

    # range lines on the road
    for r in (10, 20, 30, 50):
      a_ = proj(r, 6.0, 0)
      b_ = proj(r, -6.0, 0)
      if a_ and b_:
        dr.line([(a_[0] * S, a_[1] * S), (b_[0] * S, b_[1] * S)], fill=(255, 255, 255, 70), width=1)
        dr.text((b_[0] * S + 4, b_[1] * S - 8), f"{r} m", fill=(255, 255, 255, 140), font=f_small)

    def draw_points(pts, srcs, mode):
      for p in sorted(pts, key=lambda q: -q[1]):
        tid, d, y, v, motion, addr, bus = p
        x = d + RADAR_TO_CAMERA
        if x < 3 or x > 120 or abs(y) > 25:
          continue
        camera = kind_of(p, srcs) == 1
        moving = motion == 2 or (v_ego > 2 and abs(v + v_ego) > 1.5) or (v_ego <= 2 and abs(v) > 1.0)
        if mode == "ref":
          c = proj(x, y, 0)
          if c:
            cx, cy = c[0] * S, c[1] * S
            r = max(3, 9 - x / 12)
            dr.line([(cx - r, cy - r), (cx + r, cy + r)], fill=BEFORE + (230,), width=2)
            dr.line([(cx - r, cy + r), (cx + r, cy - r)], fill=BEFORE + (230,), width=2)
          continue
        if mode == "extra":
          c = proj(x, y, 0)
          if c:
            cx, cy = c[0] * S, c[1] * S
            r = max(2, 6 - x / 20)
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=EXTRA + (230,), width=2)
          continue
        is_lead = lead is not None and p[0] == lead[0]
        if moving or is_lead:
          color = LEAD if is_lead else (CAMERA if camera else RADAR)
          rear = draw_box(dr, proj, x, y, 1.8, 1.5, 4.0, color + (255,), width=3 if is_lead else 2, scale=S)
          if rear and (is_lead or camera):
            lx = min(q[0] for q in rear)
            ly = min(q[1] for q in rear)
            tag = ("CAM " if camera else "") + (f"{d:.1f} m" if is_lead else "")
            dr.text((lx, ly - 18), tag.strip(), fill=(TEXT if is_lead else CAMERA) + (255,), font=f_lbl if is_lead else f_small)
        else:
          c = proj(x, y, 0)
          top = proj(x, y, 0.6)
          if c and top:
            col = (CAMERA if camera else RADAR_STAT) + (200,)
            dr.line([(c[0] * S, c[1] * S), (top[0] * S, top[1] * S)], fill=col, width=2)

    if ref_out:
      draw_points(ref_out[1], ref_out[2], "ref")
    if ex_out:
      draw_points(ex_out[1], ex_out[2], "extra")
    draw_points(points, sources, "main")
    if model and model[1] > 0.5:
      c = proj(model[2], -model[3], 0)
      if c:
        cx, cy = c[0] * S, c[1] * S
        dr.ellipse([cx - 7, cy - 4, cx + 7, cy + 4], outline=VISION + (255,), width=2)
    img.paste(ov, (0, HEAD), ov)

    # bird's-eye panel
    px0, py0 = VW, HEAD
    d = ImageDraw.Draw(img)
    d.rectangle([px0, py0, W, py0 + VH], fill=PANEL)
    R, LAT = a.range, 15.0
    n_src = max(1, len(sources))
    top_pad = 34 + 14 * n_src
    ppm_y = (VH - 40 - top_pad) / R
    ppm_x = (PW - 40) / (2 * LAT)
    ox, oy = px0 + PW / 2, py0 + VH - 40

    def to_px(xf, yl):
      return ox - yl * ppm_x, oy - xf * ppm_y
    for r in range(0, int(R) + 1, 10):
      _, yy = to_px(r, 0)
      d.line([(px0 + 30, yy), (W - 10, yy)], fill=GRID, width=1)
      d.text((px0 + 6, yy - 7), f"{r}", fill=MUTED, font=f_small)
    for lane in (-5.4, -1.8, 1.8, 5.4):
      xx, _ = to_px(0, lane)
      for yy in range(int(oy - R * ppm_y), int(oy), 10):
        d.line([(xx, yy), (xx, yy + 5)], fill=GRID, width=1)
    ex_, ey_ = to_px(-RADAR_TO_CAMERA, 0)
    d.rounded_rectangle([ex_ - 9, ey_ - 4, ex_ + 9, ey_ + 30], radius=5, outline=TEXT, width=2)

    for p in points:
      key = ("m", p[0])
      trails[key].append((p[1], p[2]))
    alive = {("m", p[0]) for p in points}
    for key in list(trails):
      if key not in alive:
        trails[key].popleft() if trails[key] else None
        if not trails[key]:
          del trails[key]
    for key, tr in trails.items():
      if len(tr) > 1:
        d.line([to_px(dd, yy) for dd, yy in tr], fill=(70, 80, 92), width=1)
    if ref_out:
      for p in ref_out[1]:
        if 0 < p[1] < R and abs(p[2]) < LAT:
          cx, cy = to_px(p[1], p[2])
          d.line([(cx - 4, cy - 4), (cx + 4, cy + 4)], fill=BEFORE, width=2)
          d.line([(cx - 4, cy + 4), (cx + 4, cy - 4)], fill=BEFORE, width=2)
    if ex_out:
      for p in ex_out[1]:
        if 0 < p[1] < R and abs(p[2]) < LAT:
          cx, cy = to_px(p[1], p[2])
          d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=EXTRA, width=2)
    for p in points:
      if not (0 < p[1] < R and abs(p[2]) < LAT):
        continue
      cx, cy = to_px(p[1], p[2])
      camera = kind_of(p, sources) == 1
      is_lead = lead is not None and p[0] == lead[0]
      if camera:
        col = LEAD if is_lead else CAMERA
        d.polygon([(cx, cy - 6), (cx - 6, cy + 5), (cx + 6, cy + 5)], fill=col)
      else:
        moving = p[4] == 2 or (v_ego > 2 and abs(p[3] + v_ego) > 1.5)
        col = LEAD if is_lead else (RADAR if moving else RADAR_STAT)
        r = 6 if is_lead else (4 if moving else 3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
      if is_lead:
        d.text((cx + 9, cy - 8), f"{p[1]:.1f} m", fill=TEXT, font=f_lbl)
    if model and model[1] > 0.5 and model[2] - RADAR_TO_CAMERA < R:
      cx, cy = to_px(model[2] - RADAR_TO_CAMERA, -model[3])
      d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=VISION, width=2)
    d.text((px0 + 12, py0 + 8), "Bird's-eye (radar frame)", fill=TEXT, font=f_lbl)
    d.text((W - 80, py0 + 8), f"t {rel:4.1f} s", fill=MUTED, font=f_small)
    yline = py0 + 26
    for s, e, b, cnt, kind in sources:
      label = f"{'CAM ' if kind == 1 else ''}{s:X}-{e:X} bus {b}: {cnt}"
      d.text((px0 + 12, yline), label, fill=CAMERA if kind == 1 else RADAR, font=f_small)
      yline += 14

    # header + footer
    d.text((14, 8), a.title, fill=TEXT, font=f_title)
    d.text((14, 34), a.subtitle or f"{dump['platform']}  ·  v_ego {v_ego * 3.6:4.0f} km/h", fill=MUTED, font=f_sub)
    fx, fy = 14, H - FOOT + 9

    def legend(col, text, shape):
      nonlocal fx
      if shape == "box":
        d.rectangle([fx, fy + 2, fx + 12, fy + 12], outline=col, width=2)
      elif shape == "tri":
        d.polygon([(fx + 6, fy + 1), (fx, fy + 13), (fx + 12, fy + 13)], fill=col)
      elif shape == "ring":
        d.ellipse([fx, fy + 1, fx + 12, fy + 13], outline=col, width=2)
      elif shape == "x":
        d.line([(fx, fy + 2), (fx + 11, fy + 13)], fill=col, width=2)
        d.line([(fx, fy + 13), (fx + 11, fy + 2)], fill=col, width=2)
      else:
        d.ellipse([fx + 2, fy + 3, fx + 10, fy + 11], fill=col)
      d.text((fx + 17, fy), text, fill=MUTED, font=f_small)
      fx += 24 + int(d.textlength(text, font=f_small)) + 18
    has_radar = any(s[4] != 1 for s in sources) or not sources
    has_cam = any(s[4] == 1 for s in sources)
    legend(LEAD, "track matched to vision lead", "box")
    if has_radar:
      legend(RADAR, "moving radar track", "box")
      legend(RADAR_STAT, "stationary return", "dot")
    if has_cam:
      legend(CAMERA, "camera object (CAM source)", "tri")
    legend(VISION, "model lead (vision)", "ring")
    if ref:
      legend(BEFORE, a.ref_label, "x")
    if extra:
      legend(EXTRA, a.extra_label, "ring")

    img.save(os.path.join(tmp, f"f{n_out:04d}.png"))
    n_out += 1

  if n_out == 0:
    raise SystemExit("no frames rendered (check --start/--dur and encode index)")
  base = os.path.splitext(a.out)[0]
  subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps), "-i", os.path.join(tmp, "f%04d.png"),
                  "-vf", "split[s0][s1];[s0]palettegen=max_colors=64:stats_mode=diff[p];"
                  "[s1][p]paletteuse=dither=none:diff_mode=rectangle", base + ".gif"], check=True)
  subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps), "-i", os.path.join(tmp, "f%04d.png"),
                  "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
                  base + ".mp4"], check=True)
  shutil.copy(os.path.join(tmp, f"f{n_out // 2:04d}.png"), base + ".png")
  shutil.rmtree(tmp)
  print(f"{base}.gif ({os.path.getsize(base + '.gif') / 1e6:.1f} MB), {n_out} frames")


if __name__ == "__main__":
  main()
