"""Captured-frame regression for research bit extraction, not physical signal validation."""
from opendbc.can import CANParser


def test_mdx_captured_object_and_empty_slot():
  # ad9840558640c31d/0000001a--d6cd4871c2, segment 1, first 0x62.
  active = bytes.fromhex(
    'c68b7f03190018137e60f405f92500621b9c08000100030801fc0fb8840275b8140045050900e7ff004b0088133901f87f48203684eb30211000000800080000')
  # Same route, segment 0, first empty 0x80: payload is NOT zero-filled.
  empty = bytes.fromhex(
    '3e47e50900000000ff1fe402fe010000409c0000000000000000080074020000000000000000000001000088130000f83f0000f07ffe0ffe0f00000000000000')
  parser = CANParser('acura_mdx_4g_objects_research_generated', [(0x62, 15), (0x80, 15)], 1)
  parser.update([(1_000_000_000, [(0x62, active, 1), (0x80, empty, 1)])])
  lead = parser.vl[0x62]
  assert lead['HEADER_0_RAW'] == 0x8bc6
  assert lead['SEQUENCE_8'] == 127
  assert lead['SEQUENCE_4'] == 3
  assert lead['OBJECT_ID_RAW'] == 25
  assert lead['POSITION_X_RAW'] == 4888
  assert lead['POSITION_Y_RAW'] == 24702
  assert lead['VELOCITY_RAW'] == 1524
  assert parser.vl[0x80]['OBJECT_ID_RAW'] == 0
  assert parser.vl[0x80]['POSITION_Y_RAW'] == 8191
  assert parser.vl[0x80]['VELOCITY_RAW'] == 740
