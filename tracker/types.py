# tracker/types.py
from dataclasses import dataclass

@dataclass
class FurnaceConfig:
    lines_per_quarter: int = 4
    transpose_octaves: int = 0
    instrument_hex: str = "00"
    define_instrument: bool = False
    velocity_enabled: bool = False
    velocity_max_hex: str = "FF"
    note_off_mode: str = "REL"
    polyphony_mode: str = "per_track"
    spillover_count: int = 3

    def sanitize(self):
        self.instrument_hex = f"{int(self.instrument_hex or '0', 16) & 0xFF:02X}"
        self.velocity_max_hex = f"{int(self.velocity_max_hex or 'FF', 16) & 0xFF:02X}"
        self.transpose_octaves = max(-6, min(6, int(self.transpose_octaves)))
        if self.note_off_mode not in ("OFF", "REL"):
            self.note_off_mode = "REL"
        if self.polyphony_mode not in ("per_track", "spillover"):
            self.polyphony_mode = "per_track"
        self.spillover_count = max(1, min(16, int(self.spillover_count)))
