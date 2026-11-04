#!/usr/bin/env python3


MESSAGE_COMMENT = " ".join((
  "Research-only bus-1 auxiliary traffic, approximately 33 Hz; seven even/odd message pairs.",
  "Even-message position and speed fields carry selected targets also found in the 500-53F radar object bank.",
  "Selections on 630/634/636 agree with 4E3 ACC/CMBB/FCW moving-path target IDs at 96-100 percent on well-supported",
  "samples; 632/638 carry stationary selections. Agreement is route-dependent; specific application assignment",
  "is not established for every message. Several applications can select the same target, explaining repeated geometry.",
  "Joint range (<0.5 m) and speed (<0.2 m/s) matching is 54-97 percent versus 0-14 percent for a six-second shift",
  "across ten Ioniq, Ioniq EV, Ioniq PHEV, and K7 segments. Match the nearest-range 500 object sample held up to 80 ms.",
  "Signed speed is 13 bits starting at bit 13, scale 0.01 m/s: among range/lateral matched targets above 10 m/s",
  "in magnitude, 13-bit speed fits 96-100 percent; 11-bit aliases most faster samples, 12-bit aliases PHEV targets",
  "near -25 to -29 m/s, and 14-bit fits zero percent. Captured K7 and PHEV frames decode -15.30 and -25.26 m/s.",
  "Distance 200 m is the observed empty marker. Lateral position is right-positive, opposite RadarData.yRel.",
  "Odd-message payloads are raw only; no object meaning is assigned to them. Source ECU/consumer attribution is",
  "unresolved: object-like payloads do not exclude a head-unit consumer. No additional independent radar track list",
  "is demonstrated, so keep the existing 500-53F source and do not register this range for RadarData publication.",
))


def generate():
  parts = ['VERSION ""\n\nNS_ :\n    CM_\n\nBS_:\n\nBU_: UNKNOWN ADAS_DRV\n']
  for address in range(0x630, 0x63E):
    name = f"SELECTED_OBJECT_{address:x}" if address % 2 == 0 else f"AUXILIARY_RAW_{address:x}"
    parts.append(f"\nBO_ {address} {name}: 8 UNKNOWN\n")
    if address % 2 == 0:
      parts.extend((
        ' SG_ UNKNOWN_BIT_0 : 0|1@1+ (1,0) [0|1] "" ADAS_DRV\n',
        ' SG_ DISTANCE_CANDIDATE : 1|12@1+ (0.05,0) [0|204.75] "m" ADAS_DRV\n',
        ' SG_ REL_SPEED_CANDIDATE : 13|13@1- (0.01,0) [-40.96|40.95] "m/s" ADAS_DRV\n',
        ' SG_ UNKNOWN_BITS_26_39 : 26|14@1+ (1,0) [0|16383] "" ADAS_DRV\n',
        ' SG_ LAT_POSITION_CANDIDATE : 40|10@1+ (0.05,-25.6) [-25.6|25.55] "m" ADAS_DRV\n',
        ' SG_ UNKNOWN_BITS_50_55 : 50|6@1+ (1,0) [0|63] "" ADAS_DRV\n',
      ))
    else:
      parts.append(' SG_ UNKNOWN_PAYLOAD : 0|56@1+ (1,0) [0|72057594037927935] "" ADAS_DRV\n')
    parts.append(' SG_ UNKNOWN_BYTE_7 : 56|8@1+ (1,0) [0|255] "" ADAS_DRV\n')
    parts.append(f'CM_ BO_ {address} "{MESSAGE_COMMENT}";\n')
  return {"hyundai_selected_objects_630_63d.dbc": "".join(parts)}
