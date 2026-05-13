#!/usr/bin/env python3
"""
PLAYER2 AI BOT — Telegram Bot
Powered by Player2.game API
Features: AI Image, Music, Video, Sprite, 3D generation
"""

import asyncio
import json
import random
import httpx
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ParseMode, ChatAction

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN       = "8924492918:AAGaKEZwAAHbzsIPp1ZY6Z6394yDkXXDmVQ"
PLAYER2_API_KEY = "p2_rKAe-A7wBgHG_XkMWMkhiA"
MCP_URL         = "https://api.player2.game/api/v1/mcp"
ADMIN_ID        = 8600328303

HEADERS_BASE = {
    "Authorization": f"Bearer {PLAYER2_API_KEY}",
    "Content-Type": "application/json",
}

# ─────────────────────────────────────────────
# RANDOM TAGLINES — changes every /start
# ─────────────────────────────────────────────
TAGLINES = [
    "🔥 Where imagination meets AI power",
    "💫 Your words become instant masterpieces",
    "🚀 Create\\. Generate\\. Dominate\\.",
    "⚡ Turn prompts into reality",
    "🌌 Next\\-gen AI creative studio",
    "🎯 Prompt it\\. Generate it\\. Own it\\.",
    "🛸 The future of content is here",
    "🎨 Every prompt — a new universe",
    "💎 AI\\-powered\\. Human\\-inspired\\.",
    "🌊 Ride the wave of AI creation",
    "🧠 Your ideas\\, supercharged by AI",
    "✨ One prompt\\. Infinite possibilities\\.",
]

# ─────────────────────────────────────────────
# MCP CLIENT
# ─────────────────────────────────────────────
async def mcp_init(client: httpx.AsyncClient) -> str | None:
    """Initialize MCP session, return session ID."""
    try:
        resp = await client.post(
            MCP_URL,
            headers=HEADERS_BASE,
            json={
                "jsonrpc": "2.0", "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "telegram-bot", "version": "1.0"},
                },
            },
            timeout=30,
        )
        return resp.headers.get("mcp-session-id")
    except Exception:
        return None


async def mcp_call(client: httpx.AsyncClient, session_id: str,
                   tool: str, params: dict) -> dict:
    """Call an MCP tool and return the result dict."""
    headers = {**HEADERS_BASE, "mcp-session-id": session_id}
    resp = await client.post(
        MCP_URL,
        headers=headers,
        json={
            "jsonrpc": "2.0", "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": params},
        },
        timeout=60,
    )
    data = resp.json()
    result = data.get("result") or {}
    content = result.get("content") or []
    if content and isinstance(content, list):
        for item in content:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except Exception:
                    return {"raw": item["text"]}
    return data


async def mcp_poll_job(client: httpx.AsyncClient, session_id: str,
                       check_tool: str, job_id: str,
                       interval: int = 10, max_wait: int = 300) -> dict:
    """Poll a job until completed/failed."""
    elapsed = 0
    while elapsed < max_wait:
        await asyncio.sleep(interval)
        elapsed += interval
        result = await mcp_call(client, session_id, check_tool, {"job_id": job_id})
        status = result.get("status", "")
        if status in ("completed", "succeeded", "failed", "done"):
            return result
    return {"status": "timeout"}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


async def typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )


async def uploading_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO
    )


async def uploading_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT
    )


async def _send_audio_robust(context: ContextTypes.DEFAULT_TYPE,
                              chat_id: int, url: str, caption: str):
    """
    Try send_audio via URL → download & resend → fallback to send_document.
    Player2 audio URLs sometimes need special handling.
    """
    # Attempt 1: direct URL
    try:
        await context.bot.send_audio(
            chat_id=chat_id, audio=url,
            caption=caption, parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    except Exception:
        pass

    # Attempt 2: download bytes → resend as audio
    try:
        async with httpx.AsyncClient(follow_redirects=True) as dl:
            r = await dl.get(url, timeout=90)
            bio = BytesIO(r.content)
            bio.name = "music.mp3"
        await context.bot.send_audio(
            chat_id=chat_id, audio=bio,
            caption=caption, parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    except Exception:
        pass

    # Attempt 3: send as document
    try:
        await context.bot.send_document(
            chat_id=chat_id, document=url,
            caption=caption, parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎵 Music ready\\! [Download here]({url})",
            parse_mode=ParseMode.MARKDOWN_V2
        )


# ─────────────────────────────────────────────
# /start  ← COMPLETELY REDESIGNED
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = esc(user.first_name or "Creator")
    tagline = random.choice(TAGLINES)

    kb = [
        [
            InlineKeyboardButton("🌈 Image Gen", callback_data="help_image"),
            InlineKeyboardButton("🎧 Music AI", callback_data="help_music"),
        ],
        [
            InlineKeyboardButton("🎞️ Video Gen", callback_data="help_video"),
            InlineKeyboardButton("👾 Sprite Gen", callback_data="help_sprite"),
        ],
        [
            InlineKeyboardButton("🧊 3D Model", callback_data="help_3d"),
            InlineKeyboardButton("🖌️ Edit Image", callback_data="help_edit"),
        ],
        [InlineKeyboardButton("📋 All Commands", callback_data="help_all")],
    ]

    msg = (
        "╔══════════════════════════╗\n"
        "║  🎮  *P L A Y E R ² A I*  ║\n"
        "╚══════════════════════════╝\n\n"
        f"✦ Hey *{name}*\\! Welcome\\! ✦\n\n"
        f"_{tagline}_\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🖼️  AI Images \\& Sprites\n"
        "🎵  AI Music Composition\n"
        "🎬  AI Video Generation\n"
        "📦  3D Model Builder \\(GLB\\)\n"
        "✏️  AI Image Editor\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Powered by [Player2\\.game](https://player2\\.game)\n\n"
        "⬇️ *Tap a feature to begin\\!*"
    )

    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ─────────────────────────────────────────────
# /help
# ─────────────────────────────────────────────
HELP_TEXT = {
    "help_image":  (
        "🌈 *Image Generation*\n\n"
        "`/image <prompt>`\n\n"
        "Example:\n`/image a cyberpunk samurai in neon rain`\n\n"
        "💡 Cost: 3 Joules"
    ),
    "help_music":  (
        "🎧 *Music Generation*\n\n"
        "`/music <prompt>`\n"
        "Optional: add `\\-\\-sec 60` for duration\n\n"
        "Example:\n`/music epic battle orchestral music \\-\\-sec 30`\n\n"
        "💡 Cost: 140 Joules/min"
    ),
    "help_video":  (
        "🎞️ *Video Generation*\n\n"
        "`/video <prompt>`\n\n"
        "Example:\n`/video a dragon flying over mountains`\n\n"
        "💡 Cost: 50 Joules \\(5 sec, 480p\\)"
    ),
    "help_sprite": (
        "👾 *Sprite Generation*\n\n"
        "`/sprite <prompt>`\n\n"
        "Example:\n`/sprite pixel art warrior character facing right`\n\n"
        "💡 Cost: 3 Joules"
    ),
    "help_3d":     (
        "🧊 *3D Model Generation*\n\n"
        "`/model <prompt>`\n\n"
        "Example:\n`/model a medieval castle tower`\n\n"
        "💡 Cost: 190 Joules"
    ),
    "help_edit":   (
        "🖌️ *Edit Image*\n\n"
        "Reply to any image with:\n"
        "`/edit <what to change>`\n\n"
        "Example: Reply to a photo →\n"
        "`/edit make the background sunset`\n\n"
        "💡 Cost: 10 Joules"
    ),
    "help_all": (
        "📋 *All Commands*\n\n"
        "`/image <prompt>` — AI image\n"
        "`/music <prompt>` — AI music\n"
        "`/video <prompt>` — AI video\n"
        "`/sprite <prompt>` — Game sprite\n"
        "`/model <prompt>` — 3D model \\(GLB\\)\n"
        "`/edit <prompt>` — Edit image \\(reply\\)\n"
        "`/balance` — Check Joules balance\n"
        "`/help` — Show this menu\n"
    ),
}


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
    await update.message.reply_text(
        HELP_TEXT["help_all"],
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(kb),
    )


def _start_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌈 Image Gen", callback_data="help_image"),
            InlineKeyboardButton("🎧 Music AI", callback_data="help_music"),
        ],
        [
            InlineKeyboardButton("🎞️ Video Gen", callback_data="help_video"),
            InlineKeyboardButton("👾 Sprite Gen", callback_data="help_sprite"),
        ],
        [
            InlineKeyboardButton("🧊 3D Model", callback_data="help_3d"),
            InlineKeyboardButton("🖌️ Edit Image", callback_data="help_edit"),
        ],
        [InlineKeyboardButton("📋 All Commands", callback_data="help_all")],
    ])


def _start_msg():
    tagline = random.choice(TAGLINES)
    return (
        "╔══════════════════════════╗\n"
        "║  🎮  *P L A Y E R ² A I*  ║\n"
        "╚══════════════════════════╝\n\n"
        f"_{tagline}_\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🖼️  AI Images \\& Sprites\n"
        "🎵  AI Music Composition\n"
        "🎬  AI Video Generation\n"
        "📦  3D Model Builder \\(GLB\\)\n"
        "✏️  AI Image Editor\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Powered by [Player2\\.game](https://player2\\.game)\n\n"
        "⬇️ *Tap a feature to begin\\!*"
    )


async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "back_start":
        await q.edit_message_text(
            _start_msg(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_start_kb(),
        )
        return

    text = HELP_TEXT.get(data, "")
    if text:
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
        await q.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(kb)
        )


# ─────────────────────────────────────────────
# /image
# ─────────────────────────────────────────────
async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "❌ Prompt দাও\\!\nExample: `/image a cyberpunk city at night`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    msg = await update.message.reply_text("🌈 Generating image\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
    await uploading_photo(update, context)

    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\. Try again\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            result = await mcp_call(client, session_id, "generate_image", {"prompt": prompt})
            url = result.get("image_url") or result.get("url") or ""
            if url:
                await msg.delete()
                caption = f"🌈 *Image Generated*\n\n📝 `{esc(prompt)}`\n\n_Powered by Player2\\.game_"
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=url, caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            else:
                err = result.get("error") or result.get("raw") or str(result)
                await msg.edit_text(f"❌ Failed: `{esc(str(err)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# /music  ← FIXED: robust multi-fallback logic
# ─────────────────────────────────────────────
async def cmd_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args_text = " ".join(context.args).strip()
    if not args_text:
        await update.message.reply_text(
            "❌ Prompt দাও\\!\nExample: `/music epic battle music \\-\\-sec 30`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    duration = 30
    prompt = args_text
    if "--sec" in args_text:
        parts = args_text.split("--sec")
        prompt = parts[0].strip()
        try:
            duration = min(300, max(10, int(parts[1].strip().split()[0])))
        except Exception:
            duration = 30

    msg = await update.message.reply_text(
        f"🎧 Generating music \\({duration}s\\)\\.\\.\\. ~1 min wait",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    caption = f"🎧 *Music Generated*\n\n📝 `{esc(prompt)}`\n⏱ {duration}s\n\n_Powered by Player2\\.game_"

    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            # Pass both param names — different API versions use different keys
            result = await mcp_call(client, session_id, "generate_music", {
                "prompt": prompt,
                "duration_seconds": duration,
                "duration": duration,
            })

            # ── Case 1: Synchronous response (direct audio URL) ──
            audio_url = (
                result.get("audio_url") or result.get("url") or
                result.get("music_url") or result.get("file_url") or
                result.get("output_url") or ""
            )
            if audio_url:
                await msg.delete()
                await _send_audio_robust(context, update.effective_chat.id, audio_url, caption)
                return

            # ── Case 2: Async job response ──
            job_id = (
                result.get("job_id") or result.get("id") or
                result.get("task_id") or ""
            )
            if not job_id:
                # Show raw for debugging
                err = result.get("error") or result.get("message") or result.get("raw") or str(result)
                await msg.edit_text(
                    f"❌ Music API error:\n`{esc(str(err)[:300])}`",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                return

            await msg.edit_text("🎧 Music generating\\.\\.\\. Polling status\\.", parse_mode=ParseMode.MARKDOWN_V2)
            done = await mcp_poll_job(
                client, session_id, "check_music_job", job_id,
                interval=10, max_wait=180
            )

            status = done.get("status", "")
            audio_url = (
                done.get("audio_url") or done.get("url") or
                done.get("music_url") or done.get("file_url") or
                done.get("output_url") or ""
            )

            if audio_url:
                await msg.delete()
                await _send_audio_robust(context, update.effective_chat.id, audio_url, caption)
            elif status == "failed":
                err = done.get("error") or done.get("message") or "Unknown failure"
                await msg.edit_text(
                    f"❌ Generation failed: `{esc(str(err)[:200])}`",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif status == "timeout":
                await msg.edit_text(
                    "⏳ Timed out\\. Player2 servers might be busy — try again\\!",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await msg.edit_text(
                    f"⏳ Status: `{esc(status)}`\nDebug: `{esc(str(done)[:150])}`",
                    parse_mode=ParseMode.MARKDOWN_V2
                )

        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# /video
# ─────────────────────────────────────────────
async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "❌ Prompt দাও\\!\nExample: `/video a dragon flying over mountains`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    msg = await update.message.reply_text(
        "🎞️ Generating video\\.\\.\\. 2\\-5 minutes",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            result = await mcp_call(client, session_id, "generate_video", {"prompt": prompt})
            job_id = result.get("job_id") or result.get("id") or result.get("task_id") or ""
            if not job_id:
                err = result.get("error") or str(result)
                await msg.edit_text(f"❌ Failed: `{esc(str(err)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)
                return

            await msg.edit_text("🎞️ Video generating\\.\\.\\. Polling status\\.", parse_mode=ParseMode.MARKDOWN_V2)
            done = await mcp_poll_job(client, session_id, "check_video_job", job_id, interval=30, max_wait=360)

            status = done.get("status", "")
            video_url = done.get("video_url") or done.get("url") or done.get("output_url") or ""
            if video_url:
                await msg.delete()
                caption = f"🎞️ *Video Generated*\n\n📝 `{esc(prompt)}`\n⏱ 5 sec \\| 480p\n\n_Powered by Player2\\.game_"
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_url, caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            elif status == "failed":
                await msg.edit_text("❌ Video generation failed\\. Try different prompt\\.", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await msg.edit_text(f"⏳ Still generating\\. Status: `{esc(status)}`", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# /sprite
# ─────────────────────────────────────────────
async def cmd_sprite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "❌ Prompt দাও\\!\nExample: `/sprite pixel art warrior character`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    msg = await update.message.reply_text("👾 Generating sprite\\.\\.\\. 1\\-2 minutes", parse_mode=ParseMode.MARKDOWN_V2)

    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            result = await mcp_call(client, session_id, "generate_sprite",
                                    {"prompt": prompt, "name": prompt[:40]})
            job_id = result.get("job_id") or result.get("id") or result.get("task_id") or ""
            if not job_id:
                err = result.get("error") or str(result)
                await msg.edit_text(f"❌ Failed: `{esc(str(err)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)
                return

            await msg.edit_text("👾 Sprite generating\\.\\.\\. Please wait\\.", parse_mode=ParseMode.MARKDOWN_V2)
            done = await mcp_poll_job(client, session_id, "check_sprite_job", job_id, interval=10, max_wait=180)

            status = done.get("status", "")
            img_url = (done.get("spritesheet_url") or done.get("gif_url")
                       or done.get("image_url") or done.get("url") or "")
            if img_url:
                await msg.delete()
                caption = f"👾 *Sprite Generated*\n\n📝 `{esc(prompt)}`\n\n_Powered by Player2\\.game_"
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=img_url, caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            elif status == "failed":
                await msg.edit_text("❌ Sprite generation failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await msg.edit_text(f"⏳ Status: `{esc(status)}`", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# /model (3D from text)
# ─────────────────────────────────────────────
async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "❌ Prompt দাও\\!\nExample: `/model a medieval castle tower`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    msg = await update.message.reply_text("🧊 Generating 3D model\\.\\.\\. 1\\-5 minutes", parse_mode=ParseMode.MARKDOWN_V2)

    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            result = await mcp_call(client, session_id, "generate_3d_model_from_text", {"prompt": prompt})
            job_id = result.get("job_id") or result.get("id") or result.get("task_id") or ""
            if not job_id:
                err = result.get("error") or str(result)
                await msg.edit_text(f"❌ Failed: `{esc(str(err)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)
                return

            await msg.edit_text("🧊 3D Model generating\\.\\.\\. Please wait\\.", parse_mode=ParseMode.MARKDOWN_V2)
            done = await mcp_poll_job(client, session_id, "check_3d_model_job", job_id, interval=15, max_wait=360)

            status = done.get("status", "")
            glb_url = done.get("glb_url") or done.get("url") or done.get("output_url") or ""
            if glb_url:
                await msg.delete()
                caption = f"🧊 *3D Model Generated \\(GLB\\)*\n\n📝 `{esc(prompt)}`\n\n_Powered by Player2\\.game_"
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=glb_url, caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            elif status == "failed":
                await msg.edit_text("❌ 3D model generation failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await msg.edit_text(f"⏳ Status: `{esc(status)}`", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# /edit (reply to image)
# ─────────────────────────────────────────────
async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    reply = update.message.reply_to_message

    if not prompt:
        await update.message.reply_text(
            "❌ একটা ছবিতে reply করো এবং prompt দাও\\!\nExample: reply to photo → `/edit make the sky purple`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    image_url = None
    if reply and reply.photo:
        photo = reply.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_url = file.file_path
    elif reply and reply.document and reply.document.mime_type and reply.document.mime_type.startswith("image"):
        file = await context.bot.get_file(reply.document.file_id)
        image_url = file.file_path

    if not image_url:
        await update.message.reply_text(
            "❌ একটা ছবিতে reply করো\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    msg = await update.message.reply_text("🖌️ Editing image\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            result = await mcp_call(client, session_id, "edit_image",
                                    {"prompt": prompt, "image_url": image_url})
            url = result.get("image_url") or result.get("url") or ""
            if url:
                await msg.delete()
                caption = f"🖌️ *Image Edited*\n\n📝 `{esc(prompt)}`\n\n_Powered by Player2\\.game_"
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=url, caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            else:
                err = result.get("error") or result.get("raw") or str(result)
                await msg.edit_text(f"❌ Failed: `{esc(str(err)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# /balance
# ─────────────────────────────────────────────
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("💰 Checking balance\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
    async with httpx.AsyncClient() as client:
        session_id = await mcp_init(client)
        if not session_id:
            await msg.edit_text("❌ API connection failed\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        try:
            result = await mcp_call(client, session_id, "list_assets", {"limit": 1, "public_only": False})
            await msg.edit_text(
                "💰 *Player2 Account Active*\n\nAPI connected successfully\\!\n\n"
                "💡 *Cost per generation:*\n"
                "• 🌈 Image: 3 Joules\n"
                "• 👾 Sprite: 3 Joules\n"
                "• 🖌️ Edit: 10 Joules\n"
                "• 🎞️ Video: 50 Joules\n"
                "• 🎧 Music: 140 Joules/min\n"
                "• 🧊 3D Model: 190 Joules\n\n"
                "_Powered by [Player2\\.game](https://player2\\.game)_",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            await msg.edit_text(f"❌ Error: `{esc(str(e)[:200])}`", parse_mode=ParseMode.MARKDOWN_V2)


# ─────────────────────────────────────────────
# NOOP — silently ignore photo / video / audio
# ─────────────────────────────────────────────
async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Do nothing for non-command media messages."""
    pass


# ─────────────────────────────────────────────
# Unknown command
# ─────────────────────────────────────────────
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Unknown command\\. Use /help to see all commands\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("🎮 PLAYER2 AI BOT starting...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("image",   cmd_image))
    app.add_handler(CommandHandler("music",   cmd_music))
    app.add_handler(CommandHandler("video",   cmd_video))
    app.add_handler(CommandHandler("sprite",  cmd_sprite))
    app.add_handler(CommandHandler("model",   cmd_model))
    app.add_handler(CommandHandler("edit",    cmd_edit))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CallbackQueryHandler(cb_handler))

    # Silently ignore media without commands
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE)
        & ~filters.COMMAND,
        noop
    ))

    # Unknown commands only (not plain text)
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("✅ Bot running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
