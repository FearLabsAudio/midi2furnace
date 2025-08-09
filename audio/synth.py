# audio/synth.py
import pygame
from array import array

_INITIALIZED = False
_CACHE = {}  # (freq, ms, vol*1000, sr, ch) -> Sound

def init_audio():
    """Initialize mixer (if needed). Don't force mono; match device capabilities."""
    global _INITIALIZED
    if _INITIALIZED and pygame.mixer.get_init():
        return

    gi = pygame.mixer.get_init()
    if not gi:
        # Safer default: many backends prefer stereo; we’ll generate to match it.
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    else:
        # Already initialized by something else—use its format.
        pass

    try:
        pygame.mixer.set_num_channels(64)
    except Exception:
        pass
    _INITIALIZED = True


def _make_square(freq_hz: float, ms: int, volume: float = 0.2):
    """Create a square wave Sound that matches the current mixer format."""
    gi = pygame.mixer.get_init()
    if not gi:
        # Shouldn’t happen if init_audio() was called, but be defensive.
        sr, _, ch = 44100, -16, 2
    else:
        sr, _, ch = gi  # (frequency, size, channels)

    n_frames = max(1, int(sr * (ms / 1000.0)))
    freq_hz = max(1.0, float(freq_hz))
    period = max(1, int(sr / freq_hz))
    amp = int(32767 * max(0.0, min(1.0, volume)))

    # Build mono int16 square wave
    mono = array('h', (amp if (i % period) < (period // 2) else -amp for i in range(n_frames)))

    if ch == 1:
        raw = mono.tobytes()
    else:
        # Interleave the mono sample across all channels (e.g., stereo)
        interleaved = array('h')
        extend = interleaved.extend
        for s in mono:
            extend((s,) * ch)
        raw = interleaved.tobytes()

    return pygame.mixer.Sound(buffer=raw)


def tone(freq_hz: float, ms: int, volume: float = 0.2) -> pygame.mixer.Sound:
    gi = pygame.mixer.get_init()
    if gi:
        sr, _, ch = gi
    else:
        sr, ch = 44100, 2
    key = (int(freq_hz), int(ms), int(volume * 1000), int(sr), int(ch))
    snd = _CACHE.get(key)
    if snd is None:
        snd = _make_square(freq_hz, ms, volume)
        _CACHE[key] = snd
    return snd
