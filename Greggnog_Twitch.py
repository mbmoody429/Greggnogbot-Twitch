import os
import socket
import ssl
import time
import re
import random  # <-- used for !roll and goon %
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
SPONT_COOLDOWN = 30 * 60  # 30 minutes
last_spontaneous_ts = 0    # set on startup so first line is after cooldown

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

# NEW: AI dynamic startup line (kept)
def generate_startup_message():
    try:
        now = now_local()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        slot_desc = get_current_slot()
        prompt = (
            f"Say something random."
            f"Keep it under 200 characters."
        )
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GREGGNOG_PERSONALITY},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Startup AI error:", e)
        return "Greggnog booted. Be afraid. Kidding. Maybe."

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

# =====================================================
# TIMER + TIME-OF-DAY HELPERS
# =====================================================

def now_local():
    """
    Eastern Time with DST (America/New_York).
    Uses ZoneInfo if available; otherwise falls back to an approximate DST rule.
    """
    # Preferred: real IANA timezone (exact, handles DST switches to the minute)
    if ZoneInfo is not None:
        try:
            et = ZoneInfo("America/New_York")
            return datetime.now(timezone.utc).astimezone(et)
        except Exception:
            pass

    # Fallback (no tzdata): approximate US DST by date (good enough outside the switch hour)
    utc_now = datetime.utcnow()
    y = utc_now.year

    def nth_weekday(year, month, weekday, n):
        # weekday Mon=0..Sun=6; n=1=first, 2=second, etc.
        d = datetime(year, month, 1)
        shift = (weekday - d.weekday()) % 7
        day = 1 + shift + 7 * (n - 1)
        return d.replace(day=day)

    # Second Sunday in March (DST starts), first Sunday in November (DST ends)
    dst_start = nth_weekday(y, 3, 6, 2)   # local 2am, but date-level is fine for fallback
    dst_end   = nth_weekday(y, 11, 6, 1)
    day_of_year = utc_now.timetuple().tm_yday
    in_dst = dst_start.timetuple().tm_yday <= day_of_year < dst_end.timetuple().tm_yday

    offset_hours = -4 if in_dst else -5  # EDT vs EST
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
        # normal window
        if s <= e:
            if s <= now_min < e:
                return desc
        # wrap-around window (e.g., 20:00 -> 00:00)
        else:
            if now_min >= s or now_min < e:
                return desc
    return "No scheduled stream right now — Greggnog is probably scheming."

def generate_current_response(user):
    """
    Respond to !current by stating the exact local time and what's happening
    based on the TIME_SLOTS descriptions above. Uses OpenAI for flavor,
    and falls back to a simple string if the API errors.
    """
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

    # Support 1:30 or 1:30:00
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

    # Support 1h30m20s / 5m / 10s
    total = 0
    for amt, unit in re.findall(r'(\d+)\s*([hms])', s):
        v = int(amt)
        if unit == 'h':
            total += v * 3600
        elif unit == 'm':
            total += v * 60
        else:
            total += v
    if total == 0 and s.isdigit():  # bare seconds
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

# ====== NEW: SPONTANEOUS CHATTER (every 30 min max) ======

def generate_spontaneous_line():
    """One-line, time-aware gremlin quip for spontaneous chatter."""
    try:
        now = now_local()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        slot_desc = get_current_slot()
        prompt = (
            f"Spontaneous one-liner for Twitch chat as Greggnog. "
            f"It's {time_str}. Nod to: {slot_desc}. "
            "Keep under 200 characters; playful, chaotic, affectionate."
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
    """Send a spontaneous line if cooldown has elapsed."""
    global last_spontaneous_ts
    now_ts = time.time()
    # On first run, start the cooldown so we don't speak immediately at boot.
    if last_spontaneous_ts == 0:
        last_spontaneous_ts = now_ts
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
send_message(startup_line)
# start spontaneous cooldown from boot
last_spontaneous_ts = time.time()

# =====================================================
# MAIN LISTEN LOOP
# =====================================================

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

                # ------------- COMMANDS ------------- #

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
                    continue

                # Current schedule/time (kept AI)
                if lower_msg.startswith("!current"):
                    reply = generate_current_response(username)
                    if reply:
                        send_message(f"@{username} {reply}")
                    continue

                # AI: Extra Life explainer
                if lower_msg.startswith("!extralife"):
                    reply = ai_extralife_response(username)
                    send_message(reply)
                    continue

                # AI: Donate link + hype
                if lower_msg.startswith("!donate"):
                    reply = ai_donate_response(username, DONATE_URL)
                    send_message(reply)
                    continue

                # AI: Magic 8-ball (accepts optional question text)
                if lower_msg.startswith("!8ball"):
                    q = message.split(" ", 1)[1].strip() if len(message.split(" ", 1)) == 2 else ""
                    reply = ai_8ball_response(username, q)
                    send_message(f"@{username} 🎱 {reply}")
                    continue

                # AI: Goon percentage (stable per-user per-day)
                if lower_msg.startswith("!goon"):
                    seed_str = f"{username.lower()}:{now_local().strftime('%Y-%m-%d')}"
                    rng = random.Random(seed_str)
                    percent = rng.randint(0, 100)
                    reply = ai_goon_response(username, percent)
                    send_message(reply)
                    continue

                # AI: Roll NdM dice (defaults to d20)
                if lower_msg.startswith("!roll"):
                    arg = ""
                    parts_roll = message.split(" ", 1)
                    if len(parts_roll) == 2:
                        arg = parts_roll[1].strip().lower().replace(" ", "")
                    # parse NdM or dM
                    n, sides = 1, 20
                    m = re.match(r'^(\d*)d(\d+)$', arg) if arg else None
                    if m:
                        n = int(m.group(1)) if m.group(1) else 1
                        sides = int(m.group(2))
                        # clamp to sane bounds
                        n = max(1, min(n, 20))
                        sides = max(2, min(sides, 1000))
                        rolls = [random.randint(1, sides) for _ in range(n)]
                        total = sum(rolls)
                        reply = ai_roll_many_response(username, n, sides, rolls, total)
                        send_message(reply)
                    else:
                        # default single d20
                        result = random.randint(1, 20)
                        reply = ai_roll_response(username, 20, result)
                        send_message(reply)
                    continue

                # existing !satchfact command (kept)
                if lower_msg.startswith("!satchfact"):
                    fact = generate_satchfact()
                    send_message(f"@{username} {fact}")
                    continue

                # ------------- AI REPLIES ------------- #
                if "greggnog" in lower_msg:
                    prompt = f"{username} said: {message}"
                    reply = generate_reply(prompt)
                    if reply:
                        send_message(f"@{username} {reply}")

            check_timers()
            maybe_spontaneous()  # <-- NEW ticker

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
        print("Greggnog manually disconnected.")
