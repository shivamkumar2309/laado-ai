from speak import speak
from brain import think
from listen import listen
import webbrowser

print("✅ LAADO START HO RAHI HAI")
speak("Hello Sir, this is Laado, how can I help you today?", "caring")

MODE = "TYPE"          # TYPE or VOICE
VOICE_FIRST = True     # first voice input after wake

EXIT_WORDS = ["exit now", "quit", "ok bye", "band kar do"]

while True:

    # ================= TYPE MODE =================
    if MODE == "TYPE":
        user_input = input("\n⌨️ Type here (or type 'hey listen'): ").strip()

        if not user_input:
            continue

        user_lower = user_input.lower()

        # ❗ EXIT BY TYPING
        if user_lower in EXIT_WORDS:
            speak("Okay Sir, take care, bye.", "caring")
            break

        # WAKE WORD
        if user_lower == "hey listen":
            speak("Hmm, I'm listening Sir.", "normal")
            MODE = "VOICE"
            VOICE_FIRST = True
            continue

        result = think(user_input)

    # ================= VOICE MODE =================
    else:
        # 🔹 First voice after wake = automatic
        if not VOICE_FIRST:
            input("\n🎙️ Press Enter to speak, Sir...")

        VOICE_FIRST = False

        # ⚠️ listen() already prints "Laado is listening"
        text = listen()

        if not text:
            speak("Sorry Sir, main thoda clear nahi sun paayi.", "caring")
            continue

        text_lower = text.strip().lower()

        # ❗ EXIT BY VOICE
        if text_lower in EXIT_WORDS:
            speak("Okay Sir, take care, bye.", "caring")
            break

        # 🔁 BACK TO TYPE MODE
        if text_lower in ["i want to chat", "type mode", "text mode"]:
            speak("Okay Sir, typing mode me aa gaye.", "normal")
            MODE = "TYPE"
            continue

        result = think(text)

    # ================= RESPONSE =================
    reply = result.get("reply", "")
    tone = result.get("tone", "normal")
    action = result.get("action")

    if reply:
        speak(reply, tone)

    if action:
        if action["type"] == "youtube":
            webbrowser.open(
                f"https://www.youtube.com/results?search_query={action['query']}"
            )
        elif action["type"] == "open_site":
            webbrowser.open(action["url"])
