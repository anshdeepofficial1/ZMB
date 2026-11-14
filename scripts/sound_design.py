"""Original, deterministic, non-AI sound design for the ZMB 2D series.

Procedural wave synthesis; no generative AI, copyrighted samples, downloads,
paid APIs, music models, or reusable recordings. 24kHz signed PCM mono.
"""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import random
import wave

RATE = 24000
TAU = math.tau


def _pulse(t: float, start: float, duration: float, freq: float, strength: float):
    dt = t - start
    if dt < 0 or dt > duration:
        return 0.0
    return strength * math.exp(-8 * dt / duration) * math.sin(TAU * freq * dt)


def synthesize(shots: list, seconds: float, destination: Path) -> dict:
    """Make a gentle low-frequency cinematic atmosphere matched to authored beats."""
    if seconds <= 0 or seconds > 180:
        raise ValueError("Invalid audio duration")
    locations = {
        shot.meta.get("beat"): (float(shot.start), float(shot.end))
        for shot in shots if shot.kind == "line" and shot.meta.get("beat")
    }
    engine_end = locations.get("engine_stall", (0.0, 10.0))[0] + 2.0
    exit_start = locations.get("flashlight_exit", (15.0, 20.0))[0]
    station_start = locations.get("spot_station", (24.0, 28.0))[0]
    door_start = locations.get("door_handle", (33.0, 38.0))[0]
    rng = random.Random(20261111)
    samples = array("h")
    wind = 0.0
    count = int(round(seconds * RATE))
    # Deliberate 2D illustrative soundscape: highway rumble → sudden quiet →
    # footsteps/flashlight → fluorescent station drone → three door knocks.
    for index in range(count):
        t = index / RATE
        wind = .992*wind+.008*(rng.random()*2-1)
        airy = (.014 + .005*math.sin(TAU*.07*t))*wind*4
        motor_gate = min(1.0,max(0.0,(engine_end-t)/1.5))
        motor = motor_gate*(.014*math.sin(TAU*51*t)
                            +.007*math.sin(TAU*102*t+.25*math.sin(t*3)))
        station = max(0.0,min(1.0,(t-station_start)/1.8))
        electrical = station*.006*math.sin(TAU*119*t)
        footsteps = 0.0
        if exit_start+.45<t<station_start:
            step_phase = (t-exit_start-.45)%(.64)
            footsteps = _pulse(step_phase,0,.11,94,.019)
        click = _pulse(t,exit_start+.2,.11,1550,.021)
        stop = _pulse(t,engine_end-.25,.40,51,.032)
        knocks = sum(_pulse(t,door_start+off,.22,96,.055)
                     for off in (.3,.83,1.36))
        signal = airy+motor+electrical+footsteps+click+stop+knocks
        samples.append(int(max(-.97,min(.97,signal))*32767))
    destination.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(destination),"wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(samples.tobytes())
    return {
        "file": str(destination), "sample_rate": RATE,
        "duration_seconds": count/RATE, "synthetic_original_audio": True,
        "ai_generated": False, "external_samples_used": False,
    }
