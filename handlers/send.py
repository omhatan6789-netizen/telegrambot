import asyncio
import re

from telegram import MessageEntity, Update
from telegram.ext import ContextTypes

from handlers.developer_panel import get_registered_chats
from handlers.roles import get_rank


# =========================================================
# الإعدادات
# =========================================================

OWNER_ID = 8453977662

SEND_COMMAND_RE = re.compile(
    r"^/send(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]+))?$",
    re.IGNORECASE,
)


# =========================================================
# أدوات عامة
# =========================================================

def get_message_text(message):
    if not message:
        return ""

    if message.text is not None:
        return message.text

    if message.caption is not None:
        return message.caption

    return ""


def get_message_entities(message):
    if not message:
        return []

    if message.text is not None:
        return message.entities or []

    if message.caption is not None:
        return message.caption_entities or []

    return []


# =========================================================
# الشخص الذي تم الرد على رسالته
# =========================================================

def get_replied_user(message):
    """
    إذا كانت رسالة /send ردًا على رسالة شخص،
    يرجع الشخص صاحب الرسالة.

    إذا كانت الرسالة التي تم الرد عليها من البوت،
    لا نعتبر البوت هدفًا للمنشن.
    """

    if not message or not message.reply_to_message:
        return None

    replied_message = message.reply_to_message

    if not replied_message.from_user:
        return None

    user = replied_message.from_user

    if user.is_bot:
        return None

    return user


def get_replied_message(message):
    if not message:
        return None

    return message.reply_to_message


# =========================================================
# اسم الشخص
# =========================================================

def get_target_name(user):
    if not user:
        return ""

    if user.full_name:
        return user.full_name

    if user.first_name:
        return user.first_name

    if user.username:
        return f"@{user.username}"

    return str(user.id)


# =========================================================
# اسم القروب / القناة
# =========================================================

def get_chat_name(chat):
    if not chat:
        return ""

    if getattr(chat, "title", None):
        return chat.title

    if getattr(chat, "full_name", None):
        return chat.full_name

    if getattr(chat, "username", None):
        return f"@{chat.username}"

    return ""


# =========================================================
# معالجة المتغيرات
# =========================================================

def prepare_text_and_entities(
    text,
    entities,
    *,
    chat=None,
    replied_user=None,
):
    """
    المتغيرات:

    عند الرد على شخص:
        #الاسم = اسم الشخص
        #منشن = منشن الشخص

    بدون Reply:
        #الاسم = اسم القروب / القناة
        #منشن = اسم القروب / القناة
    """

    if not text:
        return text, list(entities or [])

    # -----------------------------------------------------
    # تحديد قيم المتغيرات
    # -----------------------------------------------------

    if replied_user:
        name_value = get_target_name(replied_user)
        mention_value = get_target_name(replied_user)
    else:
        name_value = get_chat_name(chat)
        mention_value = get_chat_name(chat)

    replacements = {
        "#الاسم": name_value,
        "#منشن": mention_value,
    }

    # -----------------------------------------------------
    # البحث عن جميع الاستبدالات
    # -----------------------------------------------------

    occurrences = []

    for variable, value in replacements.items():
        start = 0

        while True:
            position = text.find(variable, start)

            if position == -1:
                break

            occurrences.append(
                (
                    position,
                    position + len(variable),
                    value,
                    variable,
                )
            )

            start = position + len(variable)

    occurrences.sort(key=lambda item: item[0])

    # منع التداخل
    filtered_occurrences = []
    last_end = -1

    for item in occurrences:
        start, end, value, variable = item

        if start < last_end:
            continue

        filtered_occurrences.append(item)
        last_end = end

    # -----------------------------------------------------
    # لا توجد متغيرات
    # -----------------------------------------------------

    if not filtered_occurrences:
        return text, list(entities or [])

    # -----------------------------------------------------
    # بناء النص الجديد
    # -----------------------------------------------------

    parts = []
    position_map = []

    old_cursor = 0
    new_cursor = 0

    for start, end, value, variable in filtered_occurrences:

        # الجزء الذي قبل المتغير
        before = text[old_cursor:start]

        parts.append(before)

        for i in range(old_cursor, start):
            position_map.append(
                (
                    i,
                    new_cursor + (i - old_cursor),
                )
            )

        new_cursor += len(before)

        # المتغير المستبدل
        parts.append(value)

        # كل مواضع المتغير القديم تشير لبداية القيمة الجديدة
        for i in range(start, end):
            position_map.append(
                (
                    i,
                    new_cursor,
                )
            )

        new_cursor += len(value)
        old_cursor = end

    # الجزء الأخير
    tail = text[old_cursor:]

    parts.append(tail)

    for i in range(old_cursor, len(text)):
        position_map.append(
            (
                i,
                new_cursor + (i - old_cursor),
            )
        )

    new_text = "".join(parts)

    # -----------------------------------------------------
    # تحويل offsets القديمة إلى الجديدة
    # -----------------------------------------------------

    def map_offset(old_offset):
        if old_offset <= 0:
            return 0

        if old_offset >= len(text):
            return len(new_text)

        for old_pos, new_pos in position_map:
            if old_pos == old_offset:
                return new_pos

        previous = 0

        for old_pos, new_pos in position_map:
            if old_pos > old_offset:
                break

            previous = new_pos

        return previous

    # -----------------------------------------------------
    # إعادة بناء Entities
    # -----------------------------------------------------

    new_entities = []

    for entity in entities or []:
        try:
            old_start = entity.offset
            old_end = entity.offset + entity.length

            new_start = map_offset(old_start)
            new_end = map_offset(old_end)

            new_length = new_end - new_start

            if new_length <= 0:
                continue

            kwargs = {
                "type": entity.type,
                "offset": new_start,
                "length": new_length,
            }

            if entity.url is not None:
                kwargs["url"] = entity.url

            if entity.user is not None:
                kwargs["user"] = entity.user

            if entity.language is not None:
                kwargs["language"] = entity.language

            if entity.custom_emoji_id is not None:
                kwargs["custom_emoji_id"] = entity.custom_emoji_id

            try:
                new_entities.append(
                    MessageEntity(**kwargs)
                )
            except Exception:
                new_entities.append(
                    MessageEntity(
                        type=entity.type,
                        offset=new_start,
                        length=new_length,
                    )
                )

        except Exception:
            continue

    # -----------------------------------------------------
    # إضافة Text Mention حقيقي لـ #منشن
    # -----------------------------------------------------

    if replied_user and mention_value:

        search_from = 0

        while True:
            position = new_text.find(
                mention_value,
                search_from,
            )

            if position == -1:
                break

            # نتأكد أن هذا الموضع ليس Entity من نفس النوع
            already_exists = False

            for entity in new_entities:
                if (
                    entity.type == MessageEntity.TEXT_MENTION
                    and entity.offset == position
                    and entity.length == len(mention_value)
                ):
                    already_exists = True
                    break

            if not already_exists:
                new_entities.append(
                    MessageEntity(
                        type=MessageEntity.TEXT_MENTION,
                        offset=position,
                        length=len(mention_value),
                        user=replied_user,
                    )
                )

            search_from = position + len(mention_value)

    # ترتيب الـ Entities
    new_entities.sort(
        key=lambda entity: (
            entity.offset,
            entity.length,
        )
    )

    return new_text, new_entities


# =========================================================
# استخراج محتوى /send
# =========================================================

def get_send_payload(message):
    if not message:
        return None

    if not message.text:
        return None

    match = SEND_COMMAND_RE.match(
        message.text.strip()
    )

    if not match:
        return None

    payload = match.group(1)

    if payload is None:
        return ""

    return payload.strip()


# =========================================================
# إرسال محتوى الرسالة
# =========================================================

async def send_message_content(
    bot,
    target_chat_id,
    source_message,
    text,
    entities,
    *,
    reply_to_message_id=None,
):
    # -----------------------------------------------------
    # نص
    # -----------------------------------------------------

    if source_message.text is not None:
        return await bot.send_message(
            chat_id=target_chat_id,
            text=text or " ",
            entities=entities or None,
            reply_to_message_id=reply_to_message_id,
            allow_sending_without_reply=True,
        )

    # -----------------------------------------------------
    # صورة
    # -----------------------------------------------------

    if source_message.photo:
        return await bot.send_photo(
            chat_id=target_chat_id,
            photo=source_message.photo[-1].file_id,
            caption=text or None,
            caption_entities=entities or None,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # فيديو
    # -----------------------------------------------------

    if source_message.video:
        return await bot.send_video(
            chat_id=target_chat_id,
            video=source_message.video.file_id,
            caption=text or None,
            caption_entities=entities or None,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # GIF / Animation
    # -----------------------------------------------------

    if source_message.animation:
        return await bot.send_animation(
            chat_id=target_chat_id,
            animation=source_message.animation.file_id,
            caption=text or None,
            caption_entities=entities or None,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Audio
    # -----------------------------------------------------

    if source_message.audio:
        return await bot.send_audio(
            chat_id=target_chat_id,
            audio=source_message.audio.file_id,
            caption=text or None,
            caption_entities=entities or None,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Voice
    # -----------------------------------------------------

    if source_message.voice:
        return await bot.send_voice(
            chat_id=target_chat_id,
            voice=source_message.voice.file_id,
            caption=text or None,
            caption_entities=entities or None,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Document
    # -----------------------------------------------------

    if source_message.document:
        return await bot.send_document(
            chat_id=target_chat_id,
            document=source_message.document.file_id,
            caption=text or None,
            caption_entities=entities or None,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Sticker
    # -----------------------------------------------------

    if source_message.sticker:
        return await bot.send_sticker(
            chat_id=target_chat_id,
            sticker=source_message.sticker.file_id,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Video Note
    # -----------------------------------------------------

    if source_message.video_note:
        return await bot.send_video_note(
            chat_id=target_chat_id,
            video_note=source_message.video_note.file_id,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Contact
    # -----------------------------------------------------

    if source_message.contact:
        return await bot.send_contact(
            chat_id=target_chat_id,
            phone_number=source_message.contact.phone_number,
            first_name=source_message.contact.first_name,
            last_name=source_message.contact.last_name,
            vcard=source_message.contact.vcard,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Location
    # -----------------------------------------------------

    if source_message.location:
        return await bot.send_location(
            chat_id=target_chat_id,
            latitude=source_message.location.latitude,
            longitude=source_message.location.longitude,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Venue
    # -----------------------------------------------------

    if source_message.venue:
        return await bot.send_venue(
            chat_id=target_chat_id,
            latitude=source_message.venue.location.latitude,
            longitude=source_message.venue.location.longitude,
            title=source_message.venue.title,
            address=source_message.venue.address,
            foursquare_id=source_message.venue.foursquare_id,
            foursquare_type=source_message.venue.foursquare_type,
            google_place_id=source_message.venue.google_place_id,
            google_place_type=source_message.venue.google_place_type,
            reply_to_message_id=reply_to_message_id,
        )

    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    if text:
        return await bot.send_message(
            chat_id=target_chat_id,
            text=text,
            entities=entities or None,
            reply_to_message_id=reply_to_message_id,
            allow_sending_without_reply=True,
        )

    return None


# =========================================================
# /send
# =========================================================

async def send_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    user = update.effective_user

    if not user:
        return

    # =====================================================
    # الصلاحيات
    # =====================================================

    # -----------------------------------------------------
    # الخاص:
    # المالك الأساسي فقط
    # -----------------------------------------------------

    if message.chat.type == "private":

        if user.id != OWNER_ID:
            return

    # -----------------------------------------------------
    # القروبات والقنوات:
    # ادمن اساسي وفوق
    # -----------------------------------------------------

    else:

        rank = get_rank(user.id)

        allowed_ranks = {
            "ادمن اساسي",
            "نائب المالك",
            "المالك",
            "Dev",
        }

        if rank not in allowed_ranks:
            return

    # =====================================================
    # استخراج محتوى /send
    # =====================================================

    payload = get_send_payload(message)

    if payload is None:
        return

    # =====================================================
    # تحديد النص والـ Entities
    # =====================================================

    if message.text is not None:

        original_content = payload

        original_entities = []

        payload_start = message.text.find(payload)

        if payload and payload_start >= 0:

            for entity in message.entities or []:

                entity_start = entity.offset
                entity_end = (
                    entity.offset
                    + entity.length
                )

                # تجاهل entities الموجودة داخل /send
                if entity_start < payload_start:
                    continue

                # تجاهل entity التي تتجاوز النص
                if entity_end > len(message.text):
                    continue

                new_offset = (
                    entity_start
                    - payload_start
                )

                if new_offset < 0:
                    continue

                try:
                    original_entities.append(
                        MessageEntity(
                            type=entity.type,
                            offset=new_offset,
                            length=entity.length,
                            url=entity.url,
                            user=entity.user,
                            language=entity.language,
                            custom_emoji_id=entity.custom_emoji_id,
                        )
                    )
                except Exception:
                    pass

    else:

        original_content = (
            message.caption or ""
        )

        original_entities = (
            message.caption_entities or []
        )

    # =====================================================
    # حذف رسالة /send
    # =====================================================

    try:
        await message.delete()
    except Exception:
        pass

    # =====================================================
    # لا يوجد محتوى
    # =====================================================

    has_media = any(
        (
            message.photo,
            message.video,
            message.animation,
            message.audio,
            message.voice,
            message.document,
            message.sticker,
            message.video_note,
            message.contact,
            message.location,
            message.venue,
        )
    )

    if not original_content and not has_media:
        return

    # =====================================================
    # الشخص الذي تم الرد عليه
    # =====================================================

    replied_message = get_replied_message(
        message
    )

    replied_user = get_replied_user(
        message
    )

    # =====================================================
    # القروب / السوبرقروب / القناة
    # =====================================================

    if message.chat.type in (
        "group",
        "supergroup",
        "channel",
    ):

        final_text, final_entities = (
            prepare_text_and_entities(
                original_content,
                original_entities,
                chat=message.chat,
                replied_user=replied_user,
            )
        )

        reply_to_message_id = None

        if replied_message:
            reply_to_message_id = (
                replied_message.message_id
            )

        # -------------------------------------------------
        # إرسال مع Reply
        # -------------------------------------------------

        try:

            await send_message_content(
                context.bot,
                message.chat.id,
                message,
                final_text,
                final_entities,
                reply_to_message_id=(
                    reply_to_message_id
                ),
            )

        except Exception:

            # إذا فشل الـ Reply لأي سبب،
            # نرسل بدون Reply.
            try:

                await send_message_content(
                    context.bot,
                    message.chat.id,
                    message,
                    final_text,
                    final_entities,
                    reply_to_message_id=None,
                )

            except Exception:
                pass

        return

    # =====================================================
    # الخاص
    # =====================================================

    if message.chat.type == "private":

        # -------------------------------------------------
        # استخدام نظام التسجيل الموجود أصلًا
        # في developer_panel.py
        # -------------------------------------------------

        try:

            registered_chats = (
                await asyncio.to_thread(
                    get_registered_chats
                )
            )

        except Exception:

            registered_chats = []

        # -------------------------------------------------
        # الإرسال لكل القروبات والقنوات
        # -------------------------------------------------

        for row in registered_chats:

            try:

                chat_id = row[0]
                chat_type = row[1]
                title = row[2]
                username = row[3]

                # -------------------------------------------------
                # كائن بسيط لاستخدام نفس دالة المتغيرات
                # -------------------------------------------------

                class RegisteredChat:

                    def __init__(
                        self,
                        title=None,
                        username=None,
                        chat_type=None,
                    ):
                        self.title = title
                        self.username = username
                        self.type = chat_type
                        self.full_name = title

                target_chat = RegisteredChat(
                    title=title,
                    username=username,
                    chat_type=chat_type,
                )

                # -------------------------------------------------
                # #الاسم و #منشن
                #
                # إذا كان /send في الخاص رداً على شخص:
                # يتم استخدام الشخص المردود عليه.
                #
                # وإلا:
                # يتم استخدام اسم القروب/القناة.
                # -------------------------------------------------

                final_text, final_entities = (
                    prepare_text_and_entities(
                        original_content,
                        original_entities,
                        chat=target_chat,
                        replied_user=replied_user,
                    )
                )

                # -------------------------------------------------
                # لا نستخدم Reply هنا
                #
                # لأن message_id الخاص برسالة الخاص
                # غير موجود داخل القروب المستهدف.
                # -------------------------------------------------

                await send_message_content(
                    context.bot,
                    chat_id,
                    message,
                    final_text,
                    final_entities,
                    reply_to_message_id=None,
                )

            except Exception:
                # إذا فشل الإرسال لقروب/قناة معينة،
                # نستمر للباقي.
                continue

        return


# =========================================================
# حذف أوامر Slash
# =========================================================

async def delete_slash_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    حذف أي رسالة تبدأ بـ /

    أمثلة:
        /start
        /help
        /هلا
        /send هلا

    لكن:
        /
    لا يتم حذفها.

    مهم:
    لا نستخدم ApplicationHandlerStop هنا،
    حتى تستمر الأوامر بالعمل.
    """

    message = update.effective_message

    if not message:
        return

    text = message.text

    if not text:
        return

    if not text.startswith("/"):
        return

    # "/" فقط لا نحذفه
    if text == "/":
        return

    try:
        await message.delete()
    except Exception:
        pass
