import asyncio
import re

from html import escape

from telegram import (
    Update,
    MessageEntity,
)
from telegram.ext import ContextTypes

from handlers.developer_panel import get_registered_chats


# =========================================================
# إعدادات
# =========================================================

SEND_COMMAND_RE = re.compile(
    r"^/send(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]+))?$",
    re.IGNORECASE,
)


# =========================================================
# أدوات عامة
# =========================================================

def get_message_text(message):
    """
    يرجع النص أو الكابتشن الموجود في الرسالة.
    """
    if not message:
        return ""

    if message.text is not None:
        return message.text

    if message.caption is not None:
        return message.caption

    return ""


def get_message_entities(message):
    """
    يرجع الـ entities الخاصة بالنص أو الكابتشن.
    """
    if not message:
        return []

    if message.text is not None:
        return message.entities or []

    if message.caption is not None:
        return message.caption_entities or []

    return []


def get_replied_user(message):
    """
    إذا كانت رسالة /send ردًا على رسالة شخص،
    يرجع الشخص صاحب الرسالة التي تم الرد عليها.

    لا يرجع البوت كهدف منشن إذا كان الرد على رسالة البوت نفسه.
    """
    if not message or not message.reply_to_message:
        return None

    replied_message = message.reply_to_message

    if not replied_message.from_user:
        return None

    user = replied_message.from_user

    # لا نعتبر البوت هدفًا لـ #منشن
    if user.is_bot:
        return None

    return user


def get_replied_message(message):
    """
    يرجع الرسالة التي تم عمل Reply عليها.
    """
    if not message:
        return None

    return message.reply_to_message


def get_target_name(user):
    """
    اسم الشخص المستخدم في #الاسم.
    """
    if not user:
        return None

    if user.full_name:
        return user.full_name

    if user.first_name:
        return user.first_name

    if user.username:
        return f"@{user.username}"

    return str(user.id)


def build_mention_entity(text, offset, user):
    """
    ينشئ Text Mention حقيقي للشخص.
    """
    if not user:
        return None

    if offset < 0 or offset >= len(text):
        return None

    # نأخذ الكلمة/الاسم الموجود مكان #منشن
    end = offset

    while end < len(text) and not text[end].isspace():
        end += 1

    length = end - offset

    if length <= 0:
        return None

    return MessageEntity(
        type=MessageEntity.TEXT_MENTION,
        offset=offset,
        length=length,
        user=user,
    )


def replace_variables(
    text,
    entities,
    *,
    chat=None,
    replied_user=None,
):
    """
    استبدال:
        #الاسم
        #منشن

    عند وجود Reply على شخص:
        #الاسم = اسم الشخص
        #منشن = منشن الشخص

    عند عدم وجود Reply:
        #الاسم = اسم القروب/القناة
        #منشن = اسم القروب/القناة

    ويرجع:
        new_text
        new_entities
    """

    if not text:
        return text, []

    # -----------------------------------------------------
    # تحديد قيم #الاسم
    # -----------------------------------------------------

    if replied_user:
        name_value = get_target_name(replied_user)
    else:
        if chat:
            name_value = chat.title or chat.full_name or chat.username or ""
        else:
            name_value = ""

    # -----------------------------------------------------
    # استبدال #الاسم
    # -----------------------------------------------------

    text = text.replace("#الاسم", name_value)

    # -----------------------------------------------------
    # #منشن
    # -----------------------------------------------------
    #
    # إذا كان عندنا شخص مَرْدُود عليه:
    # نخلي #منشن مكانه اسم الشخص ونضيف Text Mention entity.
    #
    # إذا ما عندنا شخص:
    # نستخدم اسم القروب/القناة.
    # -----------------------------------------------------

    mention_user = replied_user

    if mention_user:
        mention_value = get_target_name(mention_user)
    else:
        mention_value = (
            chat.title
            if chat and chat.title
            else (
                chat.full_name
                if chat and chat.full_name
                else (
                    f"@{chat.username}"
                    if chat and chat.username
                    else ""
                )
            )
        )

    mention_positions = []

    search_from = 0

    while True:
        pos = text.find("#منشن", search_from)

        if pos == -1:
            break

        mention_positions.append(pos)
        search_from = pos + len("#منشن")

    if mention_positions:
        # نستبدل من الأخير للأول حتى لا تتغير offsets
        for pos in reversed(mention_positions):
            text = (
                text[:pos]
                + mention_value
                + text[pos + len("#منشن"):]
            )

    # -----------------------------------------------------
    # إعادة بناء الـ entities
    # -----------------------------------------------------
    #
    # لأن استبدال النص يغير offsets،
    # نعيد إنشاء الـ entities بناءً على النص الجديد.
    #
    # نستخدم entities الأصلية قدر الإمكان.
    # -----------------------------------------------------

    new_entities = []

    # إذا ما فيه entities أصلًا
    if not entities:
        if mention_user:
            # نحاول تحديد مواقع الاسم الناتج عن #منشن.
            # نبحث عن الاسم داخل النص.
            if mention_value:
                start = 0

                while True:
                    pos = text.find(mention_value, start)

                    if pos == -1:
                        break

                    new_entities.append(
                        MessageEntity(
                            type=MessageEntity.TEXT_MENTION,
                            offset=pos,
                            length=len(mention_value),
                            user=mention_user,
                        )
                    )

                    start = pos + len(mention_value)

        return text, new_entities

    # -----------------------------------------------------
    # تحويل النص القديم والجديد بطريقة تحفظ entities
    # -----------------------------------------------------

    # هنا نعيد معالجة الـ entities مع فروقات المتغيرات.
    #
    # المتغيرات:
    # #الاسم
    # #منشن
    #
    # إذا كانت entity تقع بعد متغير تم تغييره،
    # نعدل offset الخاص بها.
    # -----------------------------------------------------

    original_text = None

    # لا نستطيع معرفة النص الأصلي من entity وحدها،
    # لذلك نعتمد على message entities كما وصلت.
    #
    # نحسب التغييرات من النص قبل الاستبدال من جديد.
    #
    # يتم استدعاء هذه الدالة بالنص النهائي حاليًا،
    # لذلك نضيف فقط Text Mention الجديد.
    #
    # Telegram formatting الموجود في النص العادي
    # يبقى محفوظًا في أغلب الحالات عندما لا توجد
    # تغييرات قبل الـ entity.
    # -----------------------------------------------------

    for entity in entities:
        try:
            new_entities.append(
                MessageEntity(
                    type=entity.type,
                    offset=entity.offset,
                    length=entity.length,
                    url=entity.url,
                    user=entity.user,
                    language=entity.language,
                    custom_emoji_id=entity.custom_emoji_id,
                )
            )
        except TypeError:
            # توافق مع إصدارات PTB المختلفة
            try:
                new_entities.append(
                    MessageEntity(
                        type=entity.type,
                        offset=entity.offset,
                        length=entity.length,
                        url=entity.url,
                        user=entity.user,
                        language=entity.language,
                        custom_emoji_id=entity.custom_emoji_id,
                    )
                )
            except Exception:
                pass

    # -----------------------------------------------------
    # إضافة Text Mention لـ #منشن
    # -----------------------------------------------------

    if mention_user and mention_value:
        start = 0

        while True:
            pos = text.find(mention_value, start)

            if pos == -1:
                break

            # نتأكد أنه ليس entity موجودة مسبقًا
            already_exists = False

            for entity in new_entities:
                if (
                    entity.type == MessageEntity.TEXT_MENTION
                    and entity.offset == pos
                    and entity.length == len(mention_value)
                ):
                    already_exists = True
                    break

            if not already_exists:
                new_entities.append(
                    MessageEntity(
                        type=MessageEntity.TEXT_MENTION,
                        offset=pos,
                        length=len(mention_value),
                        user=mention_user,
                    )
                )

            start = pos + len(mention_value)

    return text, new_entities


# =========================================================
# معالجة المتغيرات بطريقة أدق
# =========================================================

def prepare_text_and_entities(
    text,
    entities,
    *,
    chat,
    replied_user,
):
    """
    معالجة النص مع الحفاظ على تنسيقات Telegram قدر الإمكان.

    يتم تنفيذ الاستبدالات مع تعديل offsets للـ entities.
    """

    if not text:
        return text, []

    replacements = {}

    # -----------------------------------------------------
    # #الاسم
    # -----------------------------------------------------

    if replied_user:
        name_value = get_target_name(replied_user)
    else:
        name_value = (
            chat.title
            or chat.full_name
            or (f"@{chat.username}" if chat.username else "")
            if chat
            else ""
        )

    replacements["#الاسم"] = name_value

    # -----------------------------------------------------
    # #منشن
    # -----------------------------------------------------

    if replied_user:
        mention_value = get_target_name(replied_user)
    else:
        mention_value = (
            chat.title
            or chat.full_name
            or (f"@{chat.username}" if chat.username else "")
            if chat
            else ""
        )

    replacements["#منشن"] = mention_value

    # -----------------------------------------------------
    # إنشاء خريطة للتغييرات
    # -----------------------------------------------------

    occurrences = []

    for variable, value in replacements.items():
        if value is None:
            value = ""

        start = 0

        while True:
            pos = text.find(variable, start)

            if pos == -1:
                break

            occurrences.append(
                (
                    pos,
                    pos + len(variable),
                    value,
                    variable,
                )
            )

            start = pos + len(variable)

    # ترتيبها
    occurrences.sort(key=lambda x: x[0])

    # منع التداخل
    filtered = []
    last_end = -1

    for item in occurrences:
        start, end, value, variable = item

        if start < last_end:
            continue

        filtered.append(item)
        last_end = end

    if not filtered:
        return text, list(entities or [])

    # -----------------------------------------------------
    # بناء النص الجديد
    # -----------------------------------------------------

    new_text_parts = []
    cursor = 0

    # خريطة:
    # old position -> new position
    #
    # نستخدمها لتعديل offsets.
    position_map = []

    new_position = 0

    for start, end, value, variable in filtered:
        # الجزء قبل المتغير
        before = text[cursor:start]

        new_text_parts.append(before)

        for i in range(cursor, start):
            position_map.append(
                (
                    i,
                    new_position + (i - cursor)
                )
            )

        new_position += len(before)

        # قيمة المتغير
        new_text_parts.append(value)

        # كل موضع داخل المتغير يشير إلى بداية القيمة الجديدة
        for i in range(start, end):
            position_map.append(
                (
                    i,
                    new_position
                )
            )

        new_position += len(value)

        cursor = end

    # الجزء الأخير
    tail = text[cursor:]

    new_text_parts.append(tail)

    for i in range(cursor, len(text)):
        position_map.append(
            (
                i,
                new_position + (i - cursor)
            )
        )

    new_text = "".join(new_text_parts)

    # -----------------------------------------------------
    # دالة تحويل offset
    # -----------------------------------------------------

    def map_offset(old_offset):
        if old_offset <= 0:
            return 0

        if old_offset >= len(text):
            return len(new_text)

        # إذا كان offset عند بداية متغير
        for old_pos, new_pos in position_map:
            if old_pos == old_offset:
                return new_pos

        # أقرب موضع قبله
        best = 0

        for old_pos, new_pos in position_map:
            if old_pos <= old_offset:
                best = new_pos
            else:
                break

        return best

    # -----------------------------------------------------
    # إعادة بناء entities
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
                # fallback
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
    # إضافة Text Mention للمتغير #منشن
    # -----------------------------------------------------

    if replied_user:
        search_from = 0

        while True:
            pos = new_text.find(mention_value, search_from)

            if pos == -1:
                break

            # نضيف المنشن الحقيقي
            new_entities.append(
                MessageEntity(
                    type=MessageEntity.TEXT_MENTION,
                    offset=pos,
                    length=len(mention_value),
                    user=replied_user,
                )
            )

            search_from = pos + len(mention_value)

    # ترتيب entities
    new_entities.sort(
        key=lambda e: (e.offset, e.length)
    )

    return new_text, new_entities


# =========================================================
# استخراج محتوى /send
# =========================================================

def get_send_payload(message):
    """
    يرجع النص بعد /send.
    """

    if not message:
        return None

    text = message.text

    if text is None:
        return None

    match = SEND_COMMAND_RE.match(text.strip())

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
    """
    إرسال النص/الوسائط الموجودة في رسالة /send.

    source_message هنا هي رسالة المستخدم التي كتب فيها /send.
    """

    # -----------------------------------------------------
    # رسالة نصية
    # -----------------------------------------------------

    if source_message.text is not None:
        return await bot.send_message(
            chat_id=target_chat_id,
            text=text,
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
    # Animation / GIF
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
    # إذا لم تكن الرسالة من الأنواع السابقة
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

    # -----------------------------------------------------
    # التأكد أن الرسالة /send
    # -----------------------------------------------------

    payload = get_send_payload(message)

    if payload is None:
        return

    # -----------------------------------------------------
    # النص الأساسي
    # -----------------------------------------------------

    source_text = message.text or ""

    # إذا كان /send نص
    #
    # payload يحتوي النص بعد /send
    #
    # لكن إذا كانت الرسالة نفسها عبارة عن وسائط مع caption
    # نستخدم caption.
    # -----------------------------------------------------

    if message.text is not None:
        original_content = payload
        original_entities = message.entities or []

        # entities الموجودة في الرسالة تشمل /send نفسه،
        # لذلك نحتاج أخذ entities الموجودة بعد بداية payload.
        command_match = SEND_COMMAND_RE.match(
            source_text.strip()
        )

        if command_match:
            command_part = command_match.group(0)

            # نحاول تحديد بداية payload في النص الأصلي
            payload_start = source_text.find(payload)

            if payload_start >= 0:
                adjusted_entities = []

                for entity in message.entities or []:
                    entity_start = entity.offset
                    entity_end = entity.offset + entity.length

                    if entity_start < payload_start:
                        continue

                    new_offset = entity_start - payload_start

                    if new_offset < 0:
                        continue

                    adjusted_entities.append(
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

                original_entities = adjusted_entities

    else:
        original_content = message.caption or ""
        original_entities = message.caption_entities or []

    # -----------------------------------------------------
    # حذف رسالة /send
    # -----------------------------------------------------

    try:
        await message.delete()
    except Exception:
        pass

    # -----------------------------------------------------
    # إذا ما فيه محتوى
    # -----------------------------------------------------

    if not original_content and not (
        message.photo
        or message.video
        or message.animation
        or message.audio
        or message.voice
        or message.document
        or message.sticker
        or message.video_note
        or message.contact
        or message.location
        or message.venue
    ):
        return

    # -----------------------------------------------------
    # هل فيه Reply على شخص؟
    # -----------------------------------------------------

    replied_message = get_replied_message(message)
    replied_user = get_replied_user(message)

    # -----------------------------------------------------
    # المجموعة / السوبرقروب / القناة
    # -----------------------------------------------------

    if message.chat.type in (
        "group",
        "supergroup",
        "channel",
    ):
        target_chat_id = message.chat.id

        final_text, final_entities = prepare_text_and_entities(
            original_content,
            original_entities,
            chat=message.chat,
            replied_user=replied_user,
        )

        # -------------------------------------------------
        # إذا كان المستخدم راد على رسالة شخص
        # نخلي البوت يرد على نفس الرسالة
        # -------------------------------------------------

        reply_to_message_id = None

        if replied_message:
            reply_to_message_id = replied_message.message_id

        try:
            await send_message_content(
                context.bot,
                target_chat_id,
                message,
                final_text,
                final_entities,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception:
            # في حال فشل الـ Reply لأي سبب،
            # نحاول إرسال الرسالة بدون Reply.
            try:
                await send_message_content(
                    context.bot,
                    target_chat_id,
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
        # جلب القروبات والقنوات من النظام الموجود
        # في developer_panel.py
        # -------------------------------------------------

        try:
            registered_chats = await asyncio.to_thread(
                get_registered_chats
            )
        except Exception:
            registered_chats = []

        # -------------------------------------------------
        # إرسال لكل القروبات والقنوات المسجلة
        # -------------------------------------------------

        for row in registered_chats:
            try:
                chat_id = row[0]
                chat_type = row[1]

                # العنوان الموجود في سجل المطور
                title = row[2]
                username = row[3]

                # إنشاء كائن بسيط للقناة/القروب
                #
                # get_registered_chats يرجع بيانات قاعدة البيانات
                # وليس telegram.Chat.
                #
                # لذلك نستخدم البيانات مباشرة للمتغيرات.
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
                # إذا كانت /send في الخاص ومردود عليها على شخص،
                # #الاسم و#منشن يشيران لذلك الشخص.
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
                # لا نرسل Reply في القروبات من رسالة خاصة
                #
                # لأن message_id الخاص برسالة الخاص لا يوجد
                # داخل القروب المستهدف.
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
                # إذا كان البوت لا يستطيع الإرسال لقروب/قناة معينة
                # نكمل للباقي.
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
    حتى تستمر أوامر Telegram بالعمل بعد حذف الرسالة.
    """

    message = update.effective_message

    if not message:
        return

    text = message.text

    if not text:
        return

    # يجب أن تبدأ بـ /
    if not text.startswith("/"):
        return

    # "/" فقط لا نحذفه
    if text == "/":
        return

    # حذف الرسالة
    try:
        await message.delete()
    except Exception:
        pass
