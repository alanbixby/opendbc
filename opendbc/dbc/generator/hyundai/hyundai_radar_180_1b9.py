#!/usr/bin/env python3


def generate():
  """Two forward-camera objects per message; auxiliary 2BB-2BE data is not decoded."""
  parts = ['VERSION ""\nNS_ :\nBS_:\nBU_: FR_CMR ADAS_DRV\n']
  fields = (
    ("QUALITY", 24, 7, 1, 0), ("AGE", 32, 8, 1, 0), ("MOTION_STATE", 40, 4, 1, 0),
    ("OBJECT_ID", 44, 8, 1, 0), ("WIDTH", 52, 7, 0.05, 0), ("CLASSIFICATION", 60, 3, 1, 0),
    ("LONG_DIST", 64, 13, 0.05, 0), ("LAT_DIST", 78, 12, 0.05, -102.4), ("REL_SPEED", 91, 12, 0.05, -100),
  )
  for addr in (*range(0x180, 0x185), *range(0x1B6, 0x1BA)):
    parts.append(f"BO_ {addr} RADAR_TRACK_{addr:x}: 32 FR_CMR\n")
    parts.append(' SG_ CHECKSUM : 0|16@1+ (1,0) [0|65535] "" ADAS_DRV\n')
    parts.append(' SG_ COUNTER : 16|8@1+ (1,0) [0|255] "" ADAS_DRV\n')
    for slot in (1, 2):
      for name, start, size, scale, offset in fields:
        parts.append(f' SG_ {slot}_{name} : {start + (slot - 1) * 128}|{size}@1+ ({scale},{offset}) ' +
                     f'[{offset}|{(2**size - 1) * scale + offset}] "" ADAS_DRV\n')
    parts.append(f'CM_ BO_ {addr} "Forward-camera object core related to FR_CMR 235-248; two 128-bit slots with 8-bit IDs. ' +
                 'High confidence position/speed/ID from route kinematics and vision. Downloaded Hyundai FR_CMR definitions identify the forward camera. ' +
                 'This is not an independent raw radar list. 2BB-2BE auxiliary fields remain undecoded.";\n')
    parts.append(f'CM_ SG_ {addr} CHECKSUM "Standard HKG CAN-FD CRC16, verified on every captured frame on the object bus.";\n')
    parts.append(f'CM_ SG_ {addr} COUNTER "Shared 8-bit cycle counter; objects repeat at approximately 33 Hz.";\n')
    parts.append(f'CM_ SG_ {addr} 1_OBJECT_ID "8-bit persistent ID, observed 1-255; bit 51 is part of ID, not padding.";\n')
    parts.append(f'CM_ SG_ {addr} 2_OBJECT_ID "8-bit persistent ID, observed 1-255; bit 179 is part of ID, not padding.";\n')
    for slot in (1, 2):
      for name in ("LONG_DIST", "LAT_DIST", "REL_SPEED", "OBJECT_ID"):
        parts.append(f'CM_ SG_ {addr} {slot}_{name} "High confidence: shared camera-object encoding; ' +
                     'ID zero denotes an empty slot. Lateral is left positive; speed is relative to ego.";\n')
  return {"hyundai_radar_180_1b9.dbc": "".join(parts)}
