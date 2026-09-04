import json
import re

from telegram import Update, MessageEntity
from telegram.ext import ContextTypes

from permissions import is_admin
from database import connect


# =========================================================
# الجلسات
# =========================================================

add_reply_sessions = {}
edit_reply_sessions = {}
delete_reply_sessions = {}

add_special_reply_sessions = {}
edit_special_reply_sessions = {}
delete_special_reply_sessions = {}


# =========================================================
# الكاش
# =========================================================

replies_cache = {}
special_replies_cache = {}


# =========================================================
# إنشاء أعمدة الإيموجي المميز
# =========================================================

def ensure_entities_columns():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            ALTER TABLE replies
            ADD COLUMN IF NOT EXISTS entities TEXT
            """
        )

        cur.execute(
            """
            ALTER TABLE special_replies
            ADD COLUMN IF NOT EXISTS entities TEXT
            """
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


# =========================================================
# تحويل MessageEntity إلى JSON
# =========================================================

def entities_to_json(entities):
    if not entities:
        return "[]"

    result = []

    for entity in entities:
        try:
            result.append(entity.to_dict())
        except Exception:
            pass

    return json.dumps(
        result,
        ensure_ascii=False
    )


# =========================================================
# تحويل JSON إلى MessageEntity
# =========================================================

def json_to_entities(data):
    if not data:
        return []

    try:
        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, list):
            return []

        result = []

        for entity_data in data:
            try:
                entity = MessageEntity.de_json(
                    entity_data,
                    None
                )

                if entity:
                    result.append(entity)

            except Exception as e:
                print(
                    "❌ خطأ في تحويل entity:",
                    e
                )

        return result

    except Exception as e:
        print(
            "❌ خطأ في json_to_entities:",
            e
        )
        return []


# =========================================================
# UTF-16
# Telegram offsets تستخدم UTF-16
# =========================================================

def utf16_len(text):
    return len(
        text.encode(
            "utf-16-le"
        )
    ) // 2


# =========================================================
# استبدال #الاسم مع المحافظة على entities
# =========================================================

def replace_text_and_entities(
    text,
    entities,
    replacements
):
    if not text:
        return text, entities or []

    if not replacements:
        return text, entities or []

    old_text = text

    # -----------------------------------------------------
    # نبني النص الجديد مع معرفة مكان كل جزء
    # -----------------------------------------------------

    pieces = []
    cursor = 0

    matches = list(
        re.finditer(
            r"#([^\s#]+)",
            old_text
        )
    )

    replacements_by_start = {}

    for match in matches:
        key = match.group(1)

        if key in replacements:
            replacements_by_start[match.start()] = (
                match.end(),
                str(replacements[key])
            )

    if not replacements_by_start:
        return old_text, entities or []

    new_text = ""
    mapping = []

    old_pos = 0
    new_pos = 0

    for match in matches:

        start = match.start()
        end = match.end()

        if start not in replacements_by_start:
            continue

        replacement_end, replacement = replacements_by_start[start]

        # النص قبل المتغير
        before = old_text[old_pos:start]

        new_text += before

        old_segment_len = utf16_len(
            old_text[old_pos:start]
        )

        new_segment_len = utf16_len(
            before
        )

        mapping.append(
            (
                old_pos,
                start,
                new_pos,
                new_pos + new_segment_len
            )
        )

        new_pos += new_segment_len

        # النص البديل
        new_text += replacement

        replacement_len = utf16_len(
            replacement
        )

        old_variable_len = utf16_len(
            old_text[start:end]
        )

        mapping.append(
            (
                start,
                end,
                new_pos,
                new_pos + replacement_len
            )
        )

        new_pos += replacement_len

        old_pos = end

    # الباقي
    if old_pos < len(old_text):

        before = old_text[old_pos:]

        new_text += before

        before_len = utf16_len(
            before
        )

        mapping.append(
            (
                old_pos,
                len(old_text),
                new_pos,
                new_pos + before_len
            )
        )

        new_pos += before_len

    # -----------------------------------------------------
    # تحويل offsets الخاصة بالـ entities
    # -----------------------------------------------------

    new_entities = []

    for entity in entities or []:

        old_start = entity.offset
        old_end = entity.offset + entity.length

        mapped_start = None
        mapped_end = None

        for (
            segment_old_start,
            segment_old_end,
            segment_new_start,
            segment_new_end
        ) in mapping:

            if (
                old_start >= segment_old_start
                and old_start <= segment_old_end
            ):
                ratio = (
                    old_start - segment_old_start
                )

                old_segment_length = (
                    segment_old_end
                    - segment_old_start
                )

                new_segment_length = (
                    segment_new_end
                    - segment_new_start
                )

                if old_segment_length == 0:
                    mapped_start = segment_new_start
                else:
                    mapped_start = (
                        segment_new_start
                        + ratio
                    )

                break

        for (
            segment_old_start,
            segment_old_end,
            segment_new_start,
            segment_new_end
        ) in mapping:

            if (
                old_end >= segment_old_start
                and old_end <= segment_old_end
            ):
                ratio = (
                    old_end - segment_old_start
                )

                old_segment_length = (
                    segment_old_end
                    - segment_old_start
                )

                new_segment_length = (
                    segment_new_end
                    - segment_new_start
                )

                if old_segment_length == 0:
                    mapped_end = segment_new_end
                else:
                    mapped_end = (
                        segment_new_start
                        + ratio
                    )

                break

        if mapped_start is None:
            mapped_start = old_start

        if mapped_end is None:
            mapped_end = old_end

        new_length = mapped_end - mapped_start

        if new_length <= 0:
            continue

        try:
            data = entity.to_dict()

            data["offset"] = int(
                mapped_start
            )

            data["length"] = int(
                new_length
            )

            new_entity = MessageEntity.de_json(
                data,
                None
            )

            if new_entity:
                new_entities.append(
                    new_entity
                )

        except Exception as e:
            print(
                "❌ خطأ في إعادة بناء entity:",
                e
            )

    return new_text, new_entities


# =========================================================
# تحميل الردود
# =========================================================

def load_replies_cache():

    global replies_cache
    global special_replies_cache

    ensure_entities_columns()

    conn = connect()
    cur = conn.cursor()

    try:

        # -------------------------------------------------
        # الردود العادية
        # -------------------------------------------------

        cur.execute(
            """
            SELECT
                name,
                text,
                type,
                caption,
                entities
            FROM replies
            """
        )

        rows = cur.fetchall()

        replies_cache = {}

        for row in rows:

            name = row[0]
            text = row[1]
            reply_type = row[2]
            caption = row[3]
            entities = row[4]

            replies_cache[name] = (
                text,
                reply_type,
                caption,
                entities
            )

        # -------------------------------------------------
        # الردود الخاصة
        # -------------------------------------------------

        cur.execute(
            """
            SELECT
                name,
                text,
                type,
                caption,
                entities
            FROM special_replies
            """
        )

        rows = cur.fetchall()

        special_replies_cache = {}

        for row in rows:

            special_replies_cache[row[0]] = (
                row[1],
                row[2],
                row[3],
                row[4]
            )

    finally:
        cur.close()
        conn.close()


# =========================================================
# استخراج محتوى الرسالة
# =========================================================

def extract_reply_content(message):

    # -----------------------------------------------------
    # رسالة نصية
    # -----------------------------------------------------

    if message.text is not None:

        entities = (
            message.entities
            or []
        )

        print(
            "========== EXTRACT TEXT =========="
        )
        print(
            "TEXT:",
            repr(message.text)
        )
        print(
            "ENTITIES:",
            entities
        )

        for entity in entities:
            print(
                "TYPE:",
                entity.type,
                "OFFSET:",
                entity.offset,
                "LENGTH:",
                entity.length,
                "CUSTOM_EMOJI_ID:",
                entity.custom_emoji_id
            )

        print(
            "=================================="
        )

        return (
            message.text,
            "text",
            None,
            entities
        )

    # -----------------------------------------------------
    # صورة
    # -----------------------------------------------------

    if message.photo:

        caption = (
            message.caption
            or ""
        )

        entities = (
            message.caption_entities
            or []
        )

        return (
            message.photo[-1].file_id,
            "photo",
            caption,
            entities
        )

    # -----------------------------------------------------
    # فيديو
    # -----------------------------------------------------

    if message.video:

        caption = (
            message.caption
            or ""
        )

        entities = (
            message.caption_entities
            or []
        )

        return (
            message.video.file_id,
            "video",
            caption,
            entities
        )

    # -----------------------------------------------------
    # GIF
    # -----------------------------------------------------

    if message.animation:

        caption = (
            message.caption
            or ""
        )

        entities = (
            message.caption_entities
            or []
        )

        return (
            message.animation.file_id,
            "animation",
            caption,
            entities
        )

    # -----------------------------------------------------
    # ملف
    # -----------------------------------------------------

    if message.document:

        caption = (
            message.caption
            or ""
        )

        entities = (
            message.caption_entities
            or []
        )

        return (
            message.document.file_id,
            "document",
            caption,
            entities
        )

    # -----------------------------------------------------
    # صوت
    # -----------------------------------------------------

    if message.audio:

        caption = (
            message.caption
            or ""
        )

        entities = (
            message.caption_entities
            or []
        )

        return (
            message.audio.file_id,
            "audio",
            caption,
            entities
        )

    # -----------------------------------------------------
    # فيديو نوت
    # -----------------------------------------------------

    if message.video_note:

        return (
            message.video_note.file_id,
            "video_note",
            None,
            []
        )

    return None


# =========================================================
# حفظ الرد
# =========================================================

def save_reply(
    name,
    content,
    reply_type,
    caption,
    entities,
    special=False
):

    ensure_entities_columns()

    conn = connect()
    cur = conn.cursor()

    try:

        table = (
            "special_replies"
            if special
            else "replies"
        )

        entities_json = (
            entities_to_json(entities)
        )

        query = f"""
            INSERT INTO {table}
            (
                name,
                text,
                type,
                caption,
                entities
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name)
            DO UPDATE SET
                text = excluded.text,
                type = excluded.type,
                caption = excluded.caption,
                entities = excluded.entities
        """

        cur.execute(
            query,
            (
                name,
                content,
                reply_type,
                caption,
                entities_json
            )
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()

    load_replies_cache()


# =========================================================
# إرسال الرد
# =========================================================

async def send_reply_content(
    bot,
    chat_id,
    content,
    reply_type,
    caption=None,
    entities=None
):

    entities = entities or []

    # -----------------------------------------------------
    # طباعة مهمة للتأكد من Custom Emoji
    # -----------------------------------------------------

    print(
        "========== SEND REPLY =========="
    )

    print(
        "TYPE:",
        reply_type
    )

    print(
        "CONTENT:",
        repr(content)
    )

    print(
        "CAPTION:",
        repr(caption)
    )

    print(
        "ENTITIES:",
        entities
    )

    for entity in entities:
        print(
            "TYPE:",
            entity.type,
            "OFFSET:",
            entity.offset,
            "LENGTH:",
            entity.length,
            "CUSTOM_EMOJI_ID:",
            entity.custom_emoji_id
        )

    print(
        "================================"
    )

    # -----------------------------------------------------
    # نص
    # -----------------------------------------------------

    if reply_type == "text":

        await bot.send_message(
            chat_id=chat_id,
            text=content,
            entities=entities
        )

        return

    # -----------------------------------------------------
    # صورة
    # -----------------------------------------------------

    if reply_type == "photo":

        await bot.send_photo(
            chat_id=chat_id,
            photo=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # -----------------------------------------------------
    # فيديو
    # -----------------------------------------------------

    if reply_type == "video":

        await bot.send_video(
            chat_id=chat_id,
            video=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # -----------------------------------------------------
    # GIF
    # -----------------------------------------------------

    if reply_type == "animation":

        await bot.send_animation(
            chat_id=chat_id,
            animation=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # -----------------------------------------------------
    # ملف
    # -----------------------------------------------------

    if reply_type == "document":

        await bot.send_document(
            chat_id=chat_id,
            document=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # -----------------------------------------------------
    # صوت
    # -----------------------------------------------------

    if reply_type == "audio":

        await bot.send_audio(
            chat_id=chat_id,
            audio=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # -----------------------------------------------------
    # فيديو نوت
    # -----------------------------------------------------

    if reply_type == "video_note":

        await bot.send_video_note(
            chat_id=chat_id,
            video_note=content
        )

        return


# =========================================================
# تجهيز الرد قبل الإرسال
# =========================================================

def prepare_reply(
    content,
    caption,
    entities_json,
    user
):

    entities = json_to_entities(
        entities_json
    )

    replacements = {}

    if user:

        display_name = (
            user.full_name
            or user.first_name
            or "مستخدم"
        )

        replacements["الاسم"] = (
            display_name
        )

        replacements["username"] = (
            f"@{user.username}"
            if user.username
            else display_name
        )

        replacements["المعرف"] = str(
            user.id
        )

    # -----------------------------------------------------
    # النص
    # -----------------------------------------------------

    if content:

        content, entities = (
            replace_text_and_entities(
                content,
                entities,
                replacements
            )
        )

    # -----------------------------------------------------
    # الكابشن
    # -----------------------------------------------------

    if caption:

        caption, entities = (
            replace_text_and_entities(
                caption,
                entities,
                replacements
            )
        )

    return (
        content,
        caption,
        entities
    )


# =========================================================
# إضافة رد عادي
# =========================================================

async def add_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not await is_admin(user_id):
        return

    add_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "• حلو، ارسل اسم الرد."
    )


async def add_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not await is_admin(user_id):
        return

    session = (
        add_reply_sessions.get(user_id)
    )

    if not session:
        return

    # -----------------------------------------------------
    # الاسم
    # -----------------------------------------------------

    if session["step"] == "name":

        if not update.message.text:
            return

        name = (
            update.message.text.strip()
        )

        if not name:
            return

        session["name"] = name
        session["step"] = "content"

        await update.message.reply_text(
            "• تمام، الحين ارسل محتوى الرد.\n\n"
            "تقدر ترسل نص أو صورة أو فيديو أو GIF "
            "مع كابشن.\n\n"
            "✨ وإذا استخدمت إيموجي مميز، "
            "بيتم حفظه نفسه."
        )

        return

    # -----------------------------------------------------
    # المحتوى
    # -----------------------------------------------------

    if session["step"] == "content":

        result = extract_reply_content(
            update.message
        )

        if not result:
            await update.message.reply_text(
                "• نوع الرسالة هذا غير مدعوم."
            )
            return

        (
            content,
            reply_type,
            caption,
            entities
        ) = result

        # -------------------------------------------------
        # DEBUG
        # -------------------------------------------------

        print(
            "========== REPLY DEBUG =========="
        )

        print(
            "NAME:",
            session["name"]
        )

        print(
            "TEXT:",
            repr(update.message.text)
        )

        print(
            "CAPTION:",
            repr(update.message.caption)
        )

        print(
            "ENTITIES:",
            entities
        )

        for entity in entities:
            print(
                "TYPE:",
                entity.type,
                "OFFSET:",
                entity.offset,
                "LENGTH:",
                entity.length,
                "CUSTOM_EMOJI_ID:",
                entity.custom_emoji_id
            )

        print(
            "================================="
        )

        # -------------------------------------------------
        # الحفظ
        # -------------------------------------------------

        save_reply(
            name=session["name"],
            content=content,
            reply_type=reply_type,
            caption=caption,
            entities=entities,
            special=False
        )

        del add_reply_sessions[user_id]

        await update.message.reply_text(
            f"• تم حفظ الرد «{session['name']}» بنجاح ✅"
        )


# =========================================================
# إضافة رد خاص
# =========================================================

async def add_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not await is_admin(user_id):
        return

    add_special_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "• حلو، ارسل اسم الرد الخاص."
    )


async def add_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not await is_admin(user_id):
        return

    session = (
        add_special_reply_sessions.get(
            user_id
        )
    )

    if not session:
        return

    # -----------------------------------------------------
    # الاسم
    # -----------------------------------------------------

    if session["step"] == "name":

        if not update.message.text:
            return

        name = (
            update.message.text.strip()
        )

        if not name:
            return

        session["name"] = name
        session["step"] = "content"

        await update.message.reply_text(
            "• تمام، ارسل محتوى الرد الخاص."
        )

        return

    # -----------------------------------------------------
    # المحتوى
    # -----------------------------------------------------

    if session["step"] == "content":

        result = extract_reply_content(
            update.message
        )

        if not result:
            await update.message.reply_text(
                "• نوع الرسالة هذا غير مدعوم."
            )
            return

        (
            content,
            reply_type,
            caption,
            entities
        ) = result

        print(
            "========== SPECIAL REPLY DEBUG =========="
        )

        print(
            "NAME:",
            session["name"]
        )

        print(
            "TEXT:",
            repr(update.message.text)
        )

        print(
            "CAPTION:",
            repr(update.message.caption)
        )

        print(
            "ENTITIES:",
            entities
        )

        for entity in entities:
            print(
                "TYPE:",
                entity.type,
                "OFFSET:",
                entity.offset,
                "LENGTH:",
                entity.length,
                "CUSTOM_EMOJI_ID:",
                entity.custom_emoji_id
            )

        print(
            "=========================================="
        )

        save_reply(
            name=session["name"],
            content=content,
            reply_type=reply_type,
            caption=caption,
            entities=entities,
            special=True
        )

        del add_special_reply_sessions[user_id]

        await update.message.reply_text(
            f"• تم حفظ الرد الخاص «{session['name']}» بنجاح ✅"
        )


# =========================================================
# فحص الردود
# =========================================================

async def check_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message:
        return

    if not message.text:
        return

    text = message.text.strip()

    if not text:
        return

    # -----------------------------------------------------
    # تحميل الكاش
    # -----------------------------------------------------

    if not replies_cache and not special_replies_cache:

        try:
            load_replies_cache()
        except Exception as e:
            print(
                "❌ خطأ في تحميل الردود:",
                e
            )
            return

    user = update.effective_user

    # =====================================================
    # الردود الخاصة
    # =====================================================

    if text in special_replies_cache:

        reply = (
            special_replies_cache[text]
        )

        content = reply[0]
        reply_type = reply[1]
        caption = reply[2]
        entities_json = reply[3]

        (
            content,
            caption,
            entities
        ) = prepare_reply(
            content,
            caption,
            entities_json,
            user
        )

        try:

            await send_reply_content(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                content=content,
                reply_type=reply_type,
                caption=caption,
                entities=entities
            )

        except Exception as e:

            print(
                "❌ خطأ في إرسال الرد الخاص:",
                e
            )

        return

    # =====================================================
    # الردود العادية
    # =====================================================

    if text in replies_cache:

        reply = (
            replies_cache[text]
        )

        content = reply[0]
        reply_type = reply[1]
        caption = reply[2]
        entities_json = reply[3]

        (
            content,
            caption,
            entities
        ) = prepare_reply(
            content,
            caption,
            entities_json,
            user
        )

        try:

            await send_reply_content(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                content=content,
                reply_type=reply_type,
                caption=caption,
                entities=entities
            )

        except Exception as e:

            print(
                "❌ خطأ في إرسال الرد:",
                e
            )

        return


# =========================================================
# حذف جلسة منتهية
# =========================================================

def clear_reply_sessions(user_id):

    add_reply_sessions.pop(
        user_id,
        None
    )

    edit_reply_sessions.pop(
        user_id,
        None
    )

    delete_reply_sessions.pop(
        user_id,
        None
    )

    add_special_reply_sessions.pop(
        user_id,
        None
    )

    edit_special_reply_sessions.pop(
        user_id,
        None
    )

    delete_special_reply_sessions.pop(
        user_id,
        None
    )


# =========================================================
# تشغيل الكاش عند استيراد الملف
# =========================================================

try:

    ensure_entities_columns()
    load_replies_cache()

    print(
        "✅ تم تحميل نظام الردود بنجاح"
    )

except Exception as e:

    print(
        "⚠️ تعذر تحميل الردود عند بدء التشغيل:",
        e
    )
