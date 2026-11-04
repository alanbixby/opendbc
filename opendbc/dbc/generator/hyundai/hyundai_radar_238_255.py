#!/usr/bin/env python3


def generate():
  parts = ['VERSION ""\nNS_ :\n CM_\nBS_:\nBU_: CAMERA\n']
  for addr in range(0x238, 0x256):
    geometry = (addr - 0x238) % 3 == 0
    parts.append(f"\nBO_ {addr} RADAR_TRACK_{addr:x}: 8 CAMERA\n")
    if geometry:
      parts.append(''' SG_ LONG_DIST_B : 15|13@0+ (0.05,0) [0|409.55] "m" XXX
 SG_ LAT_DIST_B : 45|10@0- (0.05,0) [-25.6|25.55] "m" XXX
 SG_ REL_SPEED_B : 18|11@0+ (0.1,-100) [-100|104.7] "m/s" XXX
 SG_ OBJECT_ID_B : 7|6@0+ (1,0) [0|63] "" XXX
 SG_ COUNTER_B : 1|2@0+ (1,0) [0|3] "" XXX
 SG_ LONG_DIST : 7|13@0+ (0.05,0) [0|409.55] "m" XXX
 SG_ LAT_DIST : 23|12@0+ (-0.05,102.4) [-102.35|102.4] "m" XXX
 SG_ OBJECT_SPEED : 39|10@0+ (0.2,-100) [-100|104.6] "m/s" XXX
 SG_ COUNTER_A : 43|2@0+ (1,0) [0|3] "" XXX
 SG_ OBJECT_ID : 63|7@0+ (1,0) [0|127] "" XXX
''')
      for signal, comment in (
        ("LONG_DIST_B", "High confidence 24-message dialect distance; shared triplet structure, different packing from 30-message dialect."),
        ("REL_SPEED_B", "High confidence relative speed: 0.1 m/s, offset -100, fitted to persistent-object distance derivatives on Niro EV and Niro PHEV."),
        ("LAT_DIST_B", "Medium confidence 24-message dialect lateral position, left positive; validate against route metrics."),
        ("OBJECT_ID_B", "Medium confidence 24-message dialect six-bit identity, zero on unused slots."),
        ("COUNTER_B", "High confidence 24-message dialect counter in low two bits of byte zero."),
        ("LONG_DIST", "High confidence geometry: leading 13 bits follow the vision lead. Range beyond nearby objects is less accurate than radar."),
        ("LAT_DIST", "High confidence sign/scale from vision: left positive. Upper boundary unexercised."),
        ("OBJECT_SPEED", "LOW confidence absolute-speed candidate; subtract ego speed. Kinematic residuals remain; see report."),
        ("COUNTER_A", "High confidence: increments modulo four every 30 ms, including empty slots."),
        ("OBJECT_ID", "Medium confidence persistent identity; zero accompanies empty geometry. Upper boundary unexercised."),
      ):
        parts.append(f'CM_ SG_ {addr} {signal} "{comment}";\n')
    else:
      parts.append(' SG_ COUNTER_A : 7|2@0+ (1,0) [0|3] "" XXX\n')
      parts.append(
        f'CM_ BO_ {addr} "Camera-object companion in a three-message slot; not an independent object.";\n'
      )
  return {"hyundai_radar_238_255.dbc": "".join(parts)}
