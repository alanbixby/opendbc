#!/usr/bin/env python3


MESSAGE_COMMENT = " ".join((
  "Research-only non-HDA2 radar scan array on bus 1 at 20 Hz, DLC 64: 16 messages with four 13-byte records each.",
  "Record starts are bytes 3, 19, 35, and 51; intervening bytes 16-18, 32-34, and 48-50 are observed-zero gaps.",
  "The 64-byte HKG B8CD checksum mask validates all 296130 sampled frames on eight routes.",
  "Active records are range-sorted in every sampled adjacent pair; message/record position is not persistent identity.",
  "VALID is one for active records and zero for empty records in all checked samples (four original plus two extra segments).",
  "It agrees exactly with the longitudinal raw-32700 empty sentinel; empty bytes are 0000bc7f00000000b700000000.",
  "Lateral position is RIGHT-positive, opposite RadarData.yRel. Vision-free ego-yaw tests give slopes -1.07 to -1.16",
  "against a left-positive prediction on Tucson HEV 5868 segment 17, Tucson 6722 segment 7, and Sportage 7e9a segment 7.",
  "Left-positive sign agreement is zero; vision favors the flipped sign on 10 of 12 discriminating segments.",
  "The approximately negative-unit yaw slope independently supports the 0.01 m lateral scale.",
  "Doppler is negative for approaching returns. Non-stationary detections match same-car 210-21F positions within 1 m",
  "at 22-74 percent versus 0.3-10 percent with a seven-second time shift. Matched speed median errors are 0.01-0.08 m/s",
  "with 96.7-99.4 percent within 0.5 m/s. A stationary-only residual is not a decode-failure test: same-speed traffic",
  "produces the second Doppler/vEgo mode near zero, alongside stationary returns near minus one.",
  "Sorting concatenated segment timestamps corrects the 26da stationary diagnostic to 0.570 / 0.557 m/s.",
  "The refined signed 13-bit Doppler field starts at record bit 48 with 0.025 m/s scale. On a6d25e segment 4,",
  "median error versus 210 drops from 0.02 to 0.01 m/s and gated RMS from 0.033 to 0.027 m/s versus the former",
  "12-bit bit-49 0.05 m/s interpretation. Longitudinal versus radial velocity semantics remain provisional.",
  "No persistent object ID or association policy is resolved. Multiple returns may belong to one object;",
  "do not publish scan positions as RadarData tracks. Existing 210-21F tracks remain the published source.",
  "DLC 64 distinguishes this range from the overlapping DLC-8 ESR 500-53F family.",
))


def generate():
  parts = ['VERSION ""\n\nNS_ :\n    CM_\n\nBS_:\n\nBU_: RADAR ADAS_DRV\n']
  for address in range(0x510, 0x520):
    parts.append(f'\nBO_ {address} RADAR_DETECTIONS_{address:x}: 64 RADAR\n')
    parts.append(' SG_ CHECKSUM : 0|16@1+ (1,0) [0|65535] "" ADAS_DRV\n')
    parts.append(' SG_ COUNTER : 16|8@1+ (1,0) [0|255] "" ADAS_DRV\n')
    for record, start in enumerate((24, 152, 280, 408)):
      signals = (
        ("FLAGS_UNKNOWN", 0, 8, "+", 1, 0, 255, ""),
        ("PROPERTY_UNKNOWN", 8, 8, "+", 1, 0, 255, ""),
        ("LONG_POSITION_CANDIDATE", 16, 15, "+", 0.01, 0, 327.67, "m"),
        ("VALID", 31, 1, "+", 1, 0, 1, ""),
        ("LAT_POSITION_CANDIDATE", 32, 14, "-", 0.01, -81.92, 81.91, "m"),
        ("POSITION_FLAGS_UNKNOWN", 46, 2, "+", 1, 0, 3, ""),
        ("DOPPLER_CANDIDATE", 48, 13, "-", 0.025, -102.4, 102.375, "m/s"),
        ("TAIL_UNKNOWN", 61, 43, "+", 1, 0, 8796093022207, ""),
      )
      for name, offset, size, sign, scale, minimum, maximum, unit in signals:
        parts.append(f' SG_ DETECTION_{record}_{name} : {start + offset}|{size}@1{sign} ({scale},0) ' +
                     f'[{minimum}|{maximum}] "{unit}" ADAS_DRV\n')
      if record < 3:
        parts.append(f' SG_ DETECTION_{record}_ALIGNMENT_UNKNOWN : {start + 104}|24@1+ (1,0) [0|16777215] "" ADAS_DRV\n')
    parts.append(f'CM_ BO_ {address} "{MESSAGE_COMMENT}";\n')
    for record in range(4):
      parts.append(f'CM_ SG_ {address} DETECTION_{record}_DOPPLER_CANDIDATE "Approaching is negative; '
                   + '13-bit field and 0.025 m/s scale supported by moving-target cross-reference.";\n')
      parts.append(f'CM_ SG_ {address} DETECTION_{record}_LAT_POSITION_CANDIDATE "RIGHT-positive; '
                   + 'negate to obtain the RadarData lateral convention.";\n')
      parts.append(f'CM_ SG_ {address} DETECTION_{record}_VALID "One for active, zero for empty; '
                   + 'equivalent to longitudinal raw value differing from 32700 in checked samples.";\n')
  return {"hyundai_radar_detections_510_51f.dbc": "".join(parts)}
