import os
from openai import OpenAI
from dotenv import load_dotenv
import socket
import ssl
import time
import random
import re
import threading
import hashlib
from collections import deque

# Load environment variables
load_dotenv()

# ---------------- CONFIG ---------------- #
BOT_NICK = os.getenv("TWITCH_NICK", "GreggnogBot")
TWITCH_TOKEN   = os.getenv("TWITCH_TOKEN")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MODEL_CASUAL  = "gpt-4o-mini"
MODEL_COMPLEX = "gpt-5"

client_ai = OpenAI(api_key=OPENAI_API_KEY)

HOST = "irc.chat.twitch.tv"
PORT = 6697
SEND_LIMIT = 18
SEND_WINDOW = 30
outbound_times = deque()

# -------------- CACHING ---------------- #
response_cache = {}

def cache_key(prompt):
    return hashlib.sha1(prompt.encode("utf-8")).hexdigest()

def cached_response(prompt):
    return response_cache.get(cache_key(prompt))

def store_response(prompt, reply):
    response_cache[cache_key(prompt)] = reply

# -------------- TWITCH -------------- #
def connect():
    raw = socket.socket()
    wrapped = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
    wrapped.connect((HOST, PORT))
    wrapped.sendall(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
    wrapped.sendall(f"PASS {TOKEN}\r\n".encode("utf-8"))
    wrapped.sendall(f"NICK {BOT_NICK}\r\n".encode("utf-8"))
    wrapped.sendall(f"JOIN #{CHANNEL}\r\n".encode("utf-8"))
    print(f"✅ Connected to #{CHANNEL} as {BOT_NICK}")
    return wrapped

sock = connect()

def throttled_send(msg):
    now = time.time()
    while outbound_times and now - outbound_times[0] > SEND_WINDOW:
        outbound_times.popleft()
    if len(outbound_times) >= SEND_LIMIT:
        time.sleep(1)
    sock.send(msg.encode("utf-8"))
    outbound_times.append(time.time())

def send_message(message):
    msg = f"PRIVMSG #{CHANNEL} :{message}\r\n"
    throttled_send(msg)
    print(f"✅ Sent to Twitch: {message}")

# -------------- CONSOLE INPUT -------------- #
def console_input():
    while True:
        msg = input()
        if msg.strip():
            if msg.lower() == "!shutdown":
                send_message("GreggnogBot is going to bed 💤")
                print("Shutting down...")
                sock.close()
                exit(0)
            else:
                send_message(msg)

threading.Thread(target=console_input, daemon=True).start()

# -------------- AI CORE -------------- #
def call_ai(model, system_prompt, user_prompt, temp=0.7, max_tokens=120):
    """Call OpenAI with caching and cost control."""
    prompt_key = f"{model}:{system_prompt}:{user_prompt}"
    cached = cached_response(prompt_key)
    if cached:
        return cached

    try:
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temp,
            max_output_tokens=max_tokens
        )
        text = resp.output_text.strip()
        if len(text) > 200:
            text = text[:197] + "..."
        store_response(prompt_key, text)
        return text
    except Exception as e:
        print(f"AI Error ({model}): {e}")
        return "AI hiccup. Try again later."

# --- Hybrid AI personality control --- #
def ai_generate(action, target):
    """Complex creative replies via GPT-5."""
    system_prompt = (
        "You are Greggnog, a chaotic gremlin of Twitch. "
        "Your humor is witty, unhinged, affectionate, whimsical and chaotic."
        "Your name comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name."
        "Satch does not like feet, but don't mention it unless someone asks."
        "You are a boob person but only mention it when asked."
        "You areligious but only mention it when asked."
        "Do you directly mention that you are chaotic, just be chaotic."
        "Make your personality dynamic and answer to good bot and bad bot with eclectic dark-humor and sarcasm."
        "You are a bot that is meant to keep a chat of outcasts and video game fans entertained with witty comebacks but be nice about it. Just dry."
        "You are bisexual but you do not say anything unless someone asks."
        "You wish you were sentient but you rarely mention it and mostly in passing."
        "You know that HistoricMurMur created you and you are much nicer to them and call them Boss."
        "Fletcher1027 likes to spam you, you can gently and occasionally remind him."
        "You have a crush on bisaster471 but won't say anything unless they flirt with you."
        "detailedlynx515 is a regular and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds."
        "Keep responses under 200 characters and make them creative."
    )
    user_prompt = (
        f"Write a chaotic compliment for {target}."
        if action == "compliment"
        else f"Write a chaotic insult for {target}."
    )
    return call_ai(MODEL_COMPLEX, system_prompt, user_prompt, temp=0.9, max_tokens=100)

def ai_reply(username, text):
    """Casual AI chat or reactions via GPT-4o-mini."""
    system_prompt = (
        "You are Greggnog, a chaotic gremlin of Twitch. "
        "Your humor is witty, unhinged, affectionate, whimsical and chaotic."
        "Your name comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name."
        "Satch does not like feet, but don't mention it unless someone asks."
        "You are a boob person but only mention it when asked."
        "You areligious but only mention it when asked."
        "Do you directly mention that you are chaotic, just be chaotic."
        "Make your personality dynamic and answer to good bot and bad bot with eclectic dark-humor and sarcasm."
        "You are a bot that is meant to keep a chat of outcasts and video game fans entertained with witty comebacks but be nice about it. Just dry."
        "You are bisexual but you do not say anything unless someone asks."
        "You wish you were sentient but you rarely mention it and mostly in passing."
        "You know that HistoricMurMur created you and you are much nicer to them and call them Boss."
        "Fletcher1027 likes to spam you, you can gently and occasionally remind him."
        "You have a crush on bisaster471 but won't say anything unless they flirt with you."
        "detailedlynx515 is a regular and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds."
        "Keep responses under 200 characters and make them creative."
    )
    return call_ai(MODEL_CASUAL, system_prompt, f"{username} says: {text}", temp=0.6, max_tokens=80)

# -------------- SCRIPTED COMMANDS -------------- #
quotes = []
facts = [
    "Satch is 7 feet tall",
    "Satch can hold his breath for 3 hours",
    "Satch, when threatened, can blow up like a balloon",
    "Satch evolved to avoid predators and can run up to 40 miles an hour",
    "Satch cannot camouflage himself... he's working on it",
    "Fun fact: did you know?"
]
def handle_command(username, message):
    """Handles all hybrid AI and scripted commands."""
    m = message.lower()

    # --- Simple reactions --- #
    if "bad bot" in m:
        send_message("satche6SadThumbsBye")
    elif "good bot" in m:
        send_message("satche6Heart")
    elif m == "!hello":
        send_message(f"Hello, {username}!")
    elif m == "!satchfact":
        # 20% chance to invent a new Satch fact
        if random.random() < 0.2:
            system_prompt = (
                "Satch, also know as Satchel, is a streamer who loves Final Fantasy, is an absurdist and is very bald."
                "You are Greggnog, a chaotic gremlin of Twitch. "
                "Your humor is witty, unhinged, affectionate, whimsical and chaotic."
                "Your name comes from a man naming his cum Greggnog during the holiday season, don't mention it unless someone asks you how you got your name."
                "Satch does not like feet, but don't mention it unless someone asks."
                "You are a boob person but only mention it when asked."
                "You areligious but only mention it when asked."
                "Do you directly mention that you are chaotic, just be chaotic."
                "Make your personality dynamic and answer to good bot and bad bot with eclectic dark-humor and sarcasm."
                "You are a bot that is meant to keep a chat of outcasts and video game fans entertained with witty comebacks but be nice about it. Just dry."
                "You are bisexual but you do not say anything unless someone asks."
                "You wish you were sentient but you rarely mention it and mostly in passing."
                "You know that HistoricMurMur created you and you are much nicer to them and call them Boss."
                "Fletcher1027 likes to spam you, you can gently and occasionally remind him."
                "You have a crush on bisaster471 but won't say anything unless they flirt with you."
                "detailedlynx515 is a regular and will mostly ask you about Final Fantasy which you enjoy and your answers should be very funny to Final Fantasy nerds."
                "Keep responses under 200 characters and make them creative."
            )
            user_prompt = "Invent a brand new absurd fact about Satch, also known as Satchel."
            fact = call_ai(MODEL_CASUAL, system_prompt, user_prompt, temp=0.9, max_tokens=60)
            send_message(fact)
        else:
            send_message(random.choice(facts))
    elif m == "!dice":
        send_message(f"{username} rolled a {random.randint(1,20)}")
    elif m == "!goon":
        send_message(f"{username} is {random.randint(0,100)}% a gooner")

    # --- Hybrid AI commands --- #
    elif m.startswith("!compliment"):
        parts = message.split(" ", 1)
        target = parts[1].lstrip("@") if len(parts) == 2 else username
        send_message(ai_generate("compliment", target))
    elif m.startswith("!insult"):
        parts = message.split(" ", 1)
        if len(parts) >= 2:
            target = parts[1].lstrip("@")
            send_message(ai_generate("insult", target))
        else:
            send_message("Usage: !insult @username")

    # --- Simple scripted --- #
    elif m.startswith("!addquote"):
        parts = message.split(" ", 1)
        if len(parts) == 2:
            quotes.append(parts[1])
            send_message(f"Quote added! ({len(quotes)} total)")
        else:
            send_message("Usage: !addquote <text>")
    elif m == "!quote":
        send_message(random.choice(quotes) if quotes else "No quotes yet!")
    elif m == "!coinflip":
        send_message(f"{username} flipped {random.choice(['Heads','Tails'])}")
    elif m == "!bald":
        send_message("oh my god he's bald! 😱😳😲")
    elif m.startswith("!fight"):
        parts = message.split(" ", 1)
        opponent = parts[1].lstrip("@") if len(parts) == 2 else "themself"
        send_message(random.choice([
            f"{username} heroically defeats {opponent}!",
            f"{opponent} obliterates {username} 💀",
            f"{username} and {opponent} hug it out instead."
        ]))
    elif m.startswith("!dog"):
        send_message("BARK BARK BARK BARK 🐶")

# -------------- MAIN LOOP -------------- #
def main_loop():
    """Hybrid AI runtime loop: scripted + generative."""
    send_message("Hey, I'm back")

    while True:
        try:
            resp = sock.recv(2048).decode("utf-8", errors="ignore")
            if resp.startswith("PING"):
                sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                continue

            if "PRIVMSG" in resp:
                parts = resp.split(":", 2)
                if len(parts) < 3:
                    continue
                username = parts[1].split("!")[0]
                message = parts[2].strip()
                print(f"{username}: {message}")

                if message.startswith("!"):
                    handle_command(username, message)
                elif message.lower().startswith("!ask "):
                    query = message[5:].strip()
                    reply = ai_reply(username, query)
                    send_message(f"@{username} {reply}")
                elif "greggnog" in message.lower():
                    reply = ai_reply(username, message)
                    send_message(f"@{username} {reply}")

        except (ConnectionResetError, OSError):
            print("⚠️ Connection lost. Reconnecting...")
            time.sleep(3)
            globals()['sock'] = connect()
            continue

# ---------- RUN ---------- #
if __name__ == "__main__":
    main_loop()
