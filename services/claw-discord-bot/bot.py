import os
import asyncio
import logging

import aiohttp
import discord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("claw-discord-bot")

DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:18789")
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

ALLOWED_USERS = frozenset({139476150786195456})
DISCORD_MAX_LEN = 2000

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def is_allowed(message: discord.Message) -> bool:
    return message.author.id in ALLOWED_USERS


def should_respond(message: discord.Message) -> bool:
    if message.author.bot:
        return False
    if not is_allowed(message):
        return False
    if isinstance(message.channel, discord.DMChannel):
        return True
    if client.user and client.user.mentioned_in(message):
        return True
    return False


def extract_content(message: discord.Message) -> str:
    content = message.content
    if client.user:
        content = content.replace(f"<@{client.user.id}>", "").replace(f"<@!{client.user.id}>", "")
    return content.strip()


def split_message(text: str) -> list[str]:
    if len(text) <= DISCORD_MAX_LEN:
        return [text]
    chunks = []
    while text:
        if len(text) <= DISCORD_MAX_LEN:
            chunks.append(text)
            break
        # Try to split at last newline within limit
        cut = text.rfind("\n", 0, DISCORD_MAX_LEN)
        if cut == -1:
            cut = DISCORD_MAX_LEN
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def query_gateway(content: str, user_id: str) -> str:
    headers = {"Content-Type": "application/json"}
    if GATEWAY_TOKEN:
        headers["Authorization"] = f"Bearer {GATEWAY_TOKEN}"

    payload = {
        "model": "openclaw/default",
        "messages": [{"role": "user", "content": content}],
        "user": user_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{GATEWAY_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                log.error("Gateway returned %d: %s", resp.status, body[:500])
                return f"Gateway error (HTTP {resp.status})"
            data = await resp.json()
            choices = data.get("choices", [])
            if not choices:
                return "No response from gateway."
            return choices[0].get("message", {}).get("content", "")


@client.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", client.user, client.user.id)


@client.event
async def on_message(message: discord.Message):
    if not should_respond(message):
        return

    content = extract_content(message)
    if not content:
        return

    async with message.channel.typing():
        try:
            reply = await query_gateway(content, str(message.author.id))
        except asyncio.TimeoutError:
            reply = "Gateway timed out."
        except Exception:
            log.exception("Gateway request failed")
            reply = "Failed to reach the gateway."

    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)


def main():
    client.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
