from opendbc.car import Bus, gen_empty_fingerprint, structs
from opendbc.car.honda.interface import CarInterface
from opendbc.car.honda.radar_interface import RadarInterface
from opendbc.car.honda.values import CAR, DBC, HondaFlags


# a468064f19bc0267/00000001--6a0c7d2514 segment 4, bus 1.
# A complete scan, including unoccupied slots and the diagnostic message.
CLARITY_SCAN = {
  0x400: "7900000012de0024",
  0x430: "3b84e30000f00025", 0x431: "6955280008f00024",
  0x432: "05204d0008f00268", 0x433: "fff0000000f00020",
  0x434: "70211cfff0f00028", 0x435: "03b3fffff8f00027",
  0x436: "fff0000000f0002d", 0x437: "fff0000000f0002c",
  0x438: "fff0000000f0002b", 0x439: "0700030008f00025",
  0x440: "03a004fff8f00029", 0x441: "0393f4fff8f00027",
  0x442: "fff0000000f00020", 0x443: "fff0000000f0002f",
  0x444: "fff0000000f0002e", 0x445: "fff0000000f0002d",
}


def make_radar(platform):
  cp = CarInterface.get_params(platform, gen_empty_fingerprint(), [], False, False, False)
  return cp, RadarInterface(cp, structs.CarParamsSP())


def scan(radar, frames=CLARITY_SCAN, bus=1, timestamp=1_000_000_000):
  return radar.update([(timestamp, [(addr, bytes.fromhex(data), bus) for addr, data in frames.items()])])


def test_clarity_captured_scan():
  cp, radar = make_radar(CAR.HONDA_CLARITY)
  assert cp.flags & HondaFlags.NIDEC
  assert cp.openpilotLongitudinalControl
  assert not cp.radarUnavailable
  assert DBC[CAR.HONDA_CLARITY][Bus.radar] == 'acura_ilx_2016_nidec'
  result = scan(radar)
  assert len(result.points) == 8
  assert not result.errors.radarFault
  assert not result.errors.wrongConfig
  assert result.radarTracksAvailable
  assert [(s.startAddress, s.endAddress, s.bus, s.trackCount) for s in result.trackSources] == [(0x430, 0x445, 1, 8)]
  point = radar.pts[0x430]
  assert (point.dRel, point.yRel, point.vRel) == (59.5, -14.1875, 0)
  point = radar.pts[0x435]
  assert (point.dRel, point.yRel, point.vRel) == (3.6875, 0.0625, -0.03125)
  assert 0x433 not in radar.pts
  old_id = point.trackId
  scan(radar, {0x435: 'fff0000000f00020', 0x445: CLARITY_SCAN[0x445]}, timestamp=1_050_000_000)
  assert 0x435 not in radar.pts
  scan(radar, timestamp=1_100_000_000)
  assert radar.pts[0x435].trackId > old_id


def test_clarity_bus_and_scan_boundary():
  _, radar = make_radar(CAR.HONDA_CLARITY)
  assert scan(radar, bus=0) is None
  assert scan(radar, {a: d for a, d in CLARITY_SCAN.items() if a != 0x445}) is None
  assert scan(radar, {0x445: CLARITY_SCAN[0x445]}) is not None


def test_nidec_reports_track_source():
  cp, radar = make_radar(CAR.HONDA_CIVIC)
  assert not cp.radarUnavailable
  result = scan(radar)
  assert len(result.points) == 8
  assert result.radarTracksAvailable
  assert [(s.startAddress, s.endAddress, s.bus, s.trackCount) for s in result.trackSources] == [(0x430, 0x445, 1, 8)]


def test_bosch_without_radar_reports_no_source():
  cp, radar = make_radar(CAR.ACURA_MDX_4G_MMR)
  assert cp.radarUnavailable
  assert radar.rcp is None
  results = [radar.update(None) for _ in range(5)]
  assert results[:4] == [None] * 4
  result = results[4]
  assert result is not None
  assert not result.points
  assert not result.trackSources
  assert not result.radarTracksAvailable
