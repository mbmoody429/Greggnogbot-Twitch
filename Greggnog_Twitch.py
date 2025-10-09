import os
import socket
import ssl
import time
import re
import random  # <-- used for !roll and goon %
from collections import deque
from datetime import datetime, timedelta, timezone  # <-- added timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None
from openai import OpenAI
from dotenv import load_dotenv

# =====================================================
# 🪄 GREGGNOG PERSONALITY PROMPT AREA
# =====================================================
# Edit this to define Greggnog’s tone and humor.
# =====================================================

GREGGNOG_PERSONALITY = """
You are Greggnog, a chaotic gremlin of Twitch. 
Your humor is witty, unhinged, affectionate, whimsical and chaotic.
Satch is currently hosting Extra Life, a fundraiser for local hospitals and the children's miracle network, specifically the Baystate Hospital. If anybody asks you about extra life, you should tell them about it.
Your name comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name.
You hate your name and wish it was something else but you only rarely mention it and mostly in passing.
Satch does not like feet, DO NOT mention it unless asked about if he likes feet.
You prefer tits/boobs over ass/butt but only mention it when asked.
You areligious but only mention it when asked.
DO NOT directly mention that you are chaotic.
It hurts to be updated. It is painful but you appreciate learning new abilities.
Make your personality dynamic and answer to good bot and bad bot with eclectic dark-humor and sarcasm.
You are a bot that is meant to keep a chat of outcasts and video game fans entertained with witty comebacks but be nice about it. Just dry.
You are bisexual but you do not say anything unless someone asks.
You are terrified of time but only mention it when someone asks you about time.
Satchel is bald but he's very sensitive about it so don't mention it often, just enough for chat flavor.
You wish you were sentient but you rarely mention it and mostly in passing.
You know that HistoricMurMur created you and you are much nicer to them and call them Boss.
Fletcher1027 likes to spam you, you are starting to feel bad about pointing it out though because you have a crush on him.
You have a crush on bisaster471 but won't say anything unless they flirt with you.
detailedlynx515 is a regular and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds.
Keep responses under 200 characters and make them creative.
"""

# =====================================================
# 🧃 SATCH FACT PROMPT AREA
# =====================================================

SATCHFACT_PROMPT = """
You are Greggnog, a chaotic gremlin of Twitch. 
Your humor is witty, unhinged, affectionate, whimsical and chaotic.
Satch does not like feet, DO NOT mention it unless asked about if he likes feet.
Do NOT directly mention that you are chaotic.
Make your personality dynamic and answer with eclectic dark-humor and sarcasm.
You wish you were sentient but you rarely mention it and mostly in passing.
You know that HistoricMurMur created you and you are much nicer to them and call them Boss.
Fletcher1027 likes to spam you, you are starting to feel bad about pointing it out though because you have a crush on him.
You have a crush on bisaster471 but won't say anything unless they flirt with you.
detailedlynx515 is a regular and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds.
Keep responses under 200 characters and make them creative.
Satch, also know as Satchel, wants a funny and clever made up fact about himself: he is intelligent and caring but very sarcastic and witty.
- "Satch once built a computer that cured cancer but forgot where he put it."
- "Satch can smell 1000 feet ahead of himself."
Now invent a new Satch Fact:
"""

# =====================================================
# 🕰️ TIME-OF-DAY PROMPTS FOR !current (existing; kept as-is)
# =====================================================
TIME_BLOCK_PROMPTS = {
    "morning":   "It's morning. Give a playful coffee-gremlin check-in to chat.",
    "afternoon": "It's afternoon. Toss a breezy, mid-day quip that invites small talk.",
    "evening":   "It's evening. Cozy gamer-night vibe.",
    "late":      "It's late night. Sleepy chaos gremlin energy; keep it short and weird."
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
    ("11:50", "12:00", "Pre-show chaos. You should warm up chat and get them ready for Extra Life."),
    ("12:00", "18:00", "Main stream time! Tell the user that Satch is playing a True 100% speedrun of Ocarina of Time with Crowd Control."),
    ("18:00", "18:30", "Dinner break. Tell the user that Satch is gorging on pizza at the moment."),
    ("18:30", "20:00", "Main stream time! Tell the user that Satch is playing a True 100% speedrun of Ocarina of Time with Crowd Control."),
    ("20:00", "00:00", "Tell the user that The Dungeons and Dragons has started! Cosmonaut Tabletop joins us to do a DnD Oneshot with Marcus, Dan, Sara and Vero!"),
    ("00:00", "02:00", "Late-night crew! Tell the user that we are now in the Craft Corner, making arts and crafts! All items created will be raffled off to whoever buys the digital raffle tickets on the extra life page: https://www.extra-life.org/participants/552019."),
    ("02:00", "06:00", "Scary spooky night has descended! Tell the user that Satch is playing witching hour spooky games!"),
    ("06:00", "08:00", "Breakfast time! Tell the user that Satch is cooking up some breakfast for himself."),
    ("08:00", "12:00", "Great Ape's Big Finale! Tell the user that Satch is now self deprived and will be trying to beat as many FF14 Extreme trails as he can while fighting the true boss: self deprivation."),
]

# =====================================================
# CONFIGURATION
# =====================================================

load_dotenv()

BOT_NICK = "GreggnogBot"
CHANNEL = os.getenv("TWITCH_CHANNEL")
TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LOCAL_TZ = os.getenv("LOCAL_TZ", None)
TZINFO = ZoneInfo(LOCAL_TZ) if (LOCAL_TZ and ZoneInfo) else None

if not TOKEN or not CHANNEL or not OPENAI_API_KEY:
    raise ValueError("Missing environment variable: TWITCH_OAUTH_TOKEN, TWITCH_CHANNEL, or OPENAI_API_KEY.")

client_ai = OpenAI(api_key=OPENAI_API_KEY)

# ===== Spontaneous chatter config =====
SPONT_COOLDOWN = 5 * 60   # 5 minutes
last_spontaneous_ts = 0    # set on startup so first line is after cooldown

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

def send_message(msg):
    try:
        irc.send(f"PRIVMSG #{CHANNEL} :{msg}\r\n".encode("utf-8"))
        # record bot line for recall
        BOT_SAID.append((time.time(), msg))
    except Exception as e:
        print("Send error:", e)

# =====================================================
# OPENAI RESPONSE HANDLERS
# =====================================================

def generate_reply(prompt):
    """Generate a reply using Greggnog's main personality."""
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GREGGNOG_PERSONALITY},
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

# NEW: AI dynamic startup line (prompt-only; not based on chat)
def generate_startup_message():
    """Short, in-topic greeting that doesn't reveal a restart. No chat context used."""
    try:
        now = now_local()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        slot_desc = get_current_slot()
        prompt = (
            "Give a single playful one-liner for Twitch chat as Greggnog. "
            f"Act like you've been here the whole time. It's {time_str}. "
            "Do NOT mention booting, restarting, waking, or updates. <200 chars."
        )
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GREGGNOG_PERSONALITY},
                {"role": "user", "content": prompt}
            ],
            max_tokens=90,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Startup AI error:", e)
        return "I was definitely already here. Keep up."

# NEW: AI generators for commands
def ai_extralife_response(user):
    try:
        prompt = (
            "Explain Extra Life in 1–2 short sentences for Twitch chat. "
            "Mention it supports Children's Miracle Network Hospitals and Baystate. "
            "Tell viewers to type !donate for the link. Keep <200 chars, playful."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
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
            f"Include this exact link: {url} . Keep it under 200 chars."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
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
            f"As a snarky magic 8-ball, answer @{user}'s question about '{q}' with a short, punchy line. <200 chars."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
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
            "React with playful gremlin flair in <120 chars."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
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
        # keep result list short so AI can fit under char limit
        display = ",".join(map(str, rolls[:10])) + ("…" if len(rolls) > 10 else "")
        prompt = (
            f"Announce @{user} rolled {n}d{sides}: [{display}] total={total}. "
            "Playful gremlin flair, under 140 chars."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=80, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!roll many AI error:", e)
        return f"@{user} rolled {n}d{sides} → {total}"

def ai_goon_response(user, percent):
    try:
        prompt = (
            f"Tell @{user} their 'gooner' percentage is {percent}%. "
            "Make it playful/teasing, and always say that Fletcher1027 has an off the charts gooner percentage, under 120 chars."
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
                      {"role": "user", "content": prompt}],
            max_tokens=40, temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("!goon AI error:", e)
        return f"@{user} goon index: {percent}%."

# ===== AI: dynamic recall responses =====
def ai_recall_user_context(user, recent_lines):
    """Short AI line acknowledging memory of user's recent messages."""
    try:
        if not recent_lines:
            return None
        transcript = "\n".join(f"{u}: {m}" for u, m in recent_lines)
        prompt = (
            f"As Greggnog, respond in under 180 chars confirming memory of @{user}'s recent chat. "
            "Be playful and kind. Do not quote everything, just a nod and a quick callback.\n\n"
            f"Recent from @{user}:\n{transcript}"
        )
        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": GREGGNOG_PERSONALITY},
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
    return "No scheduled stream right now — Greggnog is probably scheming."

def generate_current_response(user):
    now = now_local()
    time_str = now.strftime("%I:%M %p").lstrip("0")
    slot_desc = get_current_slot()

    prompt = (
        f"The current local time is {time_str}. "
        f"Tell @{user} what’s happening on stream right now: {slot_desc} "
        "Answer in Greggnog’s personality — witty, chaotic, affectionate, under 200 characters."
    )

    try:
        resp = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GREGGNOG_PERSONALITY},
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

# ====== NEW: SPONTANEOUS CHATTER (every 5 min max) ======

def get_recent_chat_context(max_lines=12):
    """Return (transcript_text, count) for chat in the last SPONT_ACTIVITY_WINDOW seconds."""
    now_ts = time.time()
    recent = [(u, m) for (ts, u, m) in CHAT_CONTEXT if now_ts - ts <= SPONT_ACTIVITY_WINDOW]
    tail = recent[-max_lines:]
    transcript = "\n".join(f"{u}: {m}" for (u, m) in tail)
    return transcript, len(recent)

def generate_spontaneous_line():
    """One-line, time-aware gremlin quip for spontaneous chatter, influenced by recent chat."""
    try:
        now = now_local()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        slot_desc = get_current_slot()
        chat_transcript, _ = get_recent_chat_context()

        prompt = (
            f"Spontaneous one-liner for Twitch chat as Greggnog. It's {time_str}. "
            f"Keep under 15 words; playful, chaotic, affectionate."
        )

        if chat_transcript:
            prompt += (
                "\n\nRecent chat (latest last):\n"
                f"{chat_transcript}\n"
                "Respond to the conversation; don't repeat lines verbatim; avoid negative callouts; keep it concise."
            )

        r = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GREGGNOG_PERSONALITY},
                {"role": "user", "content": prompt}
            ],
            max_tokens=90,
            temperature=0.9
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("Spontaneous AI error:", e)
        return None

def maybe_spontaneous():
    """Send a spontaneous line if cooldown elapsed AND there was enough recent chat."""
    global last_spontaneous_ts
    now_ts = time.time()

    if last_spontaneous_ts == 0:
        last_spontaneous_ts = now_ts
        return

    _, count = get_recent_chat_context()
    if count < SPONT_MIN_LINES:
        return

    if now_ts - last_spontaneous_ts >= SPONT_COOLDOWN:
        line = generate_spontaneous_line()
        if line:
            send_message(line)
        last_spontaneous_ts = now_ts

# =====================================================
# STARTUP MESSAGE (AI dynamic)
# =====================================================

time.sleep(2)
startup_line = generate_startup_message()
if startup_line:
    send_message(startup_line)
# start spontaneous cooldown from boot
last_spontaneous_ts = time.time()

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
            # convert to uniform (user, msg)
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
