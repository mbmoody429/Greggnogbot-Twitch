import os
import socket
import ssl
import time
from openai import OpenAI
from dotenv import load_dotenv

# =====================================================
# 🪄 GREGGNOG PERSONALITY PROMPT AREA
# =====================================================
# Edit this to train Greggnog’s tone and humor.
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
# You can edit this to change how she invents Satch Facts.
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
# CONFIGURATION
# =====================================================

load_dotenv()

BOT_NICK = "GreggnogBot"
CHANNEL = os.getenv("TWITCH_CHANNEL")
TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TOKEN or not CHANNEL or not OPENAI_API_KEY:
    raise ValueError("Missing environment variable: TWITCH_OAUTH_TOKEN, TWITCH_CHANNEL, or OPENAI_API_KEY.")

client_ai = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================
# CONNECT TO TWITCH
# =====================================================

server = "irc.chat.twitch.tv"
port = 6697
irc = ssl.wrap_socket(socket.socket())
irc.connect((server, port))

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
send_message("Greggnog is here. Be very scared. Just kidding hehe")

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
        # Ensure it starts with "Satch" for style consistency
        if not fact.lower().startswith("satch"):
            fact = "Satch " + fact[0].lower() + fact[1:]
        return fact
    except Exception as e:
        print("SatchFact error:", e)
        return "Satch once tried to debug a sandwich."

# =====================================================
# MAIN LISTEN LOOP
# =====================================================

def listen():
    buffer = ""
    while True:
        try:
            data = irc.recv(2048).decode("utf-8", errors="ignore")
            buffer += data

            # Respond to Twitch pings
            if data.startswith("PING"):
                irc.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                continue

            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                parts = line.split(" ", 3)

                if len(parts) < 4 or not parts[3].startswith(":"):
                    continue

                username = parts[0].split("!")[0][1:]
                message = parts[3][1:]

                print(f"[{username}] {message}")
                lower_msg = message.lower()

                # ------------- COMMANDS ------------- #
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

        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(5)

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    try:
        listen()
    except KeyboardInterrupt:
        print("Greggnog manually disconnected.")
