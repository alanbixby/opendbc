#!/usr/bin/env python3
"""Fetch qcamera, dump RadarData from a fork branch (and an optional 'before' branch), pick the best window, render.

  PYTHONPATH=/home/bxb/Develop/sunnypilot-ui python pr_media.py --route <dongle>/<route> --seg N --branch radar-238-family \
      [--ref-branch hyundai-radar-tracks] [--platform X] --title "..." --out out/pr6_k5
"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path("/home/bxb/Develop/radar-tracks")
SP = "/home/bxb/Develop/sunnypilot-ui"
PY = f"{SP}/.venv/bin/python"
MEDIA = ROOT / "media"


def worktree(branch):
  wt = ROOT / "review-tmp" / f"media-{branch}"
  subprocess.run(["git", "-C", str(ROOT / "opendbc"), "fetch", "-q", "origin", branch], check=True)
  if wt.exists():
    subprocess.run(["git", "-C", str(wt), "checkout", "-q", "--detach", f"origin/{branch}"], check=True)
  else:
    subprocess.run(["git", "-C", str(ROOT / "opendbc"), "worktree", "add", "-q", "--detach", str(wt), f"origin/{branch}"], check=True)
  return wt


def qcamera(route, seg):
  dongle, rname = route.split("/")
  dest = ROOT / "cache" / dongle / rname / f"{seg}--qcamera.ts"
  if dest.exists() and dest.stat().st_size > 0:
    return dest
  tok = json.load(open(Path.home() / ".comma/auth.json"))["access_token"]
  files = json.loads(subprocess.run(["curl", "-s", "-H", f"Authorization: JWT {tok}",
                                     f"https://api.commadotai.com/v1/route/{dongle}%7C{rname}/files"],
                                    capture_output=True, text=True).stdout)
  for u in files.get("qcameras", []):
    if urllib.parse.urlparse(u).path.rstrip("/").split("/")[-2] == str(seg):
      subprocess.run(["curl", "-s", "-f", "-o", str(dest), u], check=True)
      return dest
  raise SystemExit(f"no qcamera for {route} seg {seg}")


def dump(branch, rlog, out, platform):
  wt = worktree(branch)
  cmd = [PY, str(MEDIA / "dump_radar.py"), str(rlog), "--out", str(out)]
  if platform:
    cmd += ["--platform", platform]
  env = dict(os.environ, PYTHONPATH=f"{wt}:{SP}")
  r = subprocess.run(cmd, env=env, cwd=str(MEDIA), capture_output=True, text=True)
  if r.returncode:
    raise SystemExit(r.stderr[-2000:])
  print(r.stdout.strip())


def best_window(rlog, dump_path, dur):
  sys.path.insert(0, str(MEDIA))
  from render_media import load_log, match_lead, latest
  log = load_log(str(rlog))
  d = pickle.load(open(dump_path, "rb"))
  enc = log["enc"]
  t0 = enc[min(enc)]
  m_ts = [x[0] for x in log["model"]]
  v_ts, v_vals = [x[0] for x in log["v"]], [x[1] for x in log["v"]]
  hits = []
  for t, pts, _ in d["outputs"]:
    model = latest(m_ts, log["model"], t, 0.3e9)
    v = latest(v_ts, v_vals, t, 1e9) or 0.0
    lead = match_lead(pts, model, v) if model else None
    hits.append(((t - t0) / 1e9, 1 if lead else 0, len(pts), v))
  span = (max(enc) - min(enc)) / 20.0
  best, best_s = -1, 0.0
  s = 0.0
  while s + dur <= span:
    w = [h for h in hits if s <= h[0] < s + dur]
    score = sum(h[1] for h in w) * 3 + sum(min(h[2], 8) for h in w) * 0.2 + sum(1 for h in w if h[3] > 3)
    if score > best:
      best, best_s = score, s
    s += 1.0
  return best_s


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--route", required=True)
  ap.add_argument("--seg", type=int, required=True)
  ap.add_argument("--branch", required=True)
  ap.add_argument("--ref-branch")
  ap.add_argument("--ref-label", default="before this PR")
  ap.add_argument("--platform")
  ap.add_argument("--title", required=True)
  ap.add_argument("--subtitle", default="")
  ap.add_argument("--out", required=True)
  ap.add_argument("--start", type=float)
  ap.add_argument("--dur", type=float, default=8.0)
  ap.add_argument("--range", type=float, default=60.0)
  a = ap.parse_args()
  dongle, rname = a.route.split("/")
  rlog = ROOT / "cache" / dongle / rname / f"{a.seg}--rlog.zst"
  qcam = qcamera(a.route, a.seg)
  out = Path(a.out)
  out.parent.mkdir(parents=True, exist_ok=True)
  after = out.with_suffix(".after.pkl")
  dump(a.branch, rlog, after, a.platform)
  ref = None
  if a.ref_branch:
    ref = out.with_suffix(".before.pkl")
    dump(a.ref_branch, rlog, ref, a.platform)
  start = a.start if a.start is not None else best_window(rlog, after, a.dur)
  sub = a.subtitle or (f"{a.route} seg {a.seg} · branch {a.branch} · boxes = RadarData points projected with the logged "
                       "calibration (no image recognition)")
  cmd = [PY, str(MEDIA / "render_media.py"), "--rlog", str(rlog), "--qcam", str(qcam), "--dump", str(after),
         "--start", str(start), "--dur", str(a.dur), "--fps", "7", "--scale", "1.3", "--range", str(a.range),
         "--title", a.title, "--subtitle", sub, "--out", str(out.with_suffix(".gif"))]
  if ref:
    cmd += ["--ref-dump", str(ref), "--ref-label", a.ref_label]
  r = subprocess.run(cmd, env=dict(os.environ, PYTHONPATH=SP), cwd=str(MEDIA), capture_output=True, text=True)
  print("\n".join(line for line in (r.stdout + r.stderr).splitlines() if "MB" in line or "Error" in line and "pipe" not in line))
  print(f"window start {start:.0f} s")


if __name__ == "__main__":
  main()
