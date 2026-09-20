# handlers/send.py

import re

from telegram import Update, MessageEntity
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.developer_panel import get_registered_chats


# =========================================================
# الإعدادات
# =========================================================

SEND_COMMAND_RE = re.compile(
    r"^/send(?:@[A-Za-z0-9_]+)?(?:\s+|$)",
    re.IGNORECASE,
)


# =========================================================
# أدوات مساعدة
# =========================================================

def _utf16_len(text: str) -> int:
    """
    Telegram يستخدم UTF-16 offsets للـ MessageEntity.
    """
    return len(text.encode("utf-16-le")) // 2


def _strip_send_command(text: str):
    """
    يحذف /send من بداية النص ويرجع:
    payload + عدد وحدات UTF-16 التي تم حذفها.
    """

    if not text:
        return "", 0

    match = SEND_COMMAND_RE.match(text)

    if not match:
        return text, 0

    prefix = match.group(0)
    payload = text[len(prefix):]

    return payload, _utf16_len(prefix)


def _adjust_entities(
    entities,
    removed_utf16_length: int,
    original_text: str,
):
    """
    يعدّل MessageEntity offsets بعد حذف /send.

    Telegram offsets = UTF-16.
    """

    if not entities:
        return []

    adjusted = []

    for entity in entities:
        start = entity.offset
        end = entity.offset + entity.length

        # Entity بالكامل داخل /send
        if end <= removed_utf16_length:
            continue

        # قص الجزء الموجود داخل /send
        if start < removed_utf16_length:
            start = removed_utf16_length

        new_offset = start - removed_utf16_length

        new_length = end - max(
            entity.offset,
            removed_utf16_length,
        )

        if new_length <= 0:
            continue

        adjusted.append(
            MessageEntity(
                type=entity.type,
                offset=new_offset,
                length=new_length,
                url=entity.url,
                user=entity.user,
                language=entity.language,
                custom_emoji_id=entity.custom_emoji_id,
            )
        )

    return adjusted


def _replace_variables(text: str, title: str) -> str:
    """
    متغيرات /send الخاصة بالقروبات والقنوات.

    #الاسم
    #منشن

    كلاهما يصبح اسم القروب/القناة.
    """

    if not text:
        return text

    title = title or ""

    text = text.replace("#الاسم", title)
    text = text.replace("#منشن", title)

    return text


def _copy_entities_with_variable_replacement(
    text: str,
    entities,
    title: str,
):
    """
    يستبدل #الاسم و #منشن مع المحافظة على بقية الـ entities
    قدر الإمكان.

    إذا كان Entity يغطي متغيراً سيتم الحفاظ على الـ formatting
    حسب النص الناتج إذا كانت الأطوال لم تتغير.
    """

    if not text:
        return "", []

    replacements = {
        "#الاسم": title or "",
        "#منشن": title or "",
    }

    new_text = text

    # نحاول تنفيذ الاستبدالات مع تعديل offsets
    # لأن أسماء القروبات قد تختلف أطوالها.
    changes = []

    for old, new in replacements.items():
        start_search = 0

        while True:
            index = new_text.find(old, start_search)

            if index == -1:
                break

            changes.append(
                (
                    _utf16_len(new_text[:index]),
                    _utf16_len(old),
                    _utf16_len(new),
                )
            )

            start_search = index + len(old)

        new_text = new_text.replace(old, new)

    if not changes:
        return text, list(entities or [])

    # بما أننا نحتاج تعديل النص من الأصل،
    # نعيد حساب الـ entities اعتماداً على المقاطع.
    #
    # هذه الطريقة تحافظ على الـ entities التي لا تتأثر
    # بالاستبدال، وتتعامل مع التغيير في طول المتغير.

    original_text = text

    # ابحث عن جميع المتغيرات في النص الأصلي.
    matches = []

    for match in re.finditer(r"#(?:الاسم|منشن)", original_text):
        old = match.group(0)

        matches.append(
            (
                match.start(),
                match.end(),
                title or "",
            )
        )

    if not matches:
        return original_text, list(entities or [])

    # بناء النص الجديد
    pieces = []
    last = 0

    for start, end, replacement in matches:
        pieces.append(original_text[last:start])
        pieces.append(replacement)
        last = end

    pieces.append(original_text[last:])

    new_text = "".join(pieces)

    if not entities:
        return new_text, []

    adjusted_entities = []

    for entity in entities:
        entity_start = entity.offset
        entity_end = entity.offset + entity.length

        # نحول entity إلى بداية/نهاية تقريبية عبر UTF-16.
        shift = 0

        # نحاول الاحتفاظ بالتنسيق إذا كان الـ entity
        # يغطي النص بعد التعديل.
        new_start = entity_start

        for start_char, end_char, replacement in matches:
            old_start_utf16 = _utf16_len(
                original_text[:start_char]
            )

            old_end_utf16 = _utf16_len(
                original_text[:end_char]
            )

            old_length = old_end_utf16 - old_start_utf16
            new_length = _utf16_len(replacement)

            if entity_end <= old_start_utf16:
                break

            if entity_start >= old_end_utf16:
                shift += new_length - old_length
                continue

            # Entity يتداخل مع المتغير.
            #
            # إذا كان يغطي المتغير بالكامل، نحاول تمديده
            # ليغطي النص البديل بالكامل.
            if (
                entity_start <= old_start_utf16
                and entity_end >= old_end_utf16
            ):
                entity_end += new_length - old_length
                shift += new_length - old_length

            else:
                # Entity متداخل جزئياً مع المتغير.
                # نتركه كما هو قدر الإمكان.
                shift += new_length - old_length

        new_start = entity_start

        # احسب shift الخاص بالبدايات السابقة
        for start_char, end_char, replacement in matches:
            old_start_utf16 = _utf16_len(
                original_text[:start_char]
            )
            old_end_utf16 = _utf16_len(
                original_text[:end_char]
            )

            if entity_start >= old_end_utf16:
                shift_amount = (
                    _utf16_len(replacement)
                    - (old_end_utf16 - old_start_utf16)
                )
                new_start += shift_amount

        new_length = entity_end - entity_start

        if new_length <= 0:
            continue

        try:
            adjusted_entities.append(
                MessageEntity(
                    type=entity.type,
                    offset=new_start,
                    length=new_length,
                    url=entity.url,
                    user=entity.user,
                    language=entity.language,
                    custom_emoji_id=entity.custom_emoji_id,
                )
            )
        except Exception:
            continue

    return new_text, adjusted_entities


def _prepare_text_payload(message):
    """
    يجهز نص /send.
    """

    text = message.text or ""
    entities = message.entities or []

    payload, removed_length = _strip_send_command(text)

    entities = _adjust_entities(
        entities,
        removed_length,
        text,
    )

    return payload, entities


def _prepare_caption_payload(message):
    """
    يجهز Caption الخاص برسالة الوسائط.
    """

    caption = message.caption or ""
    entities = message.caption_entities or []

    payload, removed_length = _strip_send_command(caption)

    entities = _adjust_entities(
        entities,
        removed_length,
        caption,
    )

    return payload, entities


# =========================================================
# تحديد عنوان القروب / القناة
# =========================================================

def _get_chat_title(chat_data):
    """
    get_registered_chats() يرجع غالباً:

    chat_id, chat_type, title, username

    """

    if not chat_data:
        return ""

    try:
        return chat_data[2] or ""
    except Exception:
        return ""


def _get_chat_id(chat_data):
    try:
        return int(chat_data[0])
    except Exception:
        return None


def _get_chat_type(chat_data):
    try:
        return chat_data[1]
    except Exception:
        return None


# =========================================================
# إرسال نص
# =========================================================

async def _send_text(
    bot,
    chat_id,
    text,
    entities=None,
):
    if not text:
        return None

    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        entities=entities or None,
    )


# =========================================================
# إرسال أي نوع رسالة
# =========================================================

async def _send_message_content(
    bot,
    chat_id,
    source_message,
    title="",
):
    """
    يرسل محتوى رسالة /send بدون نسخ أمر /send نفسه.
    """

    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    if source_message.text:
        text, entities = _prepare_text_payload(
            source_message
        )

        text, entities = _copy_entities_with_variable_replacement(
            text,
            entities,
            title,
        )

        if not text:
            return None

        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            entities=entities or None,
        )

    # -----------------------------------------------------
    # PHOTO
    # -----------------------------------------------------

    if source_message.photo:
        caption, caption_entities = _prepare_caption_payload(
            source_message
        )

        caption, caption_entities = (
            _copy_entities_with_variable_replacement(
                caption,
                caption_entities,
                title,
            )
        )

        photo = source_message.photo[-1]

        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo.file_id,
            caption=caption or None,
            caption_entities=caption_entities or None,
        )

    # -----------------------------------------------------
    # VIDEO
    # -----------------------------------------------------

    if source_message.video:
        caption, caption_entities = _prepare_caption_payload(
            source_message
        )

        caption, caption_entities = (
            _copy_entities_with_variable_replacement(
                caption,
                caption_entities,
                title,
            )
        )

        return await bot.send_video(
            chat_id=chat_id,
            video=source_message.video.file_id,
            caption=caption or None,
            caption_entities=caption_entities or None,
        )

    # -----------------------------------------------------
    # ANIMATION / GIF
    # -----------------------------------------------------

    if source_message.animation:
        caption, caption_entities = _prepare_caption_payload(
            source_message
        )

        caption, caption_entities = (
            _copy_entities_with_variable_replacement(
                caption,
                caption_entities,
                title,
            )
        )

        return await bot.send_animation(
            chat_id=chat_id,
            animation=source_message.animation.file_id,
            caption=caption or None,
            caption_entities=caption_entities or None,
        )

    # -----------------------------------------------------
    # AUDIO
    # -----------------------------------------------------

    if source_message.audio:
        caption, caption_entities = _prepare_caption_payload(
            source_message
        )

        caption, caption_entities = (
            _copy_entities_with_variable_replacement(
                caption,
                caption_entities,
                title,
            )
        )

        return await bot.send_audio(
            chat_id=chat_id,
            audio=source_message.audio.file_id,
            caption=caption or None,
            caption_entities=caption_entities or None,
        )

    # -----------------------------------------------------
    # VOICE
    # -----------------------------------------------------

    if source_message.voice:
        caption, caption_entities = _prepare_caption_payload(
            source_message
        )

        caption, caption_entities = (
            _copy_entities_with_variable_replacement(
                caption,
                caption_entities,
                title,
            )
        )

        return await bot.send_voice(
            chat_id=chat_id,
            voice=source_message.voice.file_id,
            caption=caption or None,
            caption_entities=caption_entities or None,
        )

    # -----------------------------------------------------
    # DOCUMENT
    # -----------------------------------------------------

    if source_message.document:
        caption, caption_entities = _prepare_caption_payload(
            source_message
        )

        caption, caption_entities = (
            _copy_entities_with_variable_replacement(
                caption,
                caption_entities,
                title,
            )
        )

        return await bot.send_document(
            chat_id=chat_id,
            document=source_message.document.file_id,
            caption=caption or None,
            caption_entities=caption_entities or None,
        )

    # -----------------------------------------------------
    # STICKER
    # -----------------------------------------------------

    if source_message.sticker:
        return await bot.send_sticker(
            chat_id=chat_id,
            sticker=source_message.sticker.file_id,
        )

    # -----------------------------------------------------
    # VIDEO NOTE
    # -----------------------------------------------------

    if source_message.video_note:
        return await bot.send_video_note(
            chat_id=chat_id,
            video_note=source_message.video_note.file_id,
        )

    # -----------------------------------------------------
    # LOCATION
    # -----------------------------------------------------

    if source_message.location:
        return await bot.send_location(
            chat_id=chat_id,
            latitude=source_message.location.latitude,
            longitude=source_message.location.longitude,
        )

    # -----------------------------------------------------
    # VENUE
    # -----------------------------------------------------

    if source_message.venue:
        venue = source_message.venue

        return await bot.send_venue(
            chat_id=chat_id,
            latitude=venue.location.latitude,
            longitude=venue.location.longitude,
            title=venue.title,
            address=venue.address,
            foursquare_id=venue.foursquare_id,
            foursquare_type=venue.foursquare_type,
            google_place_id=venue.google_place_id,
            google_place_type=venue.google_place_type,
        )

    # -----------------------------------------------------
    # CONTACT
    # -----------------------------------------------------

    if source_message.contact:
        contact = source_message.contact

        return await bot.send_contact(
            chat_id=chat_id,
            phone_number=contact.phone_number,
            first_name=contact.first_name,
            last_name=contact.last_name,
            vcard=contact.vcard,
        )

    return None


# =========================================================
# التحقق من /send
# =========================================================

def is_send_command(update: Update) -> bool:
    message = update.effective_message

    if not message:
        return False

    text = message.text or message.caption

    if not text:
        return False

    return bool(SEND_COMMAND_RE.match(text))


# =========================================================
# أمر /send
# =========================================================

async def send_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    if not is_send_command(update):
        return

    # =====================================================
    # حذف رسالة الأمر
    # =====================================================

    try:
        await message.delete()
    except Exception:
        pass

    # =====================================================
    # تحديد مكان الإرسال
    # =====================================================

    chat = update.effective_chat

    if not chat:
        raise ApplicationHandlerStop

    # =====================================================
    # إرسال داخل القروب / القناة
    # =====================================================

    if chat.type in ("group", "supergroup", "channel"):
        try:
            title = chat.title or ""

            await _send_message_content(
                bot=context.bot,
                chat_id=chat.id,
                source_message=message,
                title=title,
            )

        except Exception:
            pass

        raise ApplicationHandlerStop

    # =====================================================
    # إرسال من الخاص إلى القروبات والقنوات
    # =====================================================

    if chat.type == "private":

        try:
            chats = await __import__(
                "asyncio"
            ).to_thread(
                get_registered_chats
            )
        except Exception:
            chats = []

        if not chats:
            raise ApplicationHandlerStop

        for chat_data in chats:

            chat_id = _get_chat_id(chat_data)

            if chat_id is None:
                continue

            chat_type = _get_chat_type(chat_data)

            if chat_type not in (
                "group",
                "supergroup",
                "channel",
            ):
                continue

            title = _get_chat_title(chat_data)

            try:
                await _send_message_content(
                    bot=context.bot,
                    chat_id=chat_id,
                    source_message=message,
                    title=title,
                )

            except Exception:
                # إذا فشل الإرسال لقروب واحد،
                # نكمل لباقي القروبات.
                continue

        raise ApplicationHandlerStop

    raise ApplicationHandlerStop


# =========================================================
# حذف أوامر Slash
# =========================================================

async def delete_slash_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    يحذف أي رسالة تبدأ بـ /

    مثال:
        /هلا
        /start
        /help
        /send هلا

    لكن:
        /

    لا يتم حذفها.

    مهم:
    لا نستخدم ApplicationHandlerStop هنا حتى تستمر
    الـ handlers الأخرى بتنفيذ الأمر.
    """

    message = update.effective_message

    if not message:
        return

    text = message.text or message.caption

    if not text:
        return

    text = text.strip()

    if not text.startswith("/"):
        return

    # =====================================================
    # "/" فقط لا تحذف
    # =====================================================

    if text == "/":
        return

    # =====================================================
    # حذف الرسالة
    # =====================================================

    try:
        await message.delete()
    except Exception:
        pass

    # لا تستخدم ApplicationHandlerStop
    return
