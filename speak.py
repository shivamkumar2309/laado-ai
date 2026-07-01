import asyncio
import edge_tts
import os
import uuid
from playsound import playsound

VOICE = "en-IN-NeerjaExpressiveNeural"

TONE_SETTINGS = {
    "normal":   {"rate": "-5%",  "volume": "-10%"},
    "caring":   {"rate": "-20%", "volume": "-25%"},
    "logical":  {"rate": "+5%",  "volume": "-5%"},
    "romantic": {"rate": "-10%", "volume": "-15%"},
    "excited":  {"rate": "+15%", "volume": "+0%"},
}


async def _speak_async(text: str, tone: str, filepath: str):
    settings = TONE_SETTINGS.get(tone, TONE_SETTINGS["normal"])
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=settings["rate"],
        volume=settings["volume"],
    )
    await communicate.save(filepath)


def speak(text: str, tone: str = "normal"):
    """Standard one-shot speak — used for fixed replies (time, exit, etc)."""
    print(f"[LAADO | {tone.upper()}] {text}")
    if not text.strip():
        return

    filepath = f"laado_{uuid.uuid4().hex[:8]}.mp3"
    try:
        asyncio.run(_speak_async(text, tone, filepath))
        playsound(filepath)
    except Exception as e:
        print("[SPEAK ERROR]", e)
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass