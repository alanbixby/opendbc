#!/usr/bin/env python3
"""Replay rlog CAN through the IMPORTED opendbc's RadarInterface and dump every RadarData output.

Run with the opendbc checkout under test first on PYTHONPATH:
  PYTHONPATH=<opendbc>:/home/bxb/Develop/sunnypilot-ui python dump_radar.py <rlog>... --out dump.pkl [--platform X]

The pickle holds {"platform", "outputs": [(t_ns, points, sources)]} where
points = [(trackId, dRel, yRel, vRel, motionState, sourceAddress, sourceBus)] and
sources = [(startAddress, endAddress, bus, trackCount, sourceKind)].
"""
import argparse
import pickle


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("rlogs", nargs="+")
  ap.add_argument("--out", required=True)
  ap.add_argument("--platform")
  ap.add_argument("--fp-seconds", type=float, default=10.0)
  a = ap.parse_args()

  from openpilot.tools.lib.logreader import LogReader
  from opendbc.car import gen_empty_fingerprint
  from opendbc.car.structs import CarParamsSP

  can, platform = [], a.platform
  for path in a.rlogs:
    for m in LogReader(path):
      w = m.which()
      if w == "can":
        can.append((m.logMonoTime, [(c.address, bytes(c.dat), c.src) for c in m.can if c.src < 128]))
      elif w == "carParams" and platform is None:
        platform = m.carParams.carFingerprint

  fp = gen_empty_fingerprint()
  t0 = can[0][0]
  for t, msgs in can:
    if t - t0 > a.fp_seconds * 1e9:
      break
    for addr, dat, bus in msgs:
      if bus in fp:
        fp[bus][addr] = len(dat)

  if platform.startswith(("HONDA", "ACURA")):
    from opendbc.car.honda.interface import CarInterface
    from opendbc.car.honda.radar_interface import RadarInterface
    CP = CarInterface.get_params(platform, fp, [], False, False, False)
    RI = RadarInterface(CP, CarParamsSP())
  else:
    from opendbc.car.hyundai.interface import CarInterface
    from opendbc.car.hyundai.radar_interface import RadarInterface
    from opendbc.sunnypilot.car.hyundai.values import HyundaiFlagsSP
    CP = CarInterface.get_params(platform, fp, [], False, False, False)
    RI = RadarInterface(CP, CarParamsSP(flags=HyundaiFlagsSP.RADAR_FULL_RADAR.value))

  outputs = []
  for t, msgs in can:
    rr = RI.update([(t, msgs)])
    if rr is None:
      continue
    points = [(p.trackId, p.dRel, p.yRel, p.vRel, int(getattr(p, "motionState", 0)), int(getattr(p, "sourceAddress", 0)),
               int(getattr(p, "sourceBus", 0))) for p in rr.points]
    sources = [(s.startAddress, s.endAddress, s.bus, s.trackCount, int(getattr(s, "sourceKind", 0)))
               for s in getattr(rr, "trackSources", [])]
    outputs.append((t, points, sources))

  with open(a.out, "wb") as f:
    pickle.dump({"platform": platform, "radarUnavailable": CP.radarUnavailable, "outputs": outputs}, f)
  print(f"{a.out}: {len(outputs)} outputs, platform {platform}")


if __name__ == "__main__":
  main()
