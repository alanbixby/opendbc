#!/usr/bin/env python3
"""Unvalidated MDX object-list capture layout. Deliberately not used by RadarInterface."""


def generate():
  parts = ['VERSION ""\nNS_ :\n CM_\nBS_:\nBU_: XXX\n']
  parts.append('CM_ "RESEARCH ONLY: bus 1, Acura MDX 4G MMR, stock longitudinal. ' +
               'No validated distance/speed/validity decode; do not publish these values as RadarData.";\n')
  parts.append('''
BO_ 96 OBJECT_CYCLE_RESEARCH: 16 XXX
 SG_ HEADER_0_RAW : 0|16@1+ (1,0) [0|65535] "" XXX
 SG_ SEQUENCE_8 : 16|8@1+ (1,0) [0|255] "" XXX
 SG_ SEQUENCE_4 : 24|4@1+ (1,0) [0|15] "" XXX
 SG_ HEADER_3_HIGH_RAW : 28|4@1+ (1,0) [0|15] "" XXX
 SG_ COUNT_CANDIDATE_RAW : 32|8@1+ (1,0) [0|255] "" XXX
 SG_ BYTES_5_7_RAW : 40|24@1+ (1,0) [0|16777215] "" XXX
 SG_ TIME_CANDIDATE_RAW : 64|32@1+ (1,0) [0|4294967295] "" XXX
 SG_ BYTES_12_15_RAW : 96|32@1+ (1,0) [0|4294967295] "" XXX
CM_ SG_ 96 COUNT_CANDIDATE_RAW "Matches nonzero byte-4 slots in only 69..92 percent of complete following cycles. NOT a validated count or validity rule.";
CM_ SG_ 96 TIME_CANDIDATE_RAW "Usually advances 66/67 per cycle; linear with log time. Millisecond timer candidate; origin/rollover UNKNOWN.";
''')
  for addr in range(0x62, 0x81, 2):
    parts.append(f"""
BO_ {addr} RADAR_TRACK_{addr:x}: 64 XXX
 SG_ HEADER_0_RAW : 0|16@1+ (1,0) [0|65535] "" XXX
 SG_ SEQUENCE_8 : 16|8@1+ (1,0) [0|255] "" XXX
 SG_ SEQUENCE_4 : 24|4@1+ (1,0) [0|15] "" XXX
 SG_ HEADER_3_HIGH_RAW : 28|4@1+ (1,0) [0|15] "" XXX
 SG_ OBJECT_ID_RAW : 32|8@1+ (1,0) [0|255] "" XXX
 SG_ BYTE_5_RAW : 40|8@1+ (1,0) [0|255] "" XXX
 SG_ POSITION_X_RAW : 48|16@1+ (1,0) [0|65535] "" XXX
 SG_ POSITION_X_LOW_12_RAW : 48|12@1+ (1,0) [0|4095] "" XXX
 SG_ POSITION_X_HIGH_RAW : 60|4@1+ (1,0) [0|15] "" XXX
 SG_ POSITION_Y_RAW : 64|16@1+ (1,0) [0|65535] "" XXX
 SG_ POSITION_Y_LOW_13_RAW : 64|13@1- (1,0) [-4096|4095] "" XXX
 SG_ POSITION_Y_HIGH_RAW : 77|3@1+ (1,0) [0|7] "" XXX
 SG_ VELOCITY_RAW : 80|11@1+ (1,0) [0|2047] "" XXX
 SG_ BYTE_11_HIGH_RAW : 91|5@1+ (1,0) [0|31] "" XXX
""")
    # Expose the unexplained tail without assigning a second object or geometry.
    for byte in range(12, 64):
      parts.append(f' SG_ PAYLOAD_BYTE_{byte}_RAW : {byte * 8}|8@1+ (1,0) [0|255] "" XXX\n')
    comments = {
      'HEADER_0_RAW': 'Checksum-like changing header; algorithm and coverage UNKNOWN. Not integrity checked.',
      'SEQUENCE_8': 'Observed increment modulo 256 per slot frame. Independent of SEQUENCE_4; not one 16-bit counter.',
      'SEQUENCE_4': 'Observed increment modulo 16 per slot frame.',
      'OBJECT_ID_RAW': 'Observed values 0..63. Zero is an empty-slot candidate; complete validity semantics UNKNOWN.',
      'POSITION_X_RAW': 'Original 16-bit hypothesis fails. Retained for comparison; high nibble must be investigated independently.',
      'POSITION_X_LOW_12_RAW': 'Candidate x = raw*0.04 m removes high-bit jumps, but fails kinematics and lead matching. Calibration UNKNOWN.',
      'POSITION_X_HIGH_RAW': 'Observed 1,3,6,7,8,9,10 on active slots. Flags/state vs additional range bits unresolved; do not use as validity.',
      'POSITION_Y_RAW': 'Original raw word retained. See signed lower-13-bit candidate; no general physical decode certified.',
      'POSITION_Y_LOW_13_RAW': 'Candidate left-positive y = raw*0.01 m. Vision and conditional turn geometry support sign; width/scale provisional.',
      'VELOCITY_RAW': 'Candidate relative speed = raw*0.08 - 122.88 m/s. Fails kinematic validation; width/scale/offset unresolved.',
    }
    for signal, comment in comments.items():
      parts.append(f'CM_ SG_ {addr} {signal} "{comment}";\n')
  return {'acura_mdx_4g_objects_research.dbc': ''.join(parts)}
