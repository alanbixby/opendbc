import math
from collections import deque
from dataclasses import dataclass, field

from opendbc.can import CANParser
from opendbc.car import structs
from opendbc.car.interfaces import RadarInterfaceBase

from opendbc.sunnypilot.car.hyundai.radar_interface_ext import RadarInterfaceExt
from opendbc.sunnypilot.car.hyundai.values import HyundaiFlagsSP, RadarType

RADAR_TRACK_BUSES = (0, 1, 2)
RADAR_CADENCE_TOLERANCE = 0.25
RADAR_FRESH_CYCLE_PERIODS = 3
CAMERA_238_CONFIRM_CYCLES = 3
CAMERA_238_DIALECT_CYCLES = 3
CAMERA_238_MAX_RANGE = 120.0
CAMERA_238_SPEED_ERROR = 6.0
CAMERA_238_WHEEL_FRESH_NANOS = 500_000_000


# POC for parsing corner radars: https://github.com/commaai/openpilot/pull/24221/


@dataclass(frozen=True)
class HyundaiRadarTrackSpec:
  name: str
  start_addr: int
  msg_count: int
  track_prefixes: tuple[str, ...]
  signals: tuple[str, ...]
  frequency: int
  message_size: int
  source_kind: str = "radar"
  required_msg_count: int | None = None
  addresses: tuple[int, ...] = ()

  @property
  def end_addr(self) -> int:
    return self.addresses[-1] if self.addresses else self.start_addr + self.msg_count - 1

  @property
  def address_range(self) -> range | tuple[int, ...]:
    return self.addresses or range(self.start_addr, self.end_addr + 1)

  @property
  def required_end_addr(self) -> int:
    return self.end_addr if self.required_msg_count is None else self.start_addr + self.required_msg_count - 1

  @property
  def required_address_range(self) -> range | tuple[int, ...]:
    return self.address_range if self.required_msg_count is None else range(self.start_addr, self.required_end_addr + 1)

  @property
  def dbc_name(self) -> str:
    return f"hyundai_{self.name.lower()}_generated"


@dataclass(frozen=True)
class HyundaiRadarTrackConfig:
  spec: HyundaiRadarTrackSpec
  bus: int
  end_addr: int

  @property
  def address_range(self) -> range | tuple[int, ...]:
    return self.spec.addresses or range(self.spec.start_addr, self.end_addr + 1)


HyundaiRadarTrackKey = tuple[str, int]


@dataclass
class HyundaiRadarParserConfig:
  spec: HyundaiRadarTrackSpec
  bus: int
  end_addr: int
  parser: CANParser
  cycle_timestamps: deque[int] = field(default_factory=lambda: deque(maxlen=100))
  camera_dialect: str | None = None
  camera_dialect_cycles: int = 0
  camera_cycle_addrs: set[int] = field(default_factory=set)

  def __post_init__(self):
    if self.spec.name == "RADAR_238_255" and self.end_addr == self.spec.end_addr:
      self.camera_dialect = "A"

  @property
  def address_range(self) -> range | tuple[int, ...]:
    return self.spec.addresses or range(self.spec.start_addr, self.end_addr + 1)

  @property
  def msg_count(self) -> int:
    return len(self.address_range)


@dataclass
class Camera238Confirmation:
  object_id: int
  timestamp: int
  distance: float
  lateral: float
  velocity: float
  consecutive: int = 1
  history: deque[tuple[int, float, float]] = field(default_factory=deque)

  def observe(self, object_id: int, timestamp: int, distance: float, lateral: float, velocity: float) -> bool:
    if timestamp == self.timestamp:
      return self.object_id == object_id and self.consecutive >= CAMERA_238_CONFIRM_CYCLES
    dt = (timestamp - self.timestamp) / 1e9
    consistent = (self.object_id == object_id and 0.015 <= dt <= 0.045 and
                  abs((distance - self.distance) / dt - (velocity + self.velocity) / 2) <= CAMERA_238_SPEED_ERROR and
                  abs(lateral - self.lateral) <= 0.5 + 8 * dt)
    if not consistent:
      self.consecutive = 0
      self.history.clear()
    self.consecutive += 1
    self.object_id, self.timestamp = object_id, timestamp
    self.distance, self.lateral, self.velocity = distance, lateral, velocity
    while self.history and timestamp - self.history[0][0] > 450_000_000:
      self.history.popleft()
    self.history.append((timestamp, distance, velocity))
    # A longer window catches smooth range drift that passes adjacent-frame checks.
    if timestamp - self.history[0][0] >= 180_000_000:
      derivative = (distance - self.history[0][1]) / ((timestamp - self.history[0][0]) / 1e9)
      mean_speed = sum(sample[2] for sample in self.history) / len(self.history)
      if abs(derivative - mean_speed) > CAMERA_238_SPEED_ERROR / 2:
        self.consecutive = 1
        self.history.clear()
        self.history.append((timestamp, distance, velocity))
    return self.consecutive >= CAMERA_238_CONFIRM_CYCLES


RADAR_500_53F = HyundaiRadarTrackSpec(
  "RADAR_500_53F", 0x500, 64, ("",),
  ("STATE", "ONCOMING_ESR", "AZIMUTH", "LONG_DIST", "REL_SPEED", "REL_LAT_SPEED_ESR", "REL_ACCEL", "REL_ACCEL_ESR"),
  frequency=20, message_size=8, required_msg_count=32,
)
# Compatibility alias for code importing the former truncated family name.
RADAR_500_51F = RADAR_500_53F
RADAR_210_21F = HyundaiRadarTrackSpec(
  "RADAR_210_21F", 0x210, 16, ("1_", "2_"),
  ("1_STATE", "1_STATE_ALT", "1_MOTION_STATE", "1_AGE", "1_LONG_DIST", "1_LAT_DIST", "1_REL_SPEED", "1_REL_ACCEL",
   "2_STATE", "2_STATE_ALT", "2_MOTION_STATE", "2_AGE", "2_LONG_DIST", "2_LAT_DIST", "2_REL_SPEED", "2_REL_ACCEL"),
  frequency=20, message_size=32,
)
RADAR_235_248 = HyundaiRadarTrackSpec(
  "RADAR_235_248", 0x235, 20, ("",),
  ("QUALITY", "AGE", "MOTION_STATE", "OBJECT_ID", "LONG_DIST", "LAT_DIST", "REL_SPEED", "REL_LAT_SPEED", "REL_ACCEL"),
  frequency=33, message_size=32, source_kind="camera",
)
RADAR_3A5_3C4 = HyundaiRadarTrackSpec(
  "RADAR_3A5_3C4", 0x3A5, 32, ("",), ("STATE", "MOTION_STATE", "AGE", "LONG_DIST", "LAT_DIST", "REL_SPEED", "REL_ACCEL"),
  frequency=20, message_size=24,
)
RADAR_602_617 = HyundaiRadarTrackSpec(
  "RADAR_602_617", 0x602, 16, ("1_", "2_"), ("1_DISTANCE", "1_LATERAL", "1_SPEED", "2_DISTANCE", "2_LATERAL", "2_SPEED"),
  frequency=10, message_size=8,
)

RADAR_238_255 = HyundaiRadarTrackSpec(
  "RADAR_238_255", 0x238, 30, ("",), ("LONG_DIST", "LAT_DIST", "OBJECT_SPEED", "OBJECT_ID"),
  frequency=33, message_size=8, source_kind="camera", required_msg_count=24,
)

RADAR_180_1B9 = HyundaiRadarTrackSpec(
  "RADAR_180_1B9", 0x180, 9, ("1_", "2_"),
  tuple(f"{prefix}{signal}" for prefix in ("1_", "2_")
        for signal in ("OBJECT_ID", "LONG_DIST", "LAT_DIST", "REL_SPEED", "AGE", "MOTION_STATE")),
  frequency=33, message_size=32, source_kind="camera",
  addresses=(*range(0x180, 0x185), *range(0x1B6, 0x1BA)),
)

HYUNDAI_RADAR_TRACK_SPECS = (RADAR_238_255, RADAR_180_1B9, RADAR_500_53F, RADAR_210_21F, RADAR_235_248, RADAR_3A5_3C4, RADAR_602_617)
DEFAULT_RADAR_TRIGGER_MSG = max(rt.end_addr for rt in HYUNDAI_RADAR_TRACK_SPECS)
RADAR_TRACK_SPEC_BY_ADDR = {addr: spec for spec in HYUNDAI_RADAR_TRACK_SPECS for addr in spec.address_range}
RADAR_TRACK_SPEC_BY_ADDR_SIZE = {(addr, spec.message_size): spec for spec in HYUNDAI_RADAR_TRACK_SPECS for addr in spec.address_range}

DETECTED_RADAR_TRACKS: dict[str, tuple[HyundaiRadarTrackConfig, ...]] = {}


def detect_radar_tracks(fingerprint: dict[int, dict[int, int]]) -> tuple[HyundaiRadarTrackConfig, ...]:
  detected: list[HyundaiRadarTrackConfig] = []
  for radar_spec in HYUNDAI_RADAR_TRACK_SPECS:
    for bus in RADAR_TRACK_BUSES:
      bus_fingerprint = fingerprint.get(bus, {})
      if isinstance(bus_fingerprint, dict):
        required_range_matches = all(bus_fingerprint.get(addr) == radar_spec.message_size for addr in radar_spec.required_address_range)
        full_range_matches = all(bus_fingerprint.get(addr) == radar_spec.message_size for addr in radar_spec.address_range)
      else:
        required_range_matches = all(addr in bus_fingerprint for addr in radar_spec.required_address_range)
        full_range_matches = all(addr in bus_fingerprint for addr in radar_spec.address_range)
      if required_range_matches:
        end_addr = radar_spec.end_addr if full_range_matches else radar_spec.required_end_addr
        detected.append(HyundaiRadarTrackConfig(radar_spec, bus, end_addr))
  return tuple(detected)


def set_detected_radar_tracks(car_fingerprint: str, radar_tracks: tuple[HyundaiRadarTrackConfig, ...]) -> None:
  DETECTED_RADAR_TRACKS[car_fingerprint] = radar_tracks


def get_detected_radar_tracks(CP) -> tuple[HyundaiRadarTrackConfig, ...]:
  return DETECTED_RADAR_TRACKS.get(CP.carFingerprint, ())


def get_radar_can_parser(radar_track: HyundaiRadarTrackConfig) -> CANParser:
  messages = [(f"RADAR_TRACK_{addr:x}", radar_track.spec.frequency) for addr in radar_track.address_range]
  signals = set(radar_track.spec.signals)
  if radar_track.spec is RADAR_238_255:
    messages = [(f"RADAR_TRACK_{addr:x}", radar_track.spec.frequency)
                for addr in range(0x238, radar_track.end_addr + 1, 3)]
    signals = ({"LONG_DIST", "LAT_DIST", "OBJECT_SPEED", "OBJECT_ID"} if radar_track.end_addr == 0x255 else
               {"LONG_DIST_B", "LAT_DIST_B", "REL_SPEED_B", "OBJECT_ID_B"})
  return CANParser(radar_track.spec.dbc_name, messages, radar_track.bus, signals=signals)


def get_camera_track_msg(radar_parser: HyundaiRadarParserConfig, addr: int):
  # Only geometry addresses may access the dialect-specific fields.
  if (addr - 0x238) % 3:
    return {}
  msg = radar_parser.parser.vl[f"RADAR_TRACK_{addr:x}"]
  if radar_parser.end_addr == RADAR_238_255.required_end_addr:
    return {"LONG_DIST": msg["LONG_DIST_B"], "LAT_DIST": msg["LAT_DIST_B"], "OBJECT_ID": msg["OBJECT_ID_B"],
            "OBJECT_SPEED": msg["REL_SPEED_B"], "DIALECT": "B"}
  return {**msg, "DIALECT": "A"}


def get_track_storage_key(radar_spec: HyundaiRadarTrackSpec, addr: int, track_prefix: str) -> HyundaiRadarTrackKey:
  if radar_spec.name in ("RADAR_500_53F", "RADAR_235_248", "RADAR_3A5_3C4", "RADAR_238_255"):
    return (radar_spec.name, addr)

  track_index = int(track_prefix[0]) - 1
  return (radar_spec.name, addr * 2 + track_index)


def get_track_ts_nanos(parser: CANParser, msg_name: str, radar_spec: HyundaiRadarTrackSpec, track_prefix: str) -> int:
  if radar_spec.name == "RADAR_238_255":
    return max(parser.ts_nanos[msg_name].get("LONG_DIST", 0), parser.ts_nanos[msg_name].get("LONG_DIST_B", 0))
  if radar_spec.name == "RADAR_602_617":
    return parser.ts_nanos[msg_name][f"{track_prefix}DISTANCE"]
  if radar_spec.name in ("RADAR_180_1B9", "RADAR_210_21F", "RADAR_235_248"):
    return parser.ts_nanos[msg_name][f"{track_prefix}LONG_DIST"]
  return parser.ts_nanos[msg_name]["LONG_DIST"]


def decode_radar_track(radar_spec: HyundaiRadarTrackSpec, track_msg, track_prefix: str) -> tuple[float, float, float]:
  if radar_spec.name == "RADAR_238_255":
    return track_msg["LONG_DIST"], track_msg["LAT_DIST"], track_msg["OBJECT_SPEED"]
  if radar_spec.name == "RADAR_602_617":
    return (
      track_msg[f"{track_prefix}DISTANCE"],
      track_msg[f"{track_prefix}LATERAL"],
      track_msg[f"{track_prefix}SPEED"],
    )

  if radar_spec.name in ("RADAR_180_1B9", "RADAR_210_21F"):
    return (
      track_msg[f"{track_prefix}LONG_DIST"],
      track_msg[f"{track_prefix}LAT_DIST"],
      track_msg[f"{track_prefix}REL_SPEED"],
    )

  if radar_spec.name == "RADAR_500_53F":
    azimuth = math.radians(track_msg["AZIMUTH"])
    long_dist = track_msg["LONG_DIST"]
    return (
      math.cos(azimuth) * long_dist,
      -math.sin(azimuth) * long_dist,
      track_msg["REL_SPEED"],
    )

  if radar_spec.name == "RADAR_235_248":
    return (
      track_msg["LONG_DIST"],
      track_msg["LAT_DIST"],
      track_msg["REL_SPEED"],
    )

  return (
    track_msg["LONG_DIST"],
    track_msg["LAT_DIST"],
    track_msg["REL_SPEED"],
  )


def get_radar_track_state(radar_spec: HyundaiRadarTrackSpec, track_msg, track_prefix: str) -> int:
  state = int(track_msg[f"{track_prefix}STATE"])
  if radar_spec.name == "RADAR_210_21F" and state == 0:
    # Compact-dialect platforms leave detailed STATE zero and use the shared
    # compressed lifecycle field instead.
    return {0: 0, 1: 1, 2: 3, 3: 4}[int(track_msg[f"{track_prefix}STATE_ALT"])]
  return state


def get_radar_track_motion_state(radar_spec: HyundaiRadarTrackSpec, track_msg, track_prefix: str) -> int:
  motion_state = int(track_msg[f"{track_prefix}MOTION_STATE"])
  if radar_spec.source_kind == "camera":
    # Normalize the camera-object enum to RadarPoint's common
    # 0=unknown, 1=stationary, 2=moving representation.
    if motion_state in (1, 2, 3, 6):
      return 1
    if motion_state in (5, 8, 9):
      return 2
    return 0
  return motion_state


def is_radar_track_valid(radar_spec: HyundaiRadarTrackSpec, track_msg, track_prefix: str) -> bool:
  if radar_spec.name == "RADAR_602_617":
    return 0 < track_msg[f"{track_prefix}DISTANCE"] < 255.75

  if radar_spec.name == "RADAR_238_255":
    # Candidate validity only. Publication additionally requires dialect/ego
    # eligibility and consecutive kinematic confirmation in RadarInterface.
    # B uses ID zero for real objects; its empty slots have zero distance.
    if track_msg.get("DIALECT") == "B":
      return 0 < track_msg["LONG_DIST"] <= CAMERA_238_MAX_RANGE and -25.6 < track_msg["LAT_DIST"] < 25.5
    return 0 < track_msg.get("LONG_DIST", 0) <= CAMERA_238_MAX_RANGE and track_msg.get("OBJECT_ID", 0) != 0

  if radar_spec.source_kind == "camera":
    return int(track_msg[f"{track_prefix}OBJECT_ID"]) != 0

  return get_radar_track_state(radar_spec, track_msg, track_prefix) in (3, 4)


class RadarInterface(RadarInterfaceBase, RadarInterfaceExt):
  def __init__(self, CP, CP_SP):
    RadarInterfaceBase.__init__(self, CP, CP_SP)
    RadarInterfaceExt.__init__(self, CP, CP_SP)
    self.pts: dict[int | HyundaiRadarTrackKey, structs.RadarData.RadarPoint] = {}
    detected_tracks = get_detected_radar_tracks(CP)
    self.radar_tracks_available = bool(detected_tracks)
    self.radar_tracks = detected_tracks
    self.radar_parsers = tuple(HyundaiRadarParserConfig(rt.spec, rt.bus, rt.end_addr, get_radar_can_parser(rt))
                               for rt in self.radar_tracks)
    self.seen_radar_addrs = {(rt.spec.name, rt.bus): set(rt.address_range) for rt in detected_tracks}
    self.updated_messages: set[tuple[int, int]] = set()
    self.pending_radar_can: dict[tuple[str, int], list] = {}
    self.active_radar_buses: dict[str, int] = {}
    self.camera_object_ids: dict[HyundaiRadarTrackKey, int] = {}
    self.can_time_nanos = 0
    self.trigger_msg = DEFAULT_RADAR_TRIGGER_MSG

    self.radar_off_can = True
    self.rcp: CANParser | None = None
    self._radar_mode: int | None = None
    # Legacy A camera speed is absolute. Require independent wheel speed
    # before converting it to relative speed.
    self.camera_ego_parser: CANParser | None = None
    if any(rt.spec is RADAR_238_255 and rt.end_addr == 0x255 for rt in detected_tracks):
      self.camera_ego_parser = CANParser("hyundai_can_generated", [("WHL_SPD11", 0)], 0)
    self.camera_ego_speed: float | None = None
    self.camera_238_confirmations: dict[tuple[int, int, int], Camera238Confirmation] = {}

    if CP_SP.flags & HyundaiFlagsSP.RADAR_FULL_RADAR:
      radar_mode = RadarType.FULL_RADAR
    elif CP_SP.flags & HyundaiFlagsSP.RADAR_LEAD_ONLY:
      radar_mode = RadarType.LEAD_ONLY
    else:
      radar_mode = RadarType.OFF
    self.set_radar_mode(radar_mode)

  def _discover_radar_parsers(self, can_strings) -> None:
    existing_parsers = {(parser.spec.name, parser.bus): parser for parser in self.radar_parsers}
    updated_candidates: dict[tuple[str, int], HyundaiRadarTrackSpec] = {}
    for _, can_messages in can_strings:
      for raw_addr, dat, raw_bus in can_messages:
        addr, bus = int(raw_addr), int(raw_bus)
        spec = RADAR_TRACK_SPEC_BY_ADDR_SIZE.get((addr, len(dat)))
        if spec is None or bus not in RADAR_TRACK_BUSES or len(dat) != spec.message_size:
          continue

        parser_key = (spec.name, bus)
        self.seen_radar_addrs.setdefault(parser_key, set()).add(addr)
        if parser_key not in existing_parsers:
          updated_candidates[parser_key] = spec

    upgraded_tracks = {}
    for parser_key, parser in existing_parsers.items():
      if parser.spec is RADAR_238_255 and parser.end_addr == RADAR_238_255.required_end_addr and any(
        addr > parser.spec.required_end_addr for addr in self.seen_radar_addrs[parser_key]
      ):
        # Even a partial extension disproves B. Wait for all A messages before publishing.
        parser.camera_dialect = None
        self.pts = {key: pt for key, pt in self.pts.items() if key[0] != RADAR_238_255.name}
        self.camera_238_confirmations.clear()
      if parser.end_addr == parser.spec.end_addr:
        continue
      seen_addrs = self.seen_radar_addrs[parser_key]
      if all(addr in seen_addrs for addr in parser.spec.address_range):
        upgraded_tracks[parser_key] = HyundaiRadarTrackConfig(parser.spec, parser.bus, parser.spec.end_addr)

    if upgraded_tracks:
      self.radar_tracks = tuple(
        upgraded_tracks.get((track.spec.name, track.bus), track)
        for track in self.radar_tracks
      )
      self.radar_parsers = tuple(
        HyundaiRadarParserConfig(track.spec, track.bus, track.end_addr, get_radar_can_parser(track))
        if (track.spec.name, track.bus) in upgraded_tracks else parser
        for track, parser in zip(self.radar_tracks, self.radar_parsers, strict=True)
      )
      for parser_key in upgraded_tracks:
        self.pending_radar_can.pop(parser_key, None)
        if parser_key[0] == RADAR_238_255.name:
          if self.camera_ego_parser is None:
            self.camera_ego_parser = CANParser("hyundai_can_generated", [("WHL_SPD11", 0)], 0)
          self.pts = {key: pt for key, pt in self.pts.items() if key[0] != RADAR_238_255.name}
          self.camera_238_confirmations.clear()

    discovered_tracks = []
    for (spec_name, bus), spec in updated_candidates.items():
      seen_addrs = self.seen_radar_addrs[(spec_name, bus)]
      if not all(addr in seen_addrs for addr in spec.required_address_range):
        continue
      end_addr = spec.end_addr if all(addr in seen_addrs for addr in spec.address_range) else spec.required_end_addr
      discovered_tracks.append(HyundaiRadarTrackConfig(spec, bus, end_addr))

    if not discovered_tracks:
      return

    self.radar_tracks = (*self.radar_tracks, *discovered_tracks)
    self.radar_parsers = (*self.radar_parsers, *(
      HyundaiRadarParserConfig(track.spec, track.bus, track.end_addr, get_radar_can_parser(track)) for track in discovered_tracks
    ))
    if self.camera_ego_parser is None and any(track.spec is RADAR_238_255 and track.end_addr == 0x255 for track in discovered_tracks):
      self.camera_ego_parser = CANParser("hyundai_can_generated", [("WHL_SPD11", 0)], 0)
    if self.rcp is None:
      self.rcp = self.radar_parsers[0].parser

  @property
  def radar_mode(self) -> int | None:
    return self._radar_mode

  def set_radar_mode(self, radar_mode: int) -> bool:
    if radar_mode not in (RadarType.OFF, RadarType.LEAD_ONLY, RadarType.FULL_RADAR):
      raise ValueError(f"invalid Hyundai radar mode: {radar_mode}")
    if radar_mode == self._radar_mode:
      return False

    radar_mode_flags = HyundaiFlagsSP.RADAR_LEAD_ONLY | HyundaiFlagsSP.RADAR_FULL_RADAR
    self.CP_SP.flags &= ~radar_mode_flags.value
    if radar_mode == RadarType.LEAD_ONLY:
      self.CP_SP.flags |= HyundaiFlagsSP.RADAR_LEAD_ONLY.value
    elif radar_mode == RadarType.FULL_RADAR:
      self.CP_SP.flags |= HyundaiFlagsSP.RADAR_FULL_RADAR.value

    self.pts.clear()
    self.updated_messages.clear()
    self.pending_radar_can.clear()
    self.active_radar_buses.clear()
    self.camera_238_confirmations.clear()
    self.camera_object_ids.clear()
    self.can_time_nanos = 0
    for radar_parser in self.radar_parsers:
      radar_parser.cycle_timestamps.clear()

    if radar_mode == RadarType.FULL_RADAR:
      self.trigger_msg = max((track.end_addr for track in self.radar_tracks), default=DEFAULT_RADAR_TRIGGER_MSG)
      self.rcp = self.radar_parsers[0].parser if self.radar_parsers else None
      self.radar_off_can = False
    elif radar_mode == RadarType.LEAD_ONLY and self.use_radar_interface_ext:
      self.initialize_radar_ext(DEFAULT_RADAR_TRIGGER_MSG)
      self.radar_off_can = self.rcp is None
    else:
      self.trigger_msg = self.get_trigger_msg(DEFAULT_RADAR_TRIGGER_MSG)
      self.rcp = None
      self.radar_off_can = True

    self._radar_mode = radar_mode
    return True

  def update(self, can_strings):
    if self.radar_off_can:
      ret = super().update(None)
      if ret is not None:
        ret.radarTracksAvailable = self.radar_tracks_available
      return ret

    if self.CP_SP.flags & HyundaiFlagsSP.RADAR_LEAD_ONLY and self.use_radar_interface_ext:
      vls = self.rcp.update(can_strings)
      self.updated_messages.update((0, addr) for addr in vls)

      if (0, self.trigger_msg) not in self.updated_messages:
        return None

      rr = self._update(self.updated_messages)
      self.updated_messages.clear()
      return rr

    self.can_time_nanos = max(self.can_time_nanos, max((t for t, _ in can_strings), default=0))
    self._discover_radar_parsers(can_strings)
    if self.camera_ego_parser is not None:
      if 0x386 in self.camera_ego_parser.update(can_strings):
        wheels = self.camera_ego_parser.vl["WHL_SPD11"]
        self.camera_ego_speed = sum(wheels[f"WHL_SPD_{wheel}"] for wheel in ("FL", "FR", "RL", "RR")) / 14.4
      wheel_timestamp = self.camera_ego_parser.ts_nanos["WHL_SPD11"]["WHL_SPD_FL"]
      if self.can_time_nanos - wheel_timestamp > CAMERA_238_WHEEL_FRESH_NANOS:
        self.camera_ego_speed = None
    radar_cycle_complete = False
    for radar_parser in self.radar_parsers:
      parser_key = (radar_parser.spec.name, radar_parser.bus)
      filtered_can = []
      parser_cycle_started = False
      parser_cycle_complete = False
      cycle_end_timestamps = []
      for mono_time, can_messages in can_strings:
        relevant_messages = [
          msg for msg in can_messages
          if msg[2] == radar_parser.bus and msg[0] in radar_parser.address_range and
             len(msg[1]) == radar_parser.spec.message_size
        ]
        if relevant_messages:
          if radar_parser.spec is RADAR_238_255 and radar_parser.camera_dialect is None:
            for addr, _, _ in relevant_messages:
              if addr == radar_parser.spec.start_addr:
                complete = all(a in radar_parser.camera_cycle_addrs for a in radar_parser.spec.required_address_range)
                radar_parser.camera_dialect_cycles = radar_parser.camera_dialect_cycles + 1 if complete else 0
                radar_parser.camera_cycle_addrs.clear()
                extension_seen = any(a > radar_parser.spec.required_end_addr
                                     for a in self.seen_radar_addrs[parser_key])
                if radar_parser.camera_dialect_cycles >= CAMERA_238_DIALECT_CYCLES and not extension_seen:
                  radar_parser.camera_dialect = "B"
              radar_parser.camera_cycle_addrs.add(addr)
          filtered_can.append((mono_time, relevant_messages))
          parser_cycle_started |= any(msg[0] == radar_parser.spec.start_addr for msg in relevant_messages)
          parser_cycle_complete |= any(msg[0] == radar_parser.end_addr for msg in relevant_messages)
          cycle_end_timestamps.extend(mono_time for msg in relevant_messages if msg[0] == radar_parser.end_addr)

      if filtered_can:
        if parser_cycle_started:
          self.pending_radar_can.pop(parser_key, None)
        pending_can = self.pending_radar_can.setdefault(parser_key, [])
        pending_can.extend(filtered_can)
        del pending_can[:max(0, len(pending_can) - radar_parser.msg_count * 2)]
      if not parser_cycle_complete:
        continue

      vls = radar_parser.parser.update(self.pending_radar_can.pop(parser_key, []))
      relevant_addrs = {
        addr for addr in vls
        if addr in radar_parser.address_range
      }
      if relevant_addrs:
        self.seen_radar_addrs.setdefault((radar_parser.spec.name, radar_parser.bus), set()).update(relevant_addrs)
        self.updated_messages.update((radar_parser.bus, addr) for addr in relevant_addrs)
      for timestamp in cycle_end_timestamps:
        if not radar_parser.cycle_timestamps or timestamp != radar_parser.cycle_timestamps[-1]:
          radar_parser.cycle_timestamps.append(timestamp)
      radar_cycle_complete = True

    if not radar_cycle_complete:
      return None

    rr = self._update(self.updated_messages)
    self.updated_messages.clear()
    return rr

  def _radar_range_complete(self, radar_parser: HyundaiRadarParserConfig) -> bool:
    seen_addrs = self.seen_radar_addrs.get((radar_parser.spec.name, radar_parser.bus), set())
    return all(addr in seen_addrs for addr in radar_parser.address_range)

  @staticmethod
  def _radar_parser_valid_count(radar_parser: HyundaiRadarParserConfig, updated_messages: set[tuple[int, int]]) -> int:
    if radar_parser.spec is RADAR_238_255:
      return sum(is_radar_track_valid(RADAR_238_255, get_camera_track_msg(radar_parser, addr), "")
                 for addr in range(0x238, radar_parser.end_addr + 1, 3))
    valid_count = 0
    for addr in radar_parser.address_range:
      if updated_messages and (radar_parser.bus, addr) not in updated_messages:
        continue
      msg_name = f"RADAR_TRACK_{addr:x}"
      msg = radar_parser.parser.vl[msg_name]
      for track_prefix in radar_parser.spec.track_prefixes:
        if get_track_ts_nanos(radar_parser.parser, msg_name, radar_parser.spec, track_prefix) == 0:
          continue
        if is_radar_track_valid(radar_parser.spec, msg, track_prefix):
          valid_count += 1
    return valid_count

  @staticmethod
  def _radar_parser_cadence_score(radar_parser: HyundaiRadarParserConfig) -> int:
    timestamps = radar_parser.cycle_timestamps
    if len(timestamps) < 3:
      return 1

    elapsed = timestamps[-1] - timestamps[0]
    if elapsed <= 0:
      return 0

    observed_frequency = (len(timestamps) - 1) * 1e9 / elapsed
    relative_error = abs(observed_frequency - radar_parser.spec.frequency) / radar_parser.spec.frequency
    return 2 if relative_error <= RADAR_CADENCE_TOLERANCE else 0

  def _parser_fresh(self, radar_parser: HyundaiRadarParserConfig) -> bool:
    # Direct _update callers have no CAN clock. Runtime freshness always uses incoming CAN time.
    if not self.can_time_nanos:
      return True
    return bool(radar_parser.cycle_timestamps and
                self.can_time_nanos - radar_parser.cycle_timestamps[-1] <=
                RADAR_FRESH_CYCLE_PERIODS * 1e9 / radar_parser.spec.frequency)

  def _select_active_radar_parser(self, radar_parsers: list[HyundaiRadarParserConfig]) -> HyundaiRadarParserConfig:
    valid_counts = {rp.bus: self._radar_parser_valid_count(rp, set()) for rp in radar_parsers}
    current_bus = self.active_radar_buses.get(radar_parsers[0].spec.name)

    def parser_score(radar_parser: HyundaiRadarParserConfig) -> tuple[int, int, bool, int]:
      return (
        int(self._parser_fresh(radar_parser)),
        self._radar_parser_cadence_score(radar_parser),
        radar_parser.bus == current_bus,
        valid_counts[radar_parser.bus],
      )

    best_parser = max(radar_parsers, key=parser_score)

    self.active_radar_buses[best_parser.spec.name] = best_parser.bus
    return best_parser

  def _camera_238_eligible(self, radar_parser: HyundaiRadarParserConfig) -> bool:
    return radar_parser.camera_dialect is not None and (radar_parser.camera_dialect == "B" or self.camera_ego_speed is not None)

  def _confirm_camera_238(self, radar_parser: HyundaiRadarParserConfig, addr: int, msg) -> bool:
    key = (radar_parser.bus, radar_parser.end_addr, addr)
    if not is_radar_track_valid(RADAR_238_255, msg, ""):
      self.camera_238_confirmations.pop(key, None)
      return False
    timestamp = get_track_ts_nanos(radar_parser.parser, f"RADAR_TRACK_{addr:x}", RADAR_238_255, "")
    if radar_parser.cycle_timestamps and radar_parser.cycle_timestamps[-1] - timestamp > 45_000_000:
      # A live cycle-end message cannot keep a missing object's old payload confirmed.
      self.camera_238_confirmations.pop(key, None)
      return False
    distance, lateral, velocity = decode_radar_track(RADAR_238_255, msg, "")
    if radar_parser.camera_dialect == "A":
      velocity -= self.camera_ego_speed
    object_id = int(msg["OBJECT_ID"])
    state = self.camera_238_confirmations.get(key)
    if state is None:
      state = Camera238Confirmation(object_id, timestamp, distance, lateral, velocity)
      state.history.append((timestamp, distance, velocity))
      self.camera_238_confirmations[key] = state
      return False
    return state.observe(object_id, timestamp, distance, lateral, velocity)

  def _update_radar_points_from_parser(self, radar_parser: HyundaiRadarParserConfig) -> int:
    track_count = 0
    for addr in radar_parser.address_range:
      if radar_parser.spec is RADAR_238_255 and (addr - 0x238) % 3:
        continue
      msg_name = f"RADAR_TRACK_{addr:x}"
      msg = get_camera_track_msg(radar_parser, addr) if radar_parser.spec is RADAR_238_255 else radar_parser.parser.vl[msg_name]
      for track_prefix in radar_parser.spec.track_prefixes:
        track_key = get_track_storage_key(radar_parser.spec, addr, track_prefix)
        if radar_parser.spec is RADAR_238_255 and not self._confirm_camera_238(radar_parser, addr, msg):
          self.pts.pop(track_key, None)
          continue
        if radar_parser.spec == RADAR_180_1B9:
          object_id = int(msg[f"{track_prefix}OBJECT_ID"])
          if self.camera_object_ids.get(track_key) != object_id:
            self.pts.pop(track_key, None)
          self.camera_object_ids[track_key] = object_id
        if get_track_ts_nanos(radar_parser.parser, msg_name, radar_parser.spec, track_prefix) != 0 and \
           is_radar_track_valid(radar_parser.spec, msg, track_prefix):
          track_count += 1
          if radar_parser.spec is RADAR_238_255:
            object_id = int(msg["OBJECT_ID"])
            if self.camera_object_ids.get(track_key) != object_id:
              self.pts.pop(track_key, None)
              self.camera_object_ids[track_key] = object_id
          if track_key not in self.pts:
            self.pts[track_key] = structs.RadarData.RadarPoint()
            self.pts[track_key].trackId = self.track_id
            self.track_id += 1

          full_variant = radar_parser.end_addr == radar_parser.spec.end_addr
          d_rel, y_rel, v_rel = decode_radar_track(radar_parser.spec, msg, track_prefix)
          pt = self.pts[track_key]
          pt.dRel = d_rel
          pt.yRel = y_rel
          pt.vRel = v_rel - self.camera_ego_speed if radar_parser.spec is RADAR_238_255 and full_variant else v_rel
          has_track_metadata = radar_parser.spec.name in ("RADAR_180_1B9", "RADAR_210_21F", "RADAR_235_248", "RADAR_3A5_3C4")
          if radar_parser.spec.name == "RADAR_500_53F":
            pt.motionState = 2 if full_variant and int(msg["ONCOMING_ESR"]) else 0
          else:
            pt.motionState = get_radar_track_motion_state(radar_parser.spec, msg, track_prefix) if has_track_metadata else 0
          pt.sourceAddress = addr
          pt.sourceBus = radar_parser.bus
          pt.trackAge = int(msg[f"{track_prefix}AGE"]) if has_track_metadata else min(pt.trackAge + 1, 65535)
        elif track_key in self.pts:
          del self.pts[track_key]
    return track_count

  def _update(self, updated_messages):
    ret = structs.RadarData()
    ret.radarTracksAvailable = self.radar_tracks_available

    if self.CP_SP.flags & HyundaiFlagsSP.RADAR_LEAD_ONLY:
      if self.use_radar_interface_ext and self.rcp is not None:
        return self.update_ext(ret)
      return ret

    active_radar_parsers: list[HyundaiRadarParserConfig] = []
    active_radar_sources: list[tuple[HyundaiRadarParserConfig, int]] = []
    if self.CP_SP.flags & HyundaiFlagsSP.RADAR_FULL_RADAR:
      radar_parsers_by_spec: dict[str, list[HyundaiRadarParserConfig]] = {}
      for radar_parser in self.radar_parsers:
        if not self._radar_range_complete(radar_parser):
          continue
        self.radar_tracks_available = True
        if radar_parser.spec is RADAR_238_255 and not self._camera_238_eligible(radar_parser):
          self.pts = {key: pt for key, pt in self.pts.items()
                      if key[0] != RADAR_238_255.name or pt.sourceBus != radar_parser.bus}
          self.camera_238_confirmations = {key: state for key, state in self.camera_238_confirmations.items()
                                           if key[0] != radar_parser.bus}
          continue
        radar_parsers_by_spec.setdefault(radar_parser.spec.name, []).append(radar_parser)

      ret.radarTracksAvailable = self.radar_tracks_available

      for radar_parsers in radar_parsers_by_spec.values():
        parser = self._select_active_radar_parser(radar_parsers)
        active_radar_parsers.append(parser)
        if self._parser_fresh(parser):
          track_count = self._update_radar_points_from_parser(parser)
        else:
          # Expire only at cycle-driven publication; a silent source cannot add output ticks.
          self.pts = {key: point for key, point in self.pts.items()
                      if not isinstance(key, tuple) or key[0] != parser.spec.name}
          track_count = 0
        active_radar_sources.append((parser, track_count))

    if any(not radar_parser.parser.can_valid for radar_parser in active_radar_parsers):
      ret.errors.canError = True

    ret.trackSources = [{
      "startAddress": radar_parser.spec.start_addr,
      "endAddress": radar_parser.end_addr,
      "bus": radar_parser.bus,
      "trackCount": track_count,
      "sourceKind": int(radar_parser.spec.source_kind == "camera"),
    } for radar_parser, track_count in active_radar_sources]
    ret.points = list(self.pts.values())
    return ret
