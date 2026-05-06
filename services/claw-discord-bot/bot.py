from __future__ import annotations

import os
import re
import asyncio
import base64
import json
import logging
from collections import defaultdict, deque
from io import BytesIO
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from bs4 import BeautifulSoup
from pypdf import PdfReader
from fpdf import FPDF

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
TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".csv", ".xml", ".html", ".css", ".sh", ".bash",
    ".rs", ".go", ".java", ".c", ".cpp", ".h", ".rb", ".lua",
    ".sql", ".env", ".ini", ".cfg", ".conf", ".log",
})
URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+")
MAX_WEB_CONTENT = 12000
MAX_FILE_CONTENT = 16000
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024

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


# --- Content extraction ---

async def fetch_url_content(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ClawBot/1.0)"}
        async with bot.http_session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True, max_redirects=5,
        ) as resp:
            if resp.status != 200:
                return f"[Failed to fetch {url}: HTTP {resp.status}]"
            content_type = resp.headers.get("Content-Type", "")
            if "application/pdf" in content_type:
                data = await resp.read()
                return extract_pdf_bytes(data, url)
            if "text" not in content_type and "json" not in content_type and "xml" not in content_type:
                return f"[Skipped {url}: non-text content ({content_type})]"
            html = await resp.text(errors="replace")
    except Exception as e:
        return f"[Failed to fetch {url}: {e}]"

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)

    lines = [l for l in text.splitlines() if l.strip()]
    text = "\n".join(lines)
    if len(text) > MAX_WEB_CONTENT:
        text = text[:MAX_WEB_CONTENT] + "\n[...truncated]"

    header = f"[Web: {title}]" if title else f"[Web: {url}]"
    return f"{header}\n{text}"


def extract_pdf_bytes(data: bytes, source: str = "attachment") -> str:
    try:
        reader = PdfReader(BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"--- Page {i+1} ---\n{page_text}")
        text = "\n".join(pages)
        if not text.strip():
            return f"[PDF from {source}: no extractable text (scanned/image PDF)]"
        if len(text) > MAX_FILE_CONTENT:
            text = text[:MAX_FILE_CONTENT] + "\n[...truncated]"
        return f"[PDF: {source}]\n{text}"
    except Exception as e:
        return f"[Failed to read PDF from {source}: {e}]"


async def read_attachment(att: discord.Attachment) -> str:
    if att.size > MAX_ATTACHMENT_SIZE:
        return f"[Skipped {att.filename}: too large ({att.size // 1024 // 1024}MB)]"
    data = await att.read()
    mime = (att.content_type or "").split(";")[0].strip()
    ext = os.path.splitext(att.filename)[1].lower()

    if mime == "application/pdf" or ext == ".pdf":
        return extract_pdf_bytes(data, att.filename)

    if ext in TEXT_EXTENSIONS or mime.startswith("text/"):
        try:
            text = data.decode("utf-8", errors="replace")
            if len(text) > MAX_FILE_CONTENT:
                text = text[:MAX_FILE_CONTENT] + "\n[...truncated]"
            return f"[File: {att.filename}]\n{text}"
        except Exception:
            return f"[Failed to read {att.filename}]"

    return ""


async def download_image_as_data_url(url: str, content_type: str) -> str:
    async with bot.http_session.get(url) as resp:
        if resp.status != 200:
            return None
        data = await resp.read()
    b64 = base64.b64encode(data).decode()
    mime = content_type.split(";")[0].strip()
    return f"data:{mime};base64,{b64}"


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text)


async def process_attachments(message: discord.Message) -> tuple:
    image_urls = []
    file_contents = []
    for att in message.attachments:
        mime = (att.content_type or "").split(";")[0].strip()
        if mime in IMAGE_MIMES:
            data_url = await download_image_as_data_url(att.url, att.content_type)
            if data_url:
                image_urls.append(data_url)
        else:
            content = await read_attachment(att)
            if content:
                file_contents.append(content)
    return image_urls, file_contents


# --- PDF generation ---

def generate_pdf(text: str, title: str = "Generated Document") -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)

    for line in text.split("\n"):
        if line.startswith("# "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 6, line[2:])
            pdf.set_font("Helvetica", "", 11)
        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 6, line[3:])
            pdf.set_font("Helvetica", "", 11)
        elif line.startswith("- "):
            pdf.multi_cell(0, 5, "  • " + line[2:])
        elif line.strip() == "":
            pdf.ln(3)
        else:
            pdf.multi_cell(0, 5, line)

    return pdf.output()


# --- Message building ---

def build_content(text: str, image_urls: list[str]) -> str | list:
    if not image_urls:
        return text
    parts = []
    if text:
        parts.append({"type": "text", "text": text})
    for url in image_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


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


# --- Gateway communication ---

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
    file_contexts: list[str] | None = None,
    url_contexts: list[str] | None = None,
) -> str:
    key = session_key(user_id, channel_id)

    full_text_parts = []
    if url_contexts:
        full_text_parts.extend(url_contexts)
    if file_contexts:
        full_text_parts.extend(file_contexts)
    if text:
        full_text_parts.append(text)
    combined_text = "\n\n".join(full_text_parts)

    content = build_content(combined_text, image_urls or [])
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

@bot.tree.command(name="ask", description="Ask the AI a question (with optional image or file)")
@app_commands.describe(
    prompt="Your question or message",
    image="An image to analyze (optional)",
    file="A file to read (PDF, text, code — optional)",
    url="A URL to fetch and read (optional)",
)
async def cmd_ask(
    interaction: discord.Interaction,
    prompt: str,
    image: Optional[discord.Attachment] = None,
    file: Optional[discord.Attachment] = None,
    url: Optional[str] = None,
):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return

    await interaction.response.defer()

    image_urls = []
    file_contexts = []
    url_contexts = []

    if image and image.content_type and image.content_type.split(";")[0].strip() in IMAGE_MIMES:
        data_url = await download_image_as_data_url(image.url, image.content_type)
        if data_url:
            image_urls.append(data_url)

    if file:
        content = await read_attachment(file)
        if content:
            file_contexts.append(content)

    if url:
        content = await fetch_url_content(url)
        if content:
            url_contexts.append(content)

    urls_in_prompt = extract_urls(prompt)
    for u in urls_in_prompt:
        content = await fetch_url_content(u)
        if content:
            url_contexts.append(content)

    try:
        reply = await handle_query(
            prompt, interaction.user.id, interaction.channel_id,
            image_urls, file_contexts, url_contexts,
        )
    except asyncio.TimeoutError:
        reply = "Gateway timed out."
    except Exception:
        log.exception("Gateway request failed")
        reply = "Failed to reach the gateway."

    for chunk in split_message(reply):
        await interaction.followup.send(chunk)


@bot.tree.command(name="pdf", description="Generate a PDF from the AI's response")
@app_commands.describe(
    prompt="What to generate (e.g. 'write a summary of...')",
    source="A PDF or text file to read/transform (optional)",
    url="A URL to fetch as source material (optional)",
    title="PDF title (optional, defaults to 'Generated Document')",
)
async def cmd_pdf(
    interaction: discord.Interaction,
    prompt: str,
    source: Optional[discord.Attachment] = None,
    url: Optional[str] = None,
    title: Optional[str] = None,
):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return

    await interaction.response.defer()

    file_contexts = []
    url_contexts = []

    if source:
        content = await read_attachment(source)
        if content:
            file_contexts.append(content)

    if url:
        content = await fetch_url_content(url)
        if content:
            url_contexts.append(content)

    urls_in_prompt = extract_urls(prompt)
    for u in urls_in_prompt:
        content = await fetch_url_content(u)
        if content:
            url_contexts.append(content)

    pdf_instruction = (
        "Generate your response as clean, well-structured text suitable for a PDF document. "
        "Use markdown-style headings (# and ##) and bullet points (- ) for structure. "
        "Do not use code fences or special formatting beyond that."
    )
    full_prompt = f"{pdf_instruction}\n\n{prompt}"

    try:
        reply = await handle_query(
            full_prompt, interaction.user.id, interaction.channel_id,
            file_contexts=file_contexts, url_contexts=url_contexts,
        )
    except asyncio.TimeoutError:
        await interaction.followup.send("Gateway timed out.")
        return
    except Exception:
        log.exception("Gateway request failed")
        await interaction.followup.send("Failed to reach the gateway.")
        return

    pdf_title = title or "Generated Document"
    try:
        pdf_bytes = generate_pdf(reply, pdf_title)
    except Exception:
        log.exception("PDF generation failed")
        await interaction.followup.send("Failed to generate PDF. Here's the text instead:")
        for chunk in split_message(reply):
            await interaction.followup.send(chunk)
        return

    filename = re.sub(r"[^\w\s-]", "", pdf_title).strip().replace(" ", "_")[:50] + ".pdf"
    await interaction.followup.send(
        file=discord.File(BytesIO(pdf_bytes), filename=filename)
    )


@bot.tree.command(name="fetch", description="Fetch a URL and show its content")
@app_commands.describe(url="The URL to fetch and display")
async def cmd_fetch(interaction: discord.Interaction, url: str):
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return

    await interaction.response.defer()
    content = await fetch_url_content(url)

    if len(content) > DISCORD_MAX_LEN * 3:
        pdf_bytes = generate_pdf(content, f"Content from {url}")
        await interaction.followup.send(
            content="Content was too long, sent as PDF:",
            file=discord.File(BytesIO(pdf_bytes), filename="fetched_content.pdf"),
        )
    else:
        for chunk in split_message(content):
            await interaction.followup.send(f"```\n{chunk}\n```" if len(chunk) < 1990 else chunk)


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
        await interaction.response.send_message("System prompt set.", ephemeral=True)
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

    image_urls, file_contexts = await process_attachments(message)
    url_contexts = []
    for url in extract_urls(text):
        content = await fetch_url_content(url)
        if content:
            url_contexts.append(content)

    async with message.channel.typing():
        try:
            reply = await handle_query(
                text, message.author.id, message.channel_id,
                image_urls, file_contexts, url_contexts,
            )
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
