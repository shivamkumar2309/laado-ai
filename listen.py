import sounddevice as sd
import numpy as np
import speech_recognition as sr
import queue
import os
import uuid
from scipy.io.wavfile import write

# ─── TUNE THESE FOR YOUR MIC / ROOM ────────────────────────
MIC_ID          = 1
SAMPLERATE      = 16000
SILENCE_THRESH  = 1200    # raise if room noise triggers false detection
SILENCE_DUR     = 2.0     # seconds of silence AFTER speech = done talking
IDLE_TIMEOUT    = 4       # seconds with NO speech = go idle
MAX_RECORD_SEC  = 15       # safety cap
# ─────────────────────────────────────────────────────────


def calibrate_noise_floor(seconds: float = 1.5) -> float:
    """
    Quick ambient noise check — call this once at startup to suggest
    a good SILENCE_THRESH for the current room/mic.
    """
    print("[LAADO] Calibrating mic... stay quiet for a moment.")
    samples = []

    def callback(indata, frames, time, status):
        volume = np.linalg.norm(indata) * 10
        samples.append(volume)

    try:
        with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="int16",
                             callback=callback, device=MIC_ID):
            sd.sleep(int(seconds * 1000))
    except Exception as e:
        print("[CALIBRATION ERROR]", e)
        return SILENCE_THRESH

    if not samples:
        return SILENCE_THRESH

    avg_noise = sum(samples) / len(samples)
    suggested = avg_noise * 2.5
    print(f"[LAADO] Ambient noise avg: {avg_noise:.0f} → suggested threshold: {suggested:.0f}")
    return suggested


def listen() -> str:
    """
    Records from mic and returns recognised text.
    Returns "" on silence/timeout/error — never raises, never hangs forever.
    """
    print("[LAADO] Listening...")
    q = queue.Queue()
    blocksize = 1024

    def callback(indata, frames, time, status):
        volume = np.linalg.norm(indata) * 10
        q.put((indata.copy(), volume))

    try:
        stream = sd.InputStream(
            samplerate=SAMPLERATE,
            channels=1,
            dtype="int16",
            blocksize=blocksize,
            callback=callback,
            device=MIC_ID,
        )
    except Exception as e:
        print("[MIC ERROR]", e)
        return ""

    audio_frames  = []
    speaking      = False
    silence_time  = 0.0
    idle_time     = 0.0
    recorded_time = 0.0
    sec_per_block = blocksize / SAMPLERATE

    try:
        with stream:
            while True:
                try:
                    data, volume = q.get(timeout=3)
                except queue.Empty:
                    print("[LAADO] Mic queue timeout")
                    return ""

                recorded_time += sec_per_block

                if volume > SILENCE_THRESH:
                    speaking     = True
                    silence_time = 0.0
                    idle_time    = 0.0
                    audio_frames.append(data)
                else:
                    if speaking:
                        silence_time += sec_per_block
                        audio_frames.append(data)
                        if silence_time >= SILENCE_DUR:
                            break
                    else:
                        idle_time += sec_per_block
                        if idle_time >= IDLE_TIMEOUT:
                            return ""

                if recorded_time >= MAX_RECORD_SEC:
                    break
    except Exception as e:
        print("[STREAM ERROR]", e)
        return ""

    if not audio_frames:
        return ""

    audio = np.concatenate(audio_frames, axis=0)
    audio = np.clip(audio * 3, -32768, 32767).astype(np.int16)

    wav_path = f"input_{uuid.uuid4().hex[:8]}.wav"
    write(wav_path, SAMPLERATE, audio)

    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True

    try:
        with sr.AudioFile(wav_path) as src:
            audio_data = r.record(src)
            text = r.recognize_google(audio_data, language="en-IN")
            text = text.strip()
            print(f"[USER] {text}")
            return text
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print("[STT NETWORK ERROR]", e)
        return ""
    except Exception as e:
        print("[LISTEN ERROR]", e)
        return ""
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass