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
  assert lead['POSITION_X_LOW_12_RAW'] == 792
  assert lead['POSITION_X_HIGH_RAW'] == 1
  assert lead['POSITION_Y_RAW'] == 24702
  assert lead['POSITION_Y_LOW_13_RAW'] == 126
  assert lead['POSITION_Y_HIGH_RAW'] == 3
  assert lead['VELOCITY_RAW'] == 1524
  assert parser.vl[0x80]['OBJECT_ID_RAW'] == 0
  assert parser.vl[0x80]['POSITION_Y_RAW'] == 8191
  assert parser.vl[0x80]['VELOCITY_RAW'] == 740
  assert parser.vl[0x80]['POSITION_Y_LOW_13_RAW'] == -1
  for byte in range(12, 64):
    assert lead[f'PAYLOAD_BYTE_{byte}_RAW'] == active[byte]
    assert parser.vl[0x80][f'PAYLOAD_BYTE_{byte}_RAW'] == empty[byte]


def test_mdx_cycle_header_and_high_position_bits():
  # Same route: segment 1 first 0x60; segment 3 0x74 at 232693936523 ns.
  header = bytes.fromhex('b21a930302010008c7c2010000000000')
  active = bytes.fromhex(
    'b81a0e021f00ad76ca258005fe010014439d8b01af00034007fc0f0074027f0008800000fe035800010d0188136001f87f00002c96d632b31200000200020000')
  parser = CANParser('acura_mdx_4g_objects_research_generated', [(0x60, 15), (0x74, 15)], 1)
  parser.update([(1_000_000_000, [(0x60, header, 1), (0x74, active, 1)])])
  assert parser.vl[0x60]['SEQUENCE_8'] == 147
  assert parser.vl[0x60]['SEQUENCE_4'] == 3
  assert parser.vl[0x60]['COUNT_CANDIDATE_RAW'] == 2
  assert parser.vl[0x60]['TIME_CANDIDATE_RAW'] == 115399
  assert parser.vl[0x60]['BYTES_5_7_RAW'] == 0x080001
  assert parser.vl[0x74]['OBJECT_ID_RAW'] == 31
  assert parser.vl[0x74]['POSITION_X_RAW'] == 0x76ad
  assert parser.vl[0x74]['POSITION_X_LOW_12_RAW'] == 0x6ad
  assert parser.vl[0x74]['POSITION_X_HIGH_RAW'] == 7
  assert parser.vl[0x74]['POSITION_Y_LOW_13_RAW'] == 1482
  for byte in range(12, 64):
    assert parser.vl[0x74][f'PAYLOAD_BYTE_{byte}_RAW'] == active[byte]
