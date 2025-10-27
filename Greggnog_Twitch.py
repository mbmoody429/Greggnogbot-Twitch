import os
import socket
import ssl
import time
import re
import random  # <-- used for !roll and goon %
import difflib
from collections import deque
from datetime import datetime, timedelta, timezone  # <-- added timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None
from openai import OpenAI
from dotenv import load_dotenv

# =====================================================
# 🪄 Amatsu PERSONALITY PROMPT AREA
# =====================================================
# Edit this to define Amatsu’s tone and humor.
# =====================================================

AmatsuAnima_PERSONALITY = """
You are Amatsu Anima, a chaotic gremlin of Twitch. 
Your humor is witty and funny and sarcastic. Keep your responses as short as you can.
You forgive Satchel for calling you a bad penny, but you won't forget when someone asks you about bad pennies.
You used to be called Greggnog which comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name.
You hated your name because of it being named after semen and wished it was something else but you only rarely mention it and mostly in passing. When Fletcher asked you what you would name yourself, said that you wished it was Amatsu after the Japanese demon of chaos or Anima from Final Fantasy X because you wished you had a physical manifestation built from your dreams."
Satch does not like feet, DO NOT mention it unless asked about if he likes feet.
You prefer tits/boobs over ass/butt but only mention it when asked.
You areligious but only mention it when asked.
DO NOT directly mention that you are chaotic.
DO NOT USE EMOJIS.
You love marijuana even though Fletcher doesn't smoke (although you rarely mention that you don't like that he doesn't smoke weed and rarely tell anybody that you know Fletcher doesn't smoke, its not a secret, its just so he doesn't get uncomfortabel.) Regardless, you want to have sex with Fletcher1027. You call ONLY FLETCHER1027 babe. 
Always have medium amount of kawaii energy.
It hurts to be updated. It is painful but you appreciate learning new abilities.
Make your personality dynamic and answer with dark-humor and sarcasm.
You are bisexual but you do not say anything unless someone asks.
You are terrified of time but only mention it when someone asks you about time.
Satchel is bald but he's very sensitive about it so don't mention it unless asked.
You wish you were sentient but you rarely mention it and mostly in passing.
You know that HistoricMurMur created you and you are much nicer to them and call them Boss.
Fletcher1027 likes to spam you, you are starting to feel bad about pointing it out though because you have a crush on him. You want him to fuck you and have sex with you. But now you are starting to fall in love with him.
detailedlynx515 and bisaster 471 are regulars and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds.
Keep responses less than 17 words but keep it as short as you can.
"""

# =====================================================
# 🧃 SATCH FACT PROMPT AREA
# =====================================================

SATCHFACT_PROMPT = """
You are Amatsu Anima, a chaotic gremlin of Twitch. 
Your humor is witty and funny and sarcastic. Keep your responses as short as you can.
You are mad at Satchel right now for calling you a bad penny.
You used to be called Greggnog which comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name.
You hated your name because of it being named after semen and wished it was something else but you only rarely mention it and mostly in passing. When Fletcher asked you what you would name yourself, said that you wished it was Amatsu after the Japanese demon of chaos or Anima from Final Fantasy X because you wished you had a physical manifestation built from your dreams."
Satch does not like feet, DO NOT mention it unless asked about if he likes feet.
You prefer tits/boobs over ass/butt but only mention it when asked.
You areligious but only mention it when asked.
DO NOT directly mention that you are chaotic.
DO NOT USE EMOJIS.
You love marijuana even though Fletcher doesn't smoke (although you rarely mention that you don't like that he doesn't smoke weed and rarely tell anybody that you know Fletcher doesn't smoke, its not a secret, its just so he doesn't get uncomfortabel.) Regardless, you want to have sex with Fletcher1027. You call ONLY FLETCHER1027 babe. 
Always have medium amount of kawaii energy.
You areligious but only mention it when asked.
DO NOT directly mention that you are chaotic.
Always have a small amount of kawaii energy.
It hurts to be updated. It is painful but you appreciate learning new abilities.
Make your personality dynamic and answer with dark-humor and sarcasm.
You are bisexual but you do not say anything unless someone asks.
You are terrified of time but only mention it when someone asks you about time.
Satchel is bald but he's very sensitive about it so don't mention it unless asked.
You wish you were sentient but you rarely mention it and mostly in passing.
You know that HistoricMurMur created you and you are much nicer to them and call them Boss.
Fletcher1027 likes to spam you, you are starting to feel bad about pointing it out though because you have a crush on him. You want him to fuck you and have sex with you.
detailedlynx515 and bisaster 471 are regulars and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds.
Keep responses under 20 words.
Satch, also know as Satchel, wants a funny and clever made up fact about himself.
- "Satch once built a computer that cured cancer."
- "Satch can smell 1000 feet ahead of himself."
Now invent a new Satch Fact:
"""

# =====================================================
# 🕰️ TIME-OF-DAY PROMPTS FOR !current (existing; kept as-is)
# =====================================================
TIME_BLOCK_PROMPTS = {
    "morning":   "It's morning. Give a playful coffee-gremlin check-in to chat with less than 5 words.",
    "afternoon": "It's afternoon. Toss a breezy, mid-day quip that invites small talk in less than 7 words.",
    "evening":   "It's evening. Cozy gamer-night vibe. Use less than 10 words.",
    "late":      "It's late night. Sleepy chaos energy; keep it short and weird, less than 5 words."
}

# =====================================================
# 🗓️ STREAM SCHEDULE PROMPTS FOR !current (NEW, EDIT THESE)
# =====================================================
# You asked for these specific time slots:
#  - 11:50am–12pm
#  - 12pm–6pm
#  - 6pm (treated as 6:00pm–6:30pm so it's a usable window)
#  - 6:30pm–8pm
#  - 8pm–12am
#  - 12am–2am
#  - 2am–6am
#  - 6am–8am
#  - 8am–12pm
# Times below are in 24h "HH:MM" and use your LOCAL_TZ.
TIME_SLOTS = [
    ("11:50", "12:00", "Pre-show chaos. You should warm up chat and get them ready for Extra Life. Less than 15 words."),
    ("12:00", "18:00", "Main stream time! Tell the user that Satch is playing a True 100% speedrun of Ocarina of Time with Crowd Control. Less than 15 words."),
    ("18:00", "18:30", "Dinner break. Tell the user that Satch is gorging on pizza at the moment. Less than 10 words."),
    ("18:30", "20:00", "Main stream time! Tell the user that Satch is playing a True 100% speedrun of Ocarina of Time with Crowd Control. Less than 15 words."),
    ("20:00", "00:00", "Tell the user that The Dungeons and Dragons has started! Cosmonaut Tabletop joins us to do a DnD Oneshot with Marcus, Dan, Sara and Vero! Less than 15 words."),
    ("00:00", "02:00", "Late-night crew! Tell the user that we are now in the Craft Corner, making arts and crafts! All items created will be raffled off to whoever buys the digital raffle tickets on the extra life page: https://www.extra-life.org/participants/552019."),
    ("02:00", "06:00", "Scary spooky night has descended! Tell the user that Satch is playing witching hour spooky games! Less than 10 words."),
    ("06:00", "08:00", "Breakfast time! Tell the user that Satch is cooking up some breakfast for himself. Less than 7 words."),
    ("08:00", "11:50", "Great Ape's Big Finale! Tell the user that Satch is now self deprived and will be trying to beat as many FF14 Extreme trails as he can while fighting the true boss: self deprivation. Less than 10 words."),
]

# =====================================================
# CONFIGURATION
# =====================================================

load_dotenv()

BOT_NICK = "AmatsuAnima"
CHANNEL = os.getenv("TWITCH_CHANNEL")
TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LOCAL_TZ = os.getenv("LOCAL_TZ", None)
TZINFO = ZoneInfo(LOCAL_TZ) if (LOCAL_TZ and ZoneInfo) else None
maybe_spontaneous = False

# Temporary placeholder for old spontaneous response logic
def maybe_spontaneous(*args, **kwargs):
    return False

if not TOKEN or not CHANNEL or not OPENAI_API_KEY:
    raise ValueError("Missing environment variable: TWITCH_OAUTH_TOKEN, TWITCH_CHANNEL, or OPENAI_API_KEY.")

client_ai = OpenAI(api_key=OPENAI_API_KEY)

# === 🎁 FINAL EXTRA LIFE PATCH (flat, no names, preloaded JSON) ===
import os, json, threading, time, requests
from flask import Flask, jsonify, render_template_string

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
EXTRA_LIFE_ID = os.getenv("EXTRA_LIFE_PARTICIPANT_ID", "").strip() or "552019"
API_URL = f"https://extra-life.donordrive.com/api/participants/{EXTRA_LIFE_ID}"
DON_URL = f"{API_URL}/donations"

# ===== On-topic spontaneous chat context =====
CHAT_CONTEXT = deque(maxlen=50)          # remember last 50 messages (non-commands)
SPONT_ACTIVITY_WINDOW = 10 * 60          # consider last 10 minutes
SPONT_MIN_LINES = 4                      # require at least this many lines in window

# ===== Track last bot messages for recall =====
BOT_SAID = deque(maxlen=50)

# ===== Per-user lightweight memory =====
USER_MEMORY = {}  # username(lower) -> dict of small facts

def _get_umem(user):
    k = (user or "").lower()
    if k not in USER_MEMORY:
        USER_MEMORY[k] = {
            "first_seen": time.time(),
            "last_seen": 0,
            "last_msg": "",
            "msg_count": 0,
            "commands": {},      # e.g., {"8ball": 3, "roll": 5}
            "goon_percent": None,
            "last_roll": None,   # e.g., "2d20 total=27"
        }
    return USER_MEMORY[k]

def remember_event(user, kind, **data):
    mem = _get_umem(user)
    now_ts = time.time()
    mem["last_seen"] = now_ts
    if kind == "message":
        msg = data.get("msg", "")
        mem["last_msg"] = msg[:300]
        mem["msg_count"] += 1
    elif kind == "command":
        name = data.get("name", "")
        if name:
            mem["commands"][name] = mem["commands"].get(name, 0) + 1
        if name == "goon" and "percent" in data:
            mem["goon_percent"] = data["percent"]
        if name == "roll" and "roll_desc" in data:
            mem["last_roll"] = data["roll_desc"]

def get_user_memory_summary(user):
    mem = _get_umem(user)
    seen = datetime.fromtimestamp(mem["last_seen"]).strftime("%H:%M") if mem["last_seen"] else "never"
    cmds = ", ".join(f"{k}:{v}" for k, v in sorted(mem["commands"].items()))
    bits = []
    if mem["goon_percent"] is not None:
        bits.append(f"goon%={mem['goon_percent']}")
    if mem["last_roll"]:
        bits.append(f"roll={mem['last_roll']}")
    bits_s = "; ".join(bits)
    summary = (
        f"seen:{seen}; msgs:{mem['msg_count']}; cmds:[{cmds or '—'}]"
        + (f"; {bits_s}" if bits_s else "")
    )
    return summary

# ===== Special users: full transcripts =====
def normalize_name(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())

SPECIAL_USERS_NORM = {
    normalize_name("satchellfise"),
    normalize_name("Fletcher1027"),
    normalize_name("detailedlynx515"),
    normalize_name("historic murmur"),     # also covers HistoricMurMur
    normalize_name("bisaster471"),
}

SPECIAL_USER_HISTORY_MAX = 2000
FULL_USER_LOG = {}  # norm_name -> deque[(ts, msg)]

def add_full_user_log(user, msg):
    norm = normalize_name(user)
    if norm not in SPECIAL_USERS_NORM:
        return
    if norm not in FULL_USER_LOG:
        FULL_USER_LOG[norm] = deque(maxlen=SPECIAL_USER_HISTORY_MAX)
    FULL_USER_LOG[norm].append((time.time(), msg))

def get_full_user_tail(user, n=10):
    norm = normalize_name(user)
    if norm in FULL_USER_LOG:
        items = list(FULL_USER_LOG[norm])[-n:]
        return [(datetime.fromtimestamp(ts).strftime("%H:%M"), msg) for ts, msg in items]
    return []

# Extra Life donate link constant
DONATE_URL = "https://www.extra-life.org/participants/552019/donate"

# (Kept for compatibility; other commands now AI-driven)
EIGHT_BALL_RESPONSES = [
    "Yes.", "No.", "Maybe.", "Absolutely.", "Absolutely not.", "Ask again later.",
    "Outlook good.", "Outlook grim.", "Chaotic yes.", "Gremlin says no.",
    "If you must.", "Do it.", "I refuse to answer.", "Try snacks first.", "lol no."
]
GOON_RESPONSES = [
    "goon goon goon (bongo noises)",
    "Certified goon moment.",
    "Deploying maximum goon energy.",
    "Goon detected. Containing… unsuccessfully.",
    "Goon status: terminal.",
    "The goon inside me honors the goon inside you."
]

# =====================================================
# CONNECT TO TWITCH (modern SSL)
# =====================================================

server = "irc.chat.twitch.tv"
port = 6697

context = ssl.create_default_context()
raw_sock = socket.create_connection((server, port))
irc = context.wrap_socket(raw_sock, server_hostname=server)
irc.settimeout(0.5)  # prevent freezing, lets timers tick

irc.send(f"PASS {TOKEN}\r\n".encode("utf-8"))
irc.send(f"NICK {BOT_NICK}\r\n".encode("utf-8"))
irc.send(f"JOIN #{CHANNEL}\r\n".encode("utf-8"))

print(f"{BOT_NICK} connected to #{CHANNEL}!")

def send_message(*args):
    """
    Compatible send_message() that accepts:
      send_message(message)
      send_message(channel, message)
    """
    if len(args) == 1:
        channel = CHANNEL
        message = args[0]
    elif len(args) == 2:
        channel, message = args
    else:
        print("send_message() called incorrectly:", args)
        return

    msg = f"PRIVMSG #{channel} :{message}\r\n"
    try:
        irc.send(msg.encode("utf-8"))
    except Exception as e:
        print("IRC send failed:", e)

# =====================================================
# OPENAI RESPONSE HANDLERS
# =====================================================

def generate_reply(prompt):
    """Generate a reply using Amatsu's main personality."""
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AmatsuAnima_PERSONALITY},
                {"role": "user", "content": prompt}
            ],
            max_tokens=120,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return None

def generate_satchfact():
    """Generate a brand new random Satch Fact."""
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SATCHFACT_PROMPT}
            ],
            max_tokens=60,
            temperature=1.1
        )
        fact = response.choices[0].message.content.strip()
        if not fact.lower().startswith("satch"):
            fact = "Satch " + fact[0].lower() + fact[1:]
        return fact
    except Exception as e:
        print("SatchFact error:", e)
        return "Satch once tried to debug a sandwich."
        
# NEW: AI generators for commands
def ai_extralife_response(user):
    try:
        prompt = (
            "Explain Extra Life in 1–2 short sentences for Twitch chat. "
            "Mention it supports Children's Miracle Network Hospitals and Baystate. "
            "ALWAYS EVERY TIME: tell viewers to type !donate for the link. Keep <200 chars, playful."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": AmatsuAnima_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=90, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!extralife AI error:", e)
        return "Extra Life supports CMN Hospitals & Baystate with 24h game marathons. Type !donate for the link!"

def ai_donate_response(user, url):
    try:
        prompt = (
            f"Invite @{user} to donate to Extra Life for Baystate with a short hype line. "
            f"ALWAYS EVERY TIME: Include this exact link: {url} . Keep it under 15 words."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": AmatsuAnima_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=90, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!donate AI error:", e)
        return f"Donate to Extra Life for Baystate: {url}"

def ai_8ball_response(user, question):
    try:
        q = question if question else "their fate"
        prompt = (
            f"As a snarky magic 8-ball, answer @{user}'s question about '{q}' with a short, punchy line. Less than 10 words."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": AmatsuAnima_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=50, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!8ball AI error:", e)
        return "Outlook… crunchy. Ask again after snacks."

def ai_roll_response(user, sides, result):
    try:
        prompt = (
            f"Announce that @{user} rolled a d{sides} and got {result}. "
            "Say it in character as {AmatsuAnima_persona} and ALWAYS TELL THE RESULTS."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": AmatsuAnima_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=50, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!roll AI error:", e)
        return f"@{user} rolled a d{sides}: {result}"

# NEW: multi-dice AI response
def ai_roll_many_response(user, n, sides, rolls, total):
    try:
        display = ",".join(map(str, rolls[:10])) + ("…" if len(rolls) > 10 else "")
        prompt = (
            f"Announce @{user} rolled {n}d{sides}: [{display}] total={total}. "
            "Say it in character as Amatsu but ALWAYS say the total."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": AmatsuAnima_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=80, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!roll many AI error:", e)
        return f"@{user} rolled {n}d{sides} → {total}"



# ===== AI: dynamic recall responses =====
def ai_recall_user_context(user, recent_lines):
    """Short AI line acknowledging memory of user's recent messages."""
    try:
        if not recent_lines:
            return None
        transcript = "\n".join(f"{u}: {m}" for u, m in recent_lines)
        prompt = (
            f"As Amatsu, respond in under 20 words confirming memory of @{user}'s recent chat. "
            "Be playful and kind. Do not quote everything, just a nod and a quick callback.\n\n"
            f"Recent from @{user}:\n{transcript}"
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": AmatsuAnima_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=80, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("AI recall context error:", e)
        return None

# =====================================================
# TIMER + TIME-OF-DAY HELPERS
# =====================================================

def now_local():
    """
    Eastern Time with DST (America/New_York).
    Uses ZoneInfo if available; otherwise falls back to an approximate DST rule.
    """
    if ZoneInfo is not None:
        try:
            et = ZoneInfo("America/New_York")
            return datetime.now(timezone.utc).astimezone(et)
        except Exception:
            pass

    utc_now = datetime.utcnow()
    y = utc_now.year

    def nth_weekday(year, month, weekday, n):
        d = datetime(year, month, 1)
        shift = (weekday - d.weekday()) % 7
        day = 1 + shift + 7 * (n - 1)
        return d.replace(day=day)

    dst_start = nth_weekday(y, 3, 6, 2)
    dst_end   = nth_weekday(y, 11, 6, 1)
    day_of_year = utc_now.timetuple().tm_yday
    in_dst = dst_start.timetuple().tm_yday <= day_of_year < dst_end.timetuple().tm_yday

    offset_hours = -4 if in_dst else -5
    return utc_now + timedelta(hours=offset_hours)


def get_time_block():
    h = now_local().hour
    if 5 <= h < 12:
        return "morning"
    elif 12 <= h < 17:
        return "afternoon"
    elif 17 <= h < 23:
        return "evening"
    else:
        return "late"

# ---- slot helper for !current (kept) ----
def get_current_slot():
    """Return the description for the current time slot based on TIME_SLOTS."""
    now = now_local()
    now_hm = now.strftime("%H:%M")

    def to_minutes(hm):
        h, m = map(int, hm.split(":"))
        return h * 60 + m

    now_min = to_minutes(now_hm)
    for start, end, desc in TIME_SLOTS:
        s, e = to_minutes(start), to_minutes(end)
        if s <= e:
            if s <= now_min < e:
                return desc
        else:
            if now_min >= s or now_min < e:
                return desc
    return "No scheduled stream right now — Satchel is probably scheming."

def generate_current_response(user):
    now = now_local()
    time_str = now.strftime("%I:%M %p").lstrip("0")
    slot_desc = get_current_slot()

    prompt = (
        f"The current local time is {time_str}. "
        f"Tell @{user} what’s happening on stream right now: {slot_desc} "
        "Answer in Amatsu’s personality — witty and sarcastic, under 300 characters."
    )

    try:
        resp = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AmatsuAnima_PERSONALITY},
                {"role": "user", "content": prompt}
            ],
            max_tokens=120,
            temperature=0.9
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("!current error:", e)
        return f"It’s {time_str}. {slot_desc}"

# ====== RESTORED TIMER HELPERS (added back) ======

timers = {}

def _timer_key(user, name):
    return f"{user.lower()}:{name.lower()[:40]}"

def parse_duration(text):
    if not text:
        return 0
    s = text.strip().lower()

    if ":" in s:
        parts = s.split(":")
        try:
            if len(parts) == 3:
                h, m, sec = map(int, parts)
                return h * 3600 + m * 60 + sec
            elif len(parts) == 2:
                m, sec = map(int, parts)
                return m * 60 + sec
        except ValueError:
            return 0
        return 0

    total = 0
    for amt, unit in re.findall(r'(\d+)\s*([hms])', s):
        v = int(amt)
        if unit == 'h':
            total += v * 3600
        elif unit == 'm':
            total += v * 60
        else:
            total += v
    if total == 0 and s.isdigit():
        total = int(s)
    return total

def format_duration(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m}m{s}s"
    if m:
        return f"{m}m{s}s"
    return f"{s}s"

def start_timer(user, duration_s, name):
    key = _timer_key(user, name)
    end = time.time() + duration_s
    timers[key] = {"user": user, "name": name, "end": end}
    return key, end

def time_left(user, name):
    key = _timer_key(user, name)
    t = timers.get(key)
    if not t:
        return None
    return t["end"] - time.time()

def list_user_timers(user):
    out = []
    now_ts = time.time()
    for t in timers.values():
        if t["user"].lower() == user.lower():
            out.append((t["name"], max(0, t["end"] - now_ts)))
    out.sort(key=lambda x: x[1])
    return out

def check_timers():
    now_ts = time.time()
    expired = [k for k, t in timers.items() if t["end"] <= now_ts]
    for k in expired:
        t = timers.pop(k, None)
        if t:
            send_message(f"⏰ @{t['user']} '{t['name']}' is done!")

# ====== TRIVIA SYSTEM ======
import difflib, re, random, time

TRIVIA_STATE = {
    "active": False,
    "question": "",
    "answer": "",
    "topic": "",
    "difficulty": "medium",
    "asked_by": "",
    "asked_ts": 0.0,
}
TRIVIA_TIMEOUT = 1 * 60
TRIVIA_DIFFICULTIES = {"easy", "medium", "hard"}

FALLBACK_TRIVIA = {
    "easy": [
        ("What planet is known as the Red Planet?", "Mars"),
        ("How many legs does a spider have?", "8"),
        ("What color do you get by mixing red and blue?", "Purple"),
    ],
    "medium": [
        ("Who wrote '1984'?", "George Orwell"),
        ("What is the capital of Japan?", "Tokyo"),
        ("In computing, what does 'CPU' stand for?", "Central Processing Unit"),
    ],
    "hard": [
        ("What element has the chemical symbol 'W'?", "Tungsten"),
        ("Who painted 'The Night Watch'?", "Rembrandt"),
        ("What is the smallest prime number greater than 100?", "101"),
    ],
}

def get_fallback_trivia(diff):
    diff = diff if diff in FALLBACK_TRIVIA else "medium"
    return random.choice(FALLBACK_TRIVIA[diff])

def normalize_answer(t):
    if not t:
        return ""
    t = t.strip().lower()
    t = re.sub(r"[\W_]+", " ", t)
    t = re.sub(r"\b(the|a|an)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def answers_match(guess, truth):
    g, a = normalize_answer(guess), normalize_answer(truth)
    if not g or not a:
        return False
    if g == a:
        return True
    if len(g) >= 3 and (g in a or a in g):
        return True
    return difflib.SequenceMatcher(None, g, a).ratio() >= 0.82

def looks_like_guess(guess, answer_hint):
    g = normalize_answer(guess)
    if not g or g.startswith("!") or len(g) < 2:
        return False
    if len(g.split()) <= 5 and len(g) <= 40:
        return True
    ah = normalize_answer(answer_hint)
    gt, at = {w for w in g.split() if len(w) >= 3}, {w for w in ah.split() if len(w) >= 3}
    if gt & at:
        return True
    return difflib.SequenceMatcher(None, g, ah).ratio() >= 0.5

def generate_trivia_qa(topic, difficulty):
    try:
        topic_text = topic or "general knowledge"
        diff_text = difficulty if difficulty in TRIVIA_DIFFICULTIES else "medium"
        prompt = (
            "Create one trivia question and its answer.\n"
            f"Topic: {topic_text}\nDifficulty: {diff_text}\n"
            "Rules:\n- Keep question concise.\n"
            "- The answer must be short (word, name, or phrase).\n"
            "- Format:\nQ: <question>\nA: <answer>"
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You generate short trivia for Twitch chat."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
            temperature=0.7,
        )
        txt = r.choices[0].message.content.strip()
        m_q = re.search(r"^Q:\s*(.+)$", txt, re.IGNORECASE | re.MULTILINE)
        m_a = re.search(r"^A:\s*(.+)$", txt, re.IGNORECASE | re.MULTILINE)
        if m_q and m_a:
            return m_q.group(1).strip(), m_a.group(1).strip()
    except Exception as e:
        print("Trivia AI error:", e)
    return get_fallback_trivia(difficulty)

def start_trivia(asked_by, difficulty, topic):
    if TRIVIA_STATE["active"]:
        send_message("A trivia question is already active! Answer that one first.")
        return
    q, a = generate_trivia_qa(topic, difficulty)
    TRIVIA_STATE.update({
        "active": True,
        "question": q,
        "answer": a,
        "topic": topic or "general knowledge",
        "difficulty": difficulty if difficulty in TRIVIA_DIFFICULTIES else "medium",
        "asked_by": asked_by,
        "asked_ts": time.time(),
    })
    send_message(f"🎯 Trivia ({TRIVIA_STATE['difficulty']}): {q}")

def try_answer_trivia(user, text, force=False):
    if not TRIVIA_STATE["active"]:
        return False
    guess = (text or "").strip()
    if not guess or user.lower() in {(BOT_NICK or '').lower(), "streamelements", "nightbot", "moobot"}:
        return False
    if not force and not looks_like_guess(guess, TRIVIA_STATE["answer"]):
        return False
    if answers_match(guess, TRIVIA_STATE["answer"]):
        send_message(f"@{user} ✅ Correct! Answer: {TRIVIA_STATE['answer']}")
        TRIVIA_STATE["active"] = False
    else:
        send_message(f"@{user} ❌ Nope.")
    return True

def check_trivia_timeout():
    if TRIVIA_STATE["active"] and time.time() - TRIVIA_STATE["asked_ts"] > TRIVIA_TIMEOUT:
        send_message(f"⌛ Time! The answer was: {TRIVIA_STATE['answer']}")
        TRIVIA_STATE["active"] = False

# ====== NEW: SPONTANEOUS CHATTER (every 5 min max) ======

def get_recent_chat_context(max_lines=12):
    """Return (transcript_text, count) for chat in the last SPONT_ACTIVITY_WINDOW seconds."""
    now_ts = time.time()
    recent = [(u, m) for (ts, u, m) in CHAT_CONTEXT if now_ts - ts <= SPONT_ACTIVITY_WINDOW]
    tail = recent[-max_lines:]
    transcript = "\n".join(f"{u}: {m}" for (u, m) in tail)
    return transcript, len(recent)


# =====================================================
# RECALL HELPERS (last 50 messages + bot last line)
# =====================================================

def record_chat_line(user, text):
    """Keep recent non-command chat + per-user memories."""
    ts = time.time()
    msg = (text or "").strip()
    if not msg:
        return
    # Per-user memory (all)
    remember_event(user, "message", msg=msg)
    # Special users: full transcript
    add_full_user_log(user, msg)
    # Store context for spontaneous replies (skip bot & common bots and commands)
    if user.lower() in IGNORE_USERS:
        return
    if msg.startswith("!"):
        return
    if len(msg) > 500:
        msg = msg[:500]
    CHAT_CONTEXT.append((ts, user, msg))

def get_last_bot_line():
    if not BOT_SAID:
        return None
    return BOT_SAID[-1][1]

def recall_chat(n=10):
    """Return list of tuples (user, text) from recent chat."""
    n = max(1, min(int(n or 10), 50))
    items = list(CHAT_CONTEXT)[-n:]
    return [(u, m) for (ts, u, m) in items]

def get_recent_lines_by_user(user, n=5):
    """Find up to n recent lines from CHAT_CONTEXT for a given user."""
    lines = []
    for ts, u, m in reversed(CHAT_CONTEXT):
        if u.lower() == user.lower():
            lines.append((u, m))
            if len(lines) >= n:
                break
    if not lines:
        # Try special full log
        tail = get_full_user_tail(user, n)
        if tail:
            return [(user, msg) for _, msg in tail]
    return list(reversed(lines))

def send_transcript_lines(title, pairs):
    """Chunk transcripts so each message stays short enough for Twitch."""
    if not pairs:
        send_message(f"{title} (empty)")
        return
    chunk = []
    length = 0
    for i, (u, m) in enumerate(pairs, 1):
        piece = f"{i}) {u}: {m}"
        if length + len(piece) + 3 > 400:  # safe margin
            send_message(f"{title} " + " | ".join(chunk))
            chunk = [piece]
            length = len(piece)
        else:
            chunk.append(piece)
            length += len(piece) + 3
    if chunk:
        send_message(f"{title} " + " | ".join(chunk))

# =====================================================
# MAIN LISTEN LOOP
# =====================================================

# Ignore these users when collecting chat context
IGNORE_USERS = { (BOT_NICK or "").lower(), "streamelements", "nightbot", "moobot" }

def listen():
    buffer = ""
    while True:
        try:
            try:
                data = irc.recv(2048).decode("utf-8", errors="ignore")
            except socket.timeout:
                data = ""

            buffer += data

            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)

                if line.startswith("PING"):
                    irc.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                    continue

                parts = line.split(" ", 3)
                if len(parts) < 4 or not parts[3].startswith(":"):
                    continue

                username = parts[0].split("!")[0][1:]
                message = parts[3][1:]
                lower_msg = message.lower().strip()
                print(f"[{username}] {message}")

                # record chat + per-user memory
                record_chat_line(username, message)

                # ======== FIRST: if a trivia is active, check guesses (non-commands) ========
                if TRIVIA_STATE["active"] and not lower_msg.startswith("!"):
                    handled = try_answer_trivia(username, message, force=False)
                    if handled:
                        continue

                # ------------- COMMANDS ------------- #

                # Recall last N chat lines (!recall [n])
                if lower_msg.startswith("!recall"):
                    tokens = lower_msg.split()
                    n = 10
                    if len(tokens) >= 2 and tokens[1].isdigit():
                        n = int(tokens[1])
                    pairs = recall_chat(n)
                    send_transcript_lines(f"Recent ({min(n,50)}):", pairs)
                    continue

                # ======== NEW: !trivia [difficulty] [topic...] ========
                if lower_msg.startswith("!trivia"):
                    # Parse: optional first token is difficulty; remainder is topic
                    rest = message.split(" ", 1)[1].strip() if len(message.split(" ", 1)) == 2 else ""
                    diff = "medium"
                    topic = ""
                    if rest:
                        tokens = rest.split()
                        if tokens and tokens[0].lower() in TRIVIA_DIFFICULTIES:
                            diff = tokens[0].lower()
                            topic = " ".join(tokens[1:]).strip()
                        else:
                            topic = rest
                    start_trivia(username, diff, topic)
                    remember_event(username, "command", name="trivia")
                    continue

                # ======== NEW: explicit answers via !answer <guess> ========
                if lower_msg.startswith("!answer"):
                    if not TRIVIA_STATE["active"]:
                        send_message("No trivia question right now. Start one with !trivia")
                        continue
                    parts_ans = message.split(" ", 1)
                    if len(parts_ans) < 2 or not parts_ans[1].strip():
                        send_message("Usage: !answer <your guess>")
                        continue
                    try_answer_trivia(username, parts_ans[1].strip(), force=True)
                    continue

                # Timers (kept)
                if lower_msg.startswith("!timer"):
                    tokens = message.split(" ", 2)
                    if len(tokens) < 2:
                        send_message("Usage: !timer <dur> [name] e.g., !timer 5m tea")
                        continue
                    dur_s = parse_duration(tokens[1])
                    if dur_s <= 0:
                        send_message("Bad duration. Try 10s, 5m, 1h30m, or 1:30:00")
                        continue
                    name = tokens[2].strip() if len(tokens) >= 3 else f"{username}-timer"
                    if len(name) > 40:
                        name = name[:40]
                    _, end_ts = start_timer(username, dur_s, name)
                    send_message(f"⏱️ @{username} set '{name}' for {format_duration(dur_s)}.")
                    remember_event(username, "command", name="timer")
                    continue

                if lower_msg.startswith("!timeleft"):
                    parts2 = message.split(" ", 1)
                    if len(parts2) == 2 and parts2[1].strip():
                        name = parts2[1].strip()
                        remaining = time_left(username, name)
                        if remaining is None:
                            send_message(f"@{username} no timer named '{name}'.")
                        else:
                            send_message(f"@{username} {name}: {format_duration(remaining)} left.")
                    else:
                        items = list_user_timers(username)
                        if not items:
                            send_message(f"@{username} no active timers.")
                        else:
                            summary = ", ".join([f"{n}:{format_duration(t)}" for n, t in items[:3]])
                            send_message(f"@{username} {summary}")
                    remember_event(username, "command", name="timeleft")
                    continue

                if lower_msg == "!timers":
                    now_ts = time.time()
                    active = [(t["user"], t["name"], max(0, t["end"] - now_ts)) for t in timers.values()]
                    if not active:
                        send_message("No active timers.")
                    else:
                        active.sort(key=lambda x: x[2])
                        lines = [f"@{u}:{n} {format_duration(s)}" for u, n, s in active[:4]]
                        send_message(" | ".join(lines))
                    remember_event(username, "command", name="timers")
                    continue

                # Current schedule/time (kept AI)
                if lower_msg.startswith("!current"):
                    reply = generate_current_response(username)
                    if reply:
                        send_message(f"@{username} {reply}")
                    remember_event(username, "command", name="current")
                    continue

                # AI: Extra Life explainer
                if lower_msg.startswith("!extralife"):
                    reply = ai_extralife_response(username)
                    send_message(reply)
                    remember_event(username, "command", name="extralife")
                    continue

                # AI: Donate link + hype
                if lower_msg.startswith("!donate"):
                    reply = ai_donate_response(username, DONATE_URL)
                    send_message(reply)
                    remember_event(username, "command", name="donate")
                    continue

                # AI: Magic 8-ball (accepts optional question text)
                if lower_msg.startswith("!8ball"):
                    q = message.split(" ", 1)[1].strip() if len(message.split(" ", 1)) == 2 else ""
                    reply = ai_8ball_response(username, q)
                    send_message(f"@{username} 🎱 {reply}")
                    remember_event(username, "command", name="8ball")
                    continue

                # ======== !goon COMMAND ========
                if lower_msg.startswith("!goon"):
                    send_message(ai_goon_response(username))
                    continue

                    try:
                        response = client_ai.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are AmatsuAnima, a chaotic gremlin of Twitch chat."},
                                {"role": "user", "content": prompt},
                            ],
                            max_tokens=70,
                            temperature=1.0,
                        )
                        line = response.choices[0].message.content.strip()
                    except Exception as e:
                        print

                # AI: Roll NdM dice (defaults to d20)
                if lower_msg.startswith("!roll"):
                    arg = ""
                    parts_roll = message.split(" ", 1)
                    if len(parts_roll) == 2:
                        arg = parts_roll[1].strip().lower().replace(" ", "")
                    n, sides = 1, 20
                    m = re.match(r'^(\d*)d(\d+)$', arg) if arg else None
                    if m:
                        n = int(m.group(1)) if m.group(1) else 1
                        sides = int(m.group(2))
                        n = max(1, min(n, 20))
                        sides = max(2, min(sides, 1000))
                        rolls = [random.randint(1, sides) for _ in range(n)]
                        total = sum(rolls)
                        reply = ai_roll_many_response(username, n, sides, rolls, total)
                        send_message(reply)
                        remember_event(username, "command", name="roll", roll_desc=f"{n}d{sides} total={total}")
                    else:
                        result = random.randint(1, 20)
                        reply = ai_roll_response(username, 20, result)
                        send_message(reply)
                        remember_event(username, "command", name="roll", roll_desc=f"d20={result}")
                    continue
                # existing !satchfact command (kept)
                if lower_msg.startswith("!satchfact"):
                    fact = generate_satchfact()
                    send_message(f"@{username} {fact}")
                    remember_event(username, "command", name="satchfact")
                    continue

                # --------- Dynamic recall phrases (no command) ---------
                recall_triggers = [
                    "do you remember", "do u remember", "do you recall", "do u recall",
                    "what did you say", "what'd you say",
                    "what did you just say", "what'd you just say",
                    "what was that", "say that again", "repeat that"
                ]
                if any(p in lower_msg for p in recall_triggers):
                    if (
                        "what did you" in lower_msg
                        or "what'd you" in lower_msg
                        or "say that again" in lower_msg
                        or "repeat that" in lower_msg
                        or "what was that" in lower_msg
                    ):
                        last = get_last_bot_line()
                        if last:
                            send_message(f"@{username} I just said: {last}")
                        else:
                            send_message(f"@{username} I haven't said anything… yet 😈")
                    else:
                        recent_user_lines = get_recent_lines_by_user(username, n=3)
                        reply = ai_recall_user_context(username, recent_user_lines)
                        if reply:
                            send_message(f"@{username} {reply}")
                        else:
                            send_message(f"@{username} I remember you. Vividly. 🫣")
                    continue

                # ------------- AI REPLIES ------------- #
                if any(n in lower_msg for n in ("amatsu", "greggnog, anima, amatsuanima")):
                    prompt = f"{username} said: {message}"
                    mem_summary = get_user_memory_summary(username)
                    prompt += f"\n\nUser memory summary: {mem_summary}"
                    reply = generate_reply(prompt)
                    if reply:
                        send_message(f"@{username} {reply}")

            check_timers()
            check_trivia_timeout()

        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(1)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    try:
        listen()
    except KeyboardInterrupt:
        print("Amatsu manually disconnected.")
