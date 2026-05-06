from __future__ import annotations

import os
import asyncio
import base64
import json
import logging
from collections import defaultdict, deque
from typing import Optional

import aiohttp
import discord
from discord import app_commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("claw-discord-bot")

DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:18789")
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")
MODEL = os.environ.get("OPENCLAW_MODEL", "openclaw/default")
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "20"))

ALLOWED_USERS = frozenset({139476150786195456})
DISCORD_MAX_LEN = 2000
IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})

intents = discord.Intents.default()
intents.message_content = True


class ClawBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.histories: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
        self.system_prompts: dict[str, str] = {}
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        await self.tree.sync()
        log.info("Slash commands synced")

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()


bot = ClawBot()


def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def session_key(user_id: int, channel_id: int) -> str:
    return f"{user_id}-{channel_id}"


async def download_image_as_data_url(url: str, content_type: str) -> str:
    async with bot.http_session.get(url) as resp:
        if resp.status != 200:
            return None
        data = await resp.read()
    b64 = base64.b64encode(data).decode()
    mime = content_type.split(";")[0].strip()
    return f"data:{mime};base64,{b64}"


def build_content(text: str, image_urls: list[str]) -> str | list:
    if not image_urls:
        return text
    parts = []
    if text:
        parts.append({"type": "text", "text": text})
    for url in image_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


async def extract_images(message: discord.Message) -> list[str]:
    urls = []
    for att in message.attachments:
        if att.content_type and att.content_type.split(";")[0].strip() in IMAGE_MIMES:
            data_url = await download_image_as_data_url(att.url, att.content_type)
            if data_url:
                urls.append(data_url)
    return urls


def split_message(text: str) -> list[str]:
    if len(text) <= DISCORD_MAX_LEN:
        return [text]
    chunks = []
    while text:
        if len(text) <= DISCORD_MAX_LEN:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, DISCORD_MAX_LEN)
        if cut == -1:
            cut = DISCORD_MAX_LEN
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def query_gateway_stream(messages: list[dict], user_id: str) -> str:
    headers = {"Content-Type": "application/json"}
    if GATEWAY_TOKEN:
        headers["Authorization"] = f"Bearer {GATEWAY_TOKEN}"

    payload = {
        "model": MODEL,
        "messages": messages,
        "user": user_id,
        "stream": True,
    }

    full_response = []
    async with bot.http_session.post(
        f"{GATEWAY_URL}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=180),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            log.error("Gateway returned %d: %s", resp.status, body[:500])
            return f"Gateway error (HTTP {resp.status})"

        async for line in resp.content:
            line = line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_response.append(content)
            except Exception:
                continue

    return "".join(full_response) or "No response from gateway."


async def handle_query(
    text: str,
    user_id: int,
    channel_id: int,
    image_urls: list[str] | None = None,
) -> str:
    key = session_key(user_id, channel_id)
    content = build_content(text, image_urls or [])
    user_msg = {"role": "user", "content": content}
    bot.histories[key].append(user_msg)

    messages = []
    if key in bot.system_prompts:
        messages.append({"role": "system", "content": bot.system_prompts[key]})
    messages.extend(bot.histories[key])

    reply = await query_gateway_stream(messages, str(user_id))
    bot.histories[key].append({"role": "assistant", "content": reply})
    return reply


# --- Slash commands ---

@bot.tree.command(name="ask", description="Ask the AI a question (with optional image)")
@app_commands.describe(
    prompt="Your question or message",
    image="An image to analyze (optional)",
)
async def cmd_ask(
    interaction: discord.Interaction,
    prompt: str,
    image: Optional[discord.Attachment] = None,
):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return

    await interaction.response.defer()

    image_urls = []
    if image and image.content_type and image.content_type.split(";")[0].strip() in IMAGE_MIMES:
        data_url = await download_image_as_data_url(image.url, image.content_type)
        if data_url:
            image_urls.append(data_url)

    try:
        reply = await handle_query(prompt, interaction.user.id, interaction.channel_id, image_urls)
    except asyncio.TimeoutError:
        reply = "Gateway timed out."
    except Exception:
        log.exception("Gateway request failed")
        reply = "Failed to reach the gateway."

    for i, chunk in enumerate(split_message(reply)):
        if i == 0:
            await interaction.followup.send(chunk)
        else:
            await interaction.followup.send(chunk)


@bot.tree.command(name="clear", description="Clear conversation history")
async def cmd_clear(interaction: discord.Interaction):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return
    key = session_key(interaction.user.id, interaction.channel_id)
    bot.histories[key].clear()
    await interaction.response.send_message("Conversation cleared.", ephemeral=True)


@bot.tree.command(name="system", description="Set a system prompt for this channel")
@app_commands.describe(prompt="System prompt text (leave empty to clear)")
async def cmd_system(interaction: discord.Interaction, prompt: str = ""):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return
    key = session_key(interaction.user.id, interaction.channel_id)
    if prompt:
        bot.system_prompts[key] = prompt
        await interaction.response.send_message(f"System prompt set.", ephemeral=True)
    else:
        bot.system_prompts.pop(key, None)
        await interaction.response.send_message("System prompt cleared.", ephemeral=True)


@bot.tree.command(name="model", description="Show or change the current model")
@app_commands.describe(name="Model name (e.g. openclaw/default, openai-codex/gpt-5.5)")
async def cmd_model(interaction: discord.Interaction, name: str = ""):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return
    global MODEL
    if name:
        MODEL = name
        await interaction.response.send_message(f"Model set to `{MODEL}`.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Current model: `{MODEL}`", ephemeral=True)


@bot.tree.command(name="history", description="Show conversation length")
async def cmd_history(interaction: discord.Interaction):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return
    key = session_key(interaction.user.id, interaction.channel_id)
    count = len(bot.histories[key])
    await interaction.response.send_message(
        f"History: {count} messages (max {MAX_HISTORY})", ephemeral=True
    )


# --- Message-based interaction (DMs + mentions) ---

@bot.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not is_allowed(message.author.id):
        return

    should_respond = False
    if isinstance(message.channel, discord.DMChannel):
        should_respond = True
    elif bot.user and bot.user.mentioned_in(message):
        should_respond = True

    if not should_respond:
        return

    text = message.content
    if bot.user:
        text = text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "")
    text = text.strip()

    if not text and not message.attachments:
        return

    image_urls = await extract_images(message)

    async with message.channel.typing():
        try:
            reply = await handle_query(text, message.author.id, message.channel_id, image_urls)
        except asyncio.TimeoutError:
            reply = "Gateway timed out."
        except Exception:
            log.exception("Gateway request failed")
            reply = "Failed to reach the gateway."

    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)


def main():
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
