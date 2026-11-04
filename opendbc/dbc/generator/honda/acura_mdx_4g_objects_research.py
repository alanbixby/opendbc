"""Unvalidated MDX object-list capture layout. Deliberately not used by RadarInterface."""


def generate():
  parts = ['VERSION ""\nNS_ :\n CM_\nBS_:\nBU_: XXX\n']
  parts.append('CM_ "RESEARCH ONLY: bus 1, Acura MDX 4G MMR, stock longitudinal. ' +
               'No validated distance/speed/validity decode; do not publish these values as RadarData.";\n')
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
 SG_ POSITION_Y_RAW : 64|16@1+ (1,0) [0|65535] "" XXX
 SG_ VELOCITY_RAW : 80|11@1+ (1,0) [0|2047] "" XXX
 SG_ BYTE_11_HIGH_RAW : 91|5@1+ (1,0) [0|31] "" XXX
""")
    comments = {
      'HEADER_0_RAW': 'Checksum-like changing header; algorithm and coverage UNKNOWN. Not integrity checked.',
      'SEQUENCE_8': 'Observed increment modulo 256 per slot frame. Independent of SEQUENCE_4; not one 16-bit counter.',
      'SEQUENCE_4': 'Observed increment modulo 16 per slot frame.',
      'OBJECT_ID_RAW': 'Observed values 0..63. Zero is an empty-slot candidate; complete validity semantics UNKNOWN.',
      'POSITION_X_RAW': 'Candidate x = raw*0.04 - 160 m. Scale/offset/width NOT validated across segments; retain raw bits.',
      'POSITION_Y_RAW': 'Candidate left-positive y = raw*0.01 - 245.76 m. Off-centre leads support sign in segments 0..4; width unresolved.',
      'VELOCITY_RAW': 'Candidate relative speed = raw*0.08 - 122.88 m/s. Fails kinematic validation; width/scale/offset unresolved.',
    }
    for signal, comment in comments.items():
      parts.append(f'CM_ SG_ {addr} {signal} "{comment}";\n')
  return {'acura_mdx_4g_objects_research.dbc': ''.join(parts)}
