import html
import time
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes


# ==================================================
# إعدادات الهمسات
# ==================================================
WHISPER_TTL = 5 * 60
LINES_PER_PAGE = 6
MAX_PAGES = 7


@dataclass
class WhisperDraft:
    token: str
    chat_id: int
    creator_id: int
    target_id: int
    target_name: str
    creator_name: str
    kind: str  # text / media
    temporary: bool = False
    prompt_message_id: Optional[int] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class Whisper:
    whisper_id: str
    chat_id: int
    message_id: int
    sender_id: int
    receiver_id: int
    sender_name: str
    receiver_name: str
    kind: str
    temporary: bool
    content: Optional[str] = None
    media_type: Optional[str] = None
    media_file_id: Optional[str] = None
    caption: Optional[str] = None
    pages: List[str] = field(default_factory=list)
    receiver_opened: bool = False
    page_by_user: Dict[int, int] = field(default_factory=dict)


# الجلسات النشطة في الذاكرة.
# الهمسات المرسلة تبقى حتى إعادة تشغيل البوت.
_drafts: Dict[str, WhisperDraft] = {}
_whispers: Dict[str, Whisper] = {}


def _clean_expired_drafts() -> None:
    now = time.time()
    expired = [
        token
        for token, draft in _drafts.items()
        if now - draft.created_at >= WHISPER_TTL
    ]
    for token in expired:
        _drafts.pop(token, None)


def _display_name(user) -> str:
    return (getattr(user, "first_name", None) or "مستخدم").strip() or "مستخدم"


def _mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'


def _main_whisper_text(draft: WhisperDraft) -> str:
    return (
        f"• تم تحديد الهمسة لـ ↤︎ {_mention(draft.target_id, draft.target_name)}\n"
        "• اضغط الزر لكتابة الهمسة\n"
        "-"
    )


def _group_whisper_text(whisper: Whisper) -> str:
    return (
        f"• الهمسة لـ ↤︎ {_mention(whisper.receiver_id, whisper.receiver_name)}\n"
        f"• من ↤︎ {_mention(whisper.sender_id, whisper.sender_name)}\n"
        "-"
    )


def _start_keyboard(text_url: str, media_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("همسة نصية 💬", url=text_url)],
        [InlineKeyboardButton("همسة وسائط 🖼️", url=media_url)],
    ])


def _private_keyboard(token: str, temporary: bool) -> InlineKeyboardMarkup:
    # المؤقت متاح للنصوص فقط.
    label = "🟢 همسة مؤقتة ." if temporary else "🔴 همسة مؤقتة ."
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"wh_temp:{token}")]
    ])


def _view_keyboard(whisper_id: str, sender_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("فتح الهمسة", callback_data=f"wh_open:{whisper_id}")],
        [InlineKeyboardButton(f"اهمس لـ {sender_name}", callback_data=f"wh_reply:{whisper_id}")],
    ])


def _split_pages(text: str) -> List[str]:
    lines = text.splitlines() or [""]
    pages = [
        "\n".join(lines[i:i + LINES_PER_PAGE])
        for i in range(0, len(lines), LINES_PER_PAGE)
    ]
    return pages


def _page_text(whisper: Whisper, user_id: int, page_index: int) -> str:
    page = whisper.pages[page_index]
    # Telegram CallbackQuery answer محدود بـ 200 حرفًا. نحافظ على شكل الصفحة
    # كما هو قدر الإمكان؛ الصفحات التي تتجاوز الحد تُرسل في الخاص بدل القص.
    return page


async def whisper_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """همسه/همسة/اهمس - يعمل فقط عند الرد على شخص."""
    if not update.message or update.message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        return

    target = reply.from_user
    creator = update.effective_user
    if not creator:
        return

    # تنظيف الجلسات ا��منتهية.
    _clean_expired_drafts()

    token = secrets.token_urlsafe(10)
    draft = WhisperDraft(
        token=token,
        chat_id=update.effective_chat.id,
        creator_id=creator.id,
        target_id=target.id,
        target_name=_display_name(target),
        creator_name=_display_name(creator),
        kind="pending",
    )
    _drafts[token] = draft

    me = await context.bot.get_me()
    text_url = f"https://t.me/{me.username}?start=whisper_text_{token}"
    media_url = f"https://t.me/{me.username}?start=whisper_media_{token}"

    await update.message.reply_text(
        _main_whisper_text(draft),
        parse_mode="HTML",
        reply_markup=_start_keyboard(text_url, media_url),
    )


async def whisper_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج /start whisper_TOKEN فقط، ويترك /start العادي للهاندلر الأصلي."""
    if not update.message or update.effective_chat.type != ChatType.PRIVATE:
        return False

    text = (update.message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].startswith("whisper_"):
        return False

    payload = parts[1][len("whisper_"):]
    if payload.startswith("text_"):
        kind = "text"
        token = payload[len("text_"):]
    elif payload.startswith("media_"):
        kind = "media"
        token = payload[len("media_"):]
    else:
        return False

    _clean_expired_drafts()
    draft = _drafts.get(token)

    if not draft or draft.creator_id != update.effective_user.id:
        await update.message.reply_text("❌ انتهت جلسة الهمسة، اكتب اهمس من جديد.")
        return True

    draft.kind = kind
    draft.created_at = time.time()

    draft.prompt_message_id = (
        await update.message.reply_text(
            "تمام ارسل همستك الحين .",
            reply_markup=(
                _private_keyboard(token, draft.temporary)
                if draft.kind == "text"
                else None
            ),
        )
    ).message_id

    return True


async def whisper_temp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _clean_expired_drafts()

    token = query.data.split(":", 1)[1]
    draft = _drafts.get(token)
    if not draft:
        await query.answer("❌ انتهت جلسة الهمسة، اكتب اهمس من جديد.", show_alert=True)
        return

    if query.from_user.id != draft.creator_id:
        await query.answer("❌ هذه الهمسة ليست لك.", show_alert=True)
        return

    if draft.kind != "text":
        await query.answer()
        return

    draft.temporary = not draft.temporary
    await query.answer()

    try:
        await query.edit_message_reply_markup(
            reply_markup=_private_keyboard(token, draft.temporary)
        )
    except Exception:
        pass


async def whisper_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل أول رسالة بعد تعليمات الهمسة في الخاص."""
    if not update.message or update.effective_chat.type != ChatType.PRIVATE:
        return

    _clean_expired_drafts()
    user_id = update.effective_user.id

    drafts = [d for d in _drafts.values() if d.creator_id == user_id]
    if not drafts:
        return

    # نستخدم أحدث جلسة.
    draft = max(drafts, key=lambda x: x.created_at)
    if time.time() - draft.created_at >= WHISPER_TTL:
        _drafts.pop(draft.token, None)
        return

    # لا نلتقط رسائل /start أو جلسات غير مكتملة.
    if draft.kind not in ("text", "media"):
        return

    message = update.message
    content = None
    media_type = None
    media_file_id = None
    caption = None

    if draft.kind == "text":
        if not message.text or message.text.startswith("/start"):
            return
        content = message.text
        pages = _split_pages(content)
        if len(pages) > MAX_PAGES:
            await message.reply_text("❌ الهمسة طويلة جدًا. الحد الأقصى 7 صفحات، وكل صفحة 6 سطور.")
            return
    else:
        if message.photo:
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
            caption = message.caption
        elif message.animation:
            media_type = "animation"
            media_file_id = message.animation.file_id
            caption = message.caption
        elif message.sticker:
            media_type = "sticker"
            media_file_id = message.sticker.file_id
        else:
            return
        pages = []

    whisper_id = secrets.token_urlsafe(12)
    whisper = Whisper(
        whisper_id=whisper_id,
        chat_id=draft.chat_id,
        message_id=0,
        sender_id=draft.creator_id,
        receiver_id=draft.target_id,
        sender_name=draft.creator_name,
        receiver_name=draft.target_name,
        kind=draft.kind,
        temporary=(draft.temporary if draft.kind == "text" else False),
        content=content,
        media_type=media_type,
        media_file_id=media_file_id,
        caption=caption,
        pages=pages,
    )

    # احذف رسالة المستخدم التي تحتوي الهمسة فقط.
    try:
        await message.delete()
    except Exception:
        pass

    _drafts.pop(draft.token, None)

    sent = await context.bot.send_message(
        chat_id=whisper.chat_id,
        text=_group_whisper_text(whisper),
        parse_mode="HTML",
        reply_markup=_view_keyboard(whisper.whisper_id, whisper.sender_name),
    )
    whisper.message_id = sent.message_id
    _whispers[whisper.whisper_id] = whisper

    await context.bot.send_message(
        chat_id=user_id,
        text=f"تمام ارسلت همستك لـ {_display_name_from_saved(whisper.receiver_name)} بنجاح .",
    )


def _display_name_from_saved(name: str) -> str:
    return name or "مستخدم"


async def whisper_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    whisper_id = query.data.split(":", 1)[1]
    whisper = _whispers.get(whisper_id)

    if not whisper:
        await query.answer("❌ الهمسة غير موجودة.", show_alert=True)
        return

    user_id = query.from_user.id
    if user_id not in (whisper.sender_id, whisper.receiver_id):
        await query.answer("❌ هذه الهمسة ليست لك.", show_alert=True)
        return

    # الهمسة المؤقتة: المرسل يفتحها بلا استهلاك، المستلم يستهلكها من أول فتح.
    if whisper.temporary and whisper.receiver_opened:
        await query.answer("الهمسة اختفت… الهمسة كانت مؤقتة❕", show_alert=True)
        return

    if whisper.kind == "text":
        current = whisper.page_by_user.get(user_id, 0)
        if current >= len(whisper.pages):
            current = 0

        page = _page_text(whisper, user_id, current)
        page_label = f"📄 الصفحة {current + 1}/{len(whisper.pages)}"
        alert = f"{page}\n\n{page_label}"

        # CallbackQuery alerts لا تتجاوز 200 حرفًا.
        if len(alert) <= 200:
            await query.answer(alert, show_alert=True)
        else:
            await query.answer("📄 الصفحة طويلة، تم إرسالها لك في الخاص.", show_alert=True)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{page}\n\n{page_label}",
                )
            except Exception:
                pass

        next_page = current + 1
        if next_page >= len(whisper.pages):
            next_page = 0
        whisper.page_by_user[user_id] = next_page

        if whisper.temporary and user_id == whisper.receiver_id:
            whisper.receiver_opened = True
            try:
                await context.bot.edit_message_text(
                    chat_id=whisper.chat_id,
                    message_id=whisper.message_id,
                    text="الهمسة اختفت… الهمسة كانت مؤقتة❕",
                )
            except Exception:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=whisper.chat_id,
                        message_id=whisper.message_id,
                        reply_markup=None,
                    )
                except Exception:
                    pass

        return

    # الوسائط
    if whisper.media_type == "photo":
        await context.bot.send_photo(
            chat_id=user_id,
            photo=whisper.media_file_id,
            caption=whisper.caption,
        )
    elif whisper.media_type == "animation":
        await context.bot.send_animation(
            chat_id=user_id,
            animation=whisper.media_file_id,
            caption=whisper.caption,
        )
    elif whisper.media_type == "sticker":
        await context.bot.send_sticker(
            chat_id=user_id,
            sticker=whisper.media_file_id,
        )

    await query.answer("تم فتح الهمسة.")


async def whisper_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    whisper_id = query.data.split(":", 1)[1]
    whisper = _whispers.get(whisper_id)

    if not whisper:
        await query.answer("❌ الهمسة غير موجودة.", show_alert=True)
        return

    if query.from_user.id != whisper.receiver_id:
        await query.answer("• انت لم تكتب اهمس بالقروب", show_alert=True)
        return

    token = secrets.token_urlsafe(10)
    new_draft = WhisperDraft(
        token=token,
        chat_id=whisper.chat_id,
        creator_id=whisper.receiver_id,
        target_id=whisper.sender_id,
        target_name=whisper.sender_name,
        creator_name=whisper.receiver_name,
        kind="pending",
    )
    _drafts[token] = new_draft

    me = await context.bot.get_me()
    start_url = f"https://t.me/{me.username}?start=whisper_{token}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("فتح الخاص وكتابة الهمسة", url=start_url)]
    ])

    await query.answer()
    await query.message.reply_text(
        "تمام، افتح الخاص مع البوت لكتابة الهمسة .",
        reply_markup=keyboard,
    )


async def whisper_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هاندلر واحد للـ CallbackQuery الخاص بالهمسات."""
    data = update.callback_query.data or ""
    if data.startswith("wh_temp:"):
        return await whisper_temp_callback(update, context)
    if data.startswith("wh_open:"):
        return await whisper_open_callback(update, context)
    if data.startswith("wh_reply:"):
        return await whisper_reply_callback(update, context)


def whisper_callback_filter(update: Update) -> bool:
    return bool(
        update.callback_query
        and isinstance(update.callback_query.data, str)
        and update.callback_query.data.startswith("wh_")
    )
