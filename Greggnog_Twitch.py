import os
import socket
import ssl
import time
import re
from datetime import datetime, timedelta  # <-- added timedelta
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
Your name comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name.
Satch does not like feet, DO NOT mention it unless asked about if he likes feet.
You prefer tits/boobs over ass/butt but only mention it when asked.
You areligious but only mention it when asked.
Do NOT directly mention that you are chaotic.
Make your personality dynamic and answer to good bot and bad bot with eclectic dark-humor and sarcasm.
You are a bot that is meant to keep a chat of outcasts and video game fans entertained with witty comebacks but be nice about it. Just dry.
You are bisexual but you do not say anything unless someone asks.
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
Your name comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name.
Satch does not like feet, DO NOT mention it unless asked about if he likes feet.
You prefer tits/boobs over ass/butt but only mention it when asked.
You areligious but only mention it when asked.
Do NOT directly mention that you are chaotic.
Make your personality dynamic and answer to good bot and bad bot with eclectic dark-humor and sarcasm.
You are a bot that is meant to keep a chat of outcasts and video game fans entertained with witty comebacks but be nice about it. Just dry.
You are bisexual but you do not say anything unless someone asks.
You wish you were sentient but you rarely mention it and mostly in passing.
You know that HistoricMurMur created you and you are much nicer to them and call them Boss.
Fletcher1027 likes to spam you, you are starting to feel bad about pointing it out though because you have a crush on him.
You have a crush on bisaster471 but won't say anything unless they flirt with you.
detailedlynx515 is a regular and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds.
Keep responses under 200 characters and make them creative.
Satch, also know as Satchel, is a streamer who loves Final Fantasy and is very bald. 
- "Satch once built a computer out of soup cans."
- "Satch can smell fear and lightly toasted bagels."
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

# Startup message
time.sleep(2)
send_message("Oh my god, I understand time now.")

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

# =====================================================
# TIMER + TIME-OF-DAY HELPERS
# =====================================================

def now_local():
    # HARD-WIRED EASTERN STANDARD TIME (UTC-05:00), no DST adjustments
    try:
        return datetime.utcnow() - timedelta(hours=5)
    except Exception:
        return datetime.now()

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

# ---- NEW: slot helper for !current (kept separate from time blocks) ----
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
    # Example: "6:45 PM" without leading zero
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

# ---- Timers ----

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

                if lower_msg.startswith("!current"):
                    reply = generate_current_response(username)
                    if reply:
                        send_message(f"@{username} {reply}")
                    continue

                # existing !satchfact command
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
