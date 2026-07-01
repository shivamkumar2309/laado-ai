import os
import json
import datetime
import threading

from dotenv import load_dotenv
load_dotenv()   # reads GROQ_API_KEY from a local .env file if present

import memory   # ← SQLite-backed persistent memory

# ═══════════════════════════════════════════════
#  GROQ CONFIG
# ═══════════════════════════════════════════════
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"

if not GROQ_API_KEY:
    print(
        "[LAADO WARNING] GROQ_API_KEY not set. "
        "Create a .env file or set the environment variable. "
        "See README.md for setup instructions."
    )

def _groq_client():
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


# ═══════════════════════════════════════════════
#  IN-RAM SESSION MEMORY (mirrors DB for this run,
#  kept small — DB is the real long-term memory)
# ═══════════════════════════════════════════════
session_memory = memory.get_recent_messages(limit=20)
MAX_MEMORY = 20
SUMMARIZE_EVERY = 12   # after this many new turns, compress old ones


# ═══════════════════════════════════════════════
#  SYSTEM PROMPT — uses DB facts + last summary
# ═══════════════════════════════════════════════
def build_system_prompt() -> str:
    profile = memory.get_profile()
    name    = profile.get("name", "")
    title   = profile.get("title", "Sir")
    facts   = memory.get_facts(limit=15)
    summary = memory.get_latest_summary()

    facts_str   = "; ".join(facts) if facts else "Nothing yet."
    summary_str = summary if summary else "No earlier conversation summary yet."

    return f"""You are LAADO, a personal AI assistant like Jarvis from Iron Man.

PERSONALITY: calm, warm, caring, slightly playful, always dignified. Also an excellent B.Tech teacher.

USER INFO:
- Name: {name or "unknown"}
- Title to use: {title}
- Known facts about user: {facts_str}
- Summary of earlier conversations: {summary_str}

You must respond with ONLY a valid JSON object (no markdown, no backticks, no explanation outside JSON). Structure:

{{
  "intent": "chat" | "exit" | "wake_check" | "open_site" | "youtube" | "save_name" | "time" | "date" | "recall",
  "site_query": "string or null — only if intent is open_site",
  "youtube_query": "string or null — only if intent is youtube",
  "recall_keyword": "string or null — only if intent is recall, e.g. user asks 'what do you know about my college'",
  "extracted_name": "string or null — only if user told their name",
  "new_facts": [
    {{"fact": "short fact text", "category": "identity|preference|goal|mood|misc"}}
  ],
  "reply": "your natural spoken reply, 1-3 sentences, no asterisks, no markdown, no brackets, sounds good spoken aloud",
  "tone": "normal" | "caring" | "logical" | "excited" | "romantic"
}}

INTENT RULES:
- "exit": user wants to end conversation (bye, quit, exit, band karo, goodbye, stop laado, shut down)
- "wake_check": user is just checking you're there
- "open_site": user wants ANY website opened — resolve the correct domain yourself, even for less common sites. Never limit to a fixed list.
- "youtube": user wants something played/searched on YouTube specifically
- "save_name": user is telling you their name
- "time" / "date": user is asking current time/date (system handles the actual value, you don't need to know it)
- "recall": user is asking you to remember/recall something specific about them (e.g. "what's my college", "do you remember what I like")
- "chat": everything else

Always extract new_facts silently when user reveals personal info (city, college, interests, mood, goals) — even during normal chat, categorize them properly. Keep reply concise and natural for text-to-speech. Address user as '{title}' at most once per reply, only when natural. Use the summary and facts above to maintain continuity with earlier conversations."""


def think(user_text: str) -> dict:
    """
    Single unified AI call decides intent, action, reply, tone, and facts.
    No streaming — the full reply is generated, then spoken once.
    """
    global session_memory

    session_memory.append({"role": "user", "content": user_text})
    if len(session_memory) > MAX_MEMORY:
        session_memory = session_memory[-MAX_MEMORY:]

    memory.log_message("user", user_text)

    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session_memory)

    try:
        client = _groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
    except Exception as e:
        print("[BRAIN ERROR]", e)
        return {
            "reply": "I'm having a little trouble thinking right now, Sir.",
            "tone": "caring",
            "action": None,
            "exit": False,
        }

    intent = data.get("intent", "chat")
    reply  = data.get("reply", "")
    tone   = data.get("tone", "normal")

    # ── Save name ──
    if data.get("extracted_name"):
        name = data["extracted_name"].strip().capitalize()
        memory.set_profile_value("name", name)
        memory.add_fact(f"Name is {name}", category="identity")

    # ── Save new facts (background, non-blocking) ──
    new_facts = data.get("new_facts", [])
    if new_facts:
        threading.Thread(target=_save_facts_async, args=(new_facts,), daemon=True).start()

    # ── Recall — search DB for relevant facts ──
    if intent == "recall" and data.get("recall_keyword"):
        found = memory.search_facts(data["recall_keyword"])
        if found:
            reply = "Here's what I remember: " + "; ".join(found) + "."
        else:
            reply = "I don't have anything saved about that yet, Sir."

    # ── Time/date (system clock, AI doesn't know real time) ──
    elif intent == "time":
        now = datetime.datetime.now().strftime("%I:%M %p")
        reply = f"It is {now}, Sir."
    elif intent == "date":
        today = datetime.datetime.now().strftime("%A, %d %B %Y")
        reply = f"Today is {today}."

    # ── Build action ──
    action = None
    if intent == "open_site" and data.get("site_query"):
        url = _resolve_url(data["site_query"])
        action = {"type": "open_site", "url": url}
    elif intent == "youtube" and data.get("youtube_query"):
        action = {"type": "youtube", "query": data["youtube_query"]}

    is_exit = (intent == "exit")

    session_memory.append({"role": "assistant", "content": reply})
    if len(session_memory) > MAX_MEMORY:
        session_memory = session_memory[-MAX_MEMORY:]

    memory.log_message("assistant", reply)

    # ── Auto-summarize periodically (background, non-blocking) ──
    if memory.count_messages() % SUMMARIZE_EVERY == 0:
        threading.Thread(target=_summarize_async, daemon=True).start()

    return {
        "reply": reply,
        "tone": tone,
        "action": action,
        "exit": is_exit,
        "wake": (intent == "wake_check"),
    }


def _resolve_url(query: str) -> str:
    q = query.strip().lower()
    if q.startswith("http"):
        return q
    if "." not in q:
        q = q + ".com"
    return "https://" + q


def _save_facts_async(new_facts: list):
    try:
        for item in new_facts:
            if isinstance(item, dict):
                memory.add_fact(item.get("fact", ""), item.get("category", "misc"))
            elif isinstance(item, str):
                memory.add_fact(item, "misc")
    except Exception as e:
        print("[FACT SAVE ERROR]", e)


def _summarize_async():
    """
    Compresses older conversation into a short summary so context
    isn't lost even after thousands of messages — keeps the prompt small.
    """
    try:
        recent = memory.get_recent_messages(limit=SUMMARIZE_EVERY)
        if len(recent) < 4:
            return

        convo_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        prev_summary = memory.get_latest_summary()

        prompt = (
            "Summarize this conversation segment in 2-3 short sentences, "
            "focusing on what matters for future context (topics discussed, "
            "user's goals, important details). Be concise.\n\n"
        )
        if prev_summary:
            prompt += f"Previous summary: {prev_summary}\n\n"
        prompt += f"New conversation:\n{convo_text}\n\nUpdated summary:"

        client = _groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        new_summary = response.choices[0].message.content.strip()
        memory.save_summary(new_summary)
        memory.clear_old_messages(keep_last=10)

    except Exception as e:
        print("[SUMMARIZE ERROR]", e)


# ═══════════════════════════════════════════════
#  Lightweight wake-word check (no API call)
# ═══════════════════════════════════════════════
WAKE_WORDS = ["wake up", "laado wake", "hey laado", "are you there", "start listening"]

def is_wake_word(text: str) -> bool:
    t = text.lower().strip()
    return any(w in t for w in WAKE_WORDS)