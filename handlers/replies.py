import json

from telegram import Update, MessageEntity
from telegram.ext import ContextTypes

from permissions import is_admin
from database import connect


# =========================================================
# الجلسات
# =========================================================

add_reply_sessions = {}
add_special_reply_sessions = {}

delete_reply_sessions = {}
delete_special_reply_sessions = {}

edit_reply_sessions = {}
edit_special_reply_sessions = {}


# =========================================================
# الكاش
# =========================================================

replies_cache = {}
special_replies_cache = {}


# =========================================================
# قاعدة البيانات - إضافة أعمدة الـ Entities
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

    except Exception as e:
        conn.rollback()
        print("❌ خطأ في إضافة أعمدة entities:", e)

    finally:
        cur.close()
        conn.close()


# =========================================================
# MessageEntity -> JSON
# =========================================================

def entities_to_json(entities):
    if not entities:
        return "[]"

    result = []

    for entity in entities:
        try:
            result.append(entity.to_dict())
        except Exception as e:
            print("❌ خطأ في تحويل entity:", e)

    return json.dumps(
        result,
        ensure_ascii=False
    )


# =========================================================
# JSON -> MessageEntity
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
                    "❌ خطأ في قراءة MessageEntity:",
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
# Telegram يستخدم UTF-16 في offsets
# =========================================================

def utf16_len(text):
    if not text:
        return 0

    return len(
        text.encode("utf-16-le")
    ) // 2


# =========================================================
# حساب موضع النص بعد استبدال المتغيرات
# =========================================================

def replace_text_and_entities(
    text,
    entities,
    replacements
):
    """
    يستبدل:
    #الاسم
    #يوزره
    #اليوزر
    #الرسائل
    #الايدي
    #الرتبه
    #التعديل
    #النقاط

    مع المحافظة على MessageEntity
    ومنها custom_emoji.
    """

    if not text:
        return text, entities or []

    if not replacements:
        return text, entities or []

    old_text = text

    # -----------------------------------------------------
    # نبحث عن جميع المتغيرات
    # -----------------------------------------------------

    tokens = [
        "#الاسم",
        "#يوزره",
        "#اليوزر",
        "#الرسائل",
        "#الايدي",
        "#الرتبه",
        "#التعديل",
        "#النقاط"
    ]

    occurrences = []

    for token in tokens:

        start = 0

        while True:

            index = old_text.find(
                token,
                start
            )

            if index == -1:
                break

            occurrences.append(
                (
                    index,
                    index + len(token),
                    token
                )
            )

            start = index + len(token)

    occurrences.sort(
        key=lambda x: x[0]
    )

    # لا توجد متغيرات
    if not occurrences:
        return old_text, entities or []

    # -----------------------------------------------------
    # بناء النص الجديد
    # -----------------------------------------------------

    new_text_parts = []

    # mapping:
    # old UTF16 start/end
    # new UTF16 start/end
    mappings = []

    old_cursor = 0
    new_cursor = 0

    for start, end, token in occurrences:

        # حماية من التداخل
        if start < old_cursor:
            continue

        # ---------------------------------------------
        # الجزء العادي قبل المتغير
        # ---------------------------------------------

        normal_part = old_text[
            old_cursor:start
        ]

        if normal_part:

            new_text_parts.append(
                normal_part
            )

            old_len = utf16_len(
                normal_part
            )

            mappings.append(
                (
                    utf16_len(
                        old_text[:old_cursor]
                    ),
                    utf16_len(
                        old_text[:start]
                    ),
                    new_cursor,
                    new_cursor + old_len
                )
            )

            new_cursor += old_len

        # ---------------------------------------------
        # المتغير
        # ---------------------------------------------

        replacement = replacements.get(
            token,
            token
        )

        replacement = str(
            replacement
        )

        new_text_parts.append(
            replacement
        )

        old_start_utf16 = utf16_len(
            old_text[:start]
        )

        old_end_utf16 = utf16_len(
            old_text[:end]
        )

        replacement_len = utf16_len(
            replacement
        )

        mappings.append(
            (
                old_start_utf16,
                old_end_utf16,
                new_cursor,
                new_cursor + replacement_len
            )
        )

        new_cursor += replacement_len
        old_cursor = end

    # ---------------------------------------------
    # باقي النص
    # ---------------------------------------------

    if old_cursor < len(old_text):

        remaining = old_text[
            old_cursor:
        ]

        new_text_parts.append(
            remaining
        )

        remaining_len = utf16_len(
            remaining
        )

        mappings.append(
            (
                utf16_len(
                    old_text[:old_cursor]
                ),
                utf16_len(
                    old_text
                ),
                new_cursor,
                new_cursor + remaining_len
            )
        )

        new_cursor += remaining_len

    new_text = "".join(
        new_text_parts
    )

    # =====================================================
    # إعادة ضبط الـ Entities
    # =====================================================

    new_entities = []

    for entity in entities or []:

        old_start = entity.offset
        old_end = (
            entity.offset
            + entity.length
        )

        new_start = None
        new_end = None

        # ---------------------------------------------
        # موضع البداية
        # ---------------------------------------------

        for (
            map_old_start,
            map_old_end,
            map_new_start,
            map_new_end
        ) in mappings:

            if (
                map_old_start
                <= old_start
                <= map_old_end
            ):

                old_range = (
                    map_old_end
                    - map_old_start
                )

                new_range = (
                    map_new_end
                    - map_new_start
                )

                if old_range == 0:

                    new_start = map_new_start

                else:

                    ratio = (
                        old_start
                        - map_old_start
                    ) / old_range

                    new_start = int(
                        map_new_start
                        + (
                            new_range
                            * ratio
                        )
                    )

                break

        # ---------------------------------------------
        # موضع النهاية
        # ---------------------------------------------

        for (
            map_old_start,
            map_old_end,
            map_new_start,
            map_new_end
        ) in mappings:

            if (
                map_old_start
                <= old_end
                <= map_old_end
            ):

                old_range = (
                    map_old_end
                    - map_old_start
                )

                new_range = (
                    map_new_end
                    - map_new_start
                )

                if old_range == 0:

                    new_end = map_new_end

                else:

                    ratio = (
                        old_end
                        - map_old_start
                    ) / old_range

                    new_end = int(
                        map_new_start
                        + (
                            new_range
                            * ratio
                        )
                    )

                break

        # ---------------------------------------------
        # إذا لم نجد mapping
        # ---------------------------------------------

        if new_start is None:
            new_start = old_start

        if new_end is None:
            new_end = old_end

        new_length = (
            new_end
            - new_start
        )

        if new_length <= 0:
            continue

        try:

            entity_data = entity.to_dict()

            entity_data["offset"] = int(
                new_start
            )

            entity_data["length"] = int(
                new_length
            )

            new_entity = (
                MessageEntity.de_json(
                    entity_data,
                    None
                )
            )

            if new_entity:
                new_entities.append(
                    new_entity
                )

        except Exception as e:

            print(
                "❌ خطأ في تعديل Entity:",
                e
            )

    return (
        new_text,
        new_entities
    )


# =========================================================
# استخراج محتوى الرسالة
# =========================================================

def extract_reply_content(message):

    # =====================================================
    # نص
    # =====================================================

    if message.text is not None:

        entities = (
            message.entities
            or []
        )

        return (
            message.text,
            "text",
            None,
            entities
        )

    # =====================================================
    # صورة
    # =====================================================

    if message.photo:

        return (
            message.photo[-1].file_id,
            "photo",
            message.caption,
            message.caption_entities or []
        )

    # =====================================================
    # فيديو
    # =====================================================

    if message.video:

        return (
            message.video.file_id,
            "video",
            message.caption,
            message.caption_entities or []
        )

    # =====================================================
    # متحركة
    # =====================================================

    if message.animation:

        return (
            message.animation.file_id,
            "animation",
            message.caption,
            message.caption_entities or []
        )

    # =====================================================
    # ملصق
    # =====================================================

    if message.sticker:

        return (
            message.sticker.file_id,
            "sticker",
            None,
            []
        )

    # =====================================================
    # بصمة
    # =====================================================

    if message.voice:

        return (
            message.voice.file_id,
            "voice",
            None,
            []
        )

    # =====================================================
    # أغنية
    # =====================================================

    if message.audio:

        return (
            message.audio.file_id,
            "audio",
            message.caption,
            message.caption_entities or []
        )

    # =====================================================
    # ملف
    # =====================================================

    if message.document:

        return (
            message.document.file_id,
            "document",
            message.caption,
            message.caption_entities or []
        )

    return None


# =========================================================
# تحميل الردود في الكاش
# =========================================================

def load_replies_cache():

    global replies_cache
    global special_replies_cache

    ensure_entities_columns()

    conn = connect()
    cur = conn.cursor()

    try:

        # =================================================
        # الردود العادية
        # =================================================

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

            replies_cache[row[0]] = (
                row[1],
                row[2],
                row[3],
                row[4]
            )

        # =================================================
        # الردود المميزة
        # =================================================

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

    table = (
        "special_replies"
        if special
        else "replies"
    )

    entities_json = (
        entities_to_json(
            entities
        )
    )

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            f"""
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
                text = EXCLUDED.text,
                type = EXCLUDED.type,
                caption = EXCLUDED.caption,
                entities = EXCLUDED.entities
            """,
            (
                name,
                content,
                reply_type,
                caption,
                entities_json
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()

    load_replies_cache()


# =========================================================
# إضافة رد عادي - البداية
# =========================================================

async def add_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = (
        update.effective_user.id
    )

    if not is_admin(user_id):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    # إلغاء جلسات الألعاب
    try:

        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )

        add_game_sessions.pop(
            user_id,
            None
        )

        add_question_sessions.pop(
            user_id,
            None
        )

    except Exception:
        pass

    add_reply_sessions.pop(
        user_id,
        None
    )

    add_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "حسنًا، ارسل اسم الرد"
    )


# =========================================================
# إضافة رد عادي
# =========================================================

async def add_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = (
        update.effective_user.id
    )

    if user_id not in add_reply_sessions:
        return

    session = (
        add_reply_sessions[user_id]
    )

    # منع تكرار الأمر
    if update.message.text == "اضف رد":
        return

    # =====================================================
    # اسم الرد
    # =====================================================

    if session["step"] == "name":

        if not update.message.text:

            await update.message.reply_text(
                "❌ أرسل الاسم كنص"
            )

            return

        session["name"] = (
            update.message.text.strip()
        )

        session["step"] = "content"

        await update.message.reply_text(
            "• حسناً يمكنك اضافة\n"
            "( نص, صوره, فيديو, متحركه, بصمه, اغنيه, ملف, ملصق )\n\n"
            "ويمكنك اضافة الرد بتلك الطريقة :\n\n"
            "▹ #الاسم - اسم العضو .\n"
            "▹ #يوزره - يوزر الرد .\n"
            "▹ #اليوزر - يوزر مرسل الرساله .\n"
            "▹ #الرسائل - عدد رسائل المستخدم .\n"
            "▹ #الايدي - ايدي المستخدم .\n"
            "▹ #الرتبه - رتبة المستخدم .\n"
            "▹ #التعديل - عدد تعديلات .\n"
            "▹ #النقاط - نقاط المستخدم ."
        )

        return

    # =====================================================
    # محتوى الرد
    # =====================================================

    if session["step"] == "content":

        result = extract_reply_content(
            update.message
        )

        if not result:

            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )

            return

        (
            content,
            reply_type,
            caption,
            entities
        ) = result

        # =================================================
        # Debug Custom Emoji
        # =================================================

        print(
            "========== ADD REPLY =========="
        )

        print(
            "NAME:",
            session["name"]
        )

        print(
            "TYPE:",
            reply_type
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
                "ENTITY:",
                entity.type,
                "| offset:",
                entity.offset,
                "| length:",
                entity.length,
                "| custom_emoji_id:",
                entity.custom_emoji_id
            )

        print(
            "==============================="
        )

        # =================================================
        # حفظ
        # =================================================

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
            f"✅ تم إضافة الرد: {session['name']}"
        )


# =========================================================
# إضافة رد مميز - البداية
# =========================================================

async def add_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = (
        update.effective_user.id
    )

    if not is_admin(user_id):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    try:

        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )

        add_game_sessions.pop(
            user_id,
            None
        )

        add_question_sessions.pop(
            user_id,
            None
        )

    except Exception:
        pass

    add_special_reply_sessions.pop(
        user_id,
        None
    )

    add_special_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز"
    )


# =========================================================
# إضافة رد مميز
# =========================================================

async def add_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = (
        update.effective_user.id
    )

    if user_id not in add_special_reply_sessions:
        return

    session = (
        add_special_reply_sessions[user_id]
    )

    if update.message.text == "اضف رد مميز":
        return

    # =====================================================
    # الاسم
    # =====================================================

    if session["step"] == "name":

        if not update.message.text:

            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )

            return

        session["name"] = (
            update.message.text.strip()
        )

        session["step"] = "content"

        await update.message.reply_text(
            "• حسناً يمكنك اضافة\n"
            "( نص, صوره, فيديو, متحركه, بصمه, اغنيه, ملف, ملصق )\n\n"
            "ويمكنك اضافة الرد بتلك الطريقة :\n\n"
            "▹ #الاسم - اسم العضو .\n"
            "▹ #يوزره - يوزر الرد .\n"
            "▹ #اليوزر - يوزر مرسل الرساله .\n"
            "▹ #الرسائل - عدد رسائل المستخدم .\n"
            "▹ #الايدي - ايدي المستخدم .\n"
            "▹ #الرتبه - رتبة المستخدم .\n"
            "▹ #التعديل - عدد تعديلات .\n"
            "▹ #النقاط - نقاط المستخدم ."
        )

        return

    # =====================================================
    # المحتوى
    # =====================================================

    if session["step"] == "content":

        result = extract_reply_content(
            update.message
        )

        if not result:

            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )

            return

        (
            content,
            reply_type,
            caption,
            entities
        ) = result

        print(
            "======= ADD SPECIAL REPLY ======="
        )

        print(
            "NAME:",
            session["name"]
        )

        print(
            "TYPE:",
            reply_type
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
                "ENTITY:",
                entity.type,
                "| offset:",
                entity.offset,
                "| length:",
                entity.length,
                "| custom_emoji_id:",
                entity.custom_emoji_id
            )

        print(
            "================================="
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
            f"⭐ تم حفظ الرد المميز: {session['name']}"
        )


# =========================================================
# تجهيز بيانات المستخدم
# =========================================================

def get_user_replacements(
    user,
    conn
):

    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT
                first_name,
                username,
                messages,
                rank
            FROM users
            WHERE user_id = ?
            """,
            (user.id,)
        )

        user_data = cur.fetchone()

        cur.execute(
            """
            SELECT points
            FROM points
            WHERE user_id = ?
            """,
            (user.id,)
        )

        points_data = cur.fetchone()

    finally:

        cur.close()

    user_name = (
        user.first_name
        or "مستخدم"
    )

    user_username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )

    messages = (
        user_data[2]
        if user_data
        else 0
    )

    rank = (
        user_data[3]
        if user_data
        else "عضو"
    )

    points = (
        points_data[0]
        if points_data
        else 0
    )

    return {
        "#الاسم": user_name,
        "#يوزره": user_username,
        "#اليوزر": user_username,
        "#الرسائل": str(messages),
        "#الايدي": str(user.id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points)
    }


# =========================================================
# تجهيز الرد
# =========================================================

def prepare_reply(
    content,
    caption,
    entities_json,
    replacements
):

    entities = json_to_entities(
        entities_json
    )

    # =====================================================
    # النص
    # =====================================================

    if content:

        content, entities = (
            replace_text_and_entities(
                content,
                entities,
                replacements
            )
        )

    # =====================================================
    # الكابشن
    # =====================================================

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
# إرسال الرد
# =========================================================

async def send_reply_content(
    update,
    content,
    reply_type,
    caption=None,
    entities=None
):

    entities = entities or []

    # =====================================================
    # Debug
    # =====================================================

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
            "ENTITY:",
            entity.type,
            "| offset:",
            entity.offset,
            "| length:",
            entity.length,
            "| custom_emoji_id:",
            entity.custom_emoji_id
        )

    print(
        "================================"
    )

    # =====================================================
    # نص
    # =====================================================

    if reply_type == "text":

        await update.message.reply_text(
            text=content,
            entities=entities
        )

        return

    # =====================================================
    # صورة
    # =====================================================

    if reply_type == "photo":

        await update.message.reply_photo(
            photo=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # =====================================================
    # فيديو
    # =====================================================

    if reply_type == "video":

        await update.message.reply_video(
            video=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # =====================================================
    # متحركة
    # =====================================================

    if reply_type == "animation":

        await update.message.reply_animation(
            animation=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # =====================================================
    # ملصق
    # =====================================================

    if reply_type == "sticker":

        await update.message.reply_sticker(
            sticker=content
        )

        return

    # =====================================================
    # بصمة
    # =====================================================

    if reply_type == "voice":

        await update.message.reply_voice(
            voice=content
        )

        return

    # =====================================================
    # أغنية
    # =====================================================

    if reply_type == "audio":

        await update.message.reply_audio(
            audio=content,
            caption=caption or None,
            caption_entities=entities
        )

        return

    # =====================================================
    # ملف
    # =====================================================

    if reply_type == "document":

        await update.message.reply_document(
            document=content,
            caption=caption or None,
            caption_entities=entities
        )

        return


# =========================================================
# تشغيل الردود
# =========================================================

async def check_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    message_text = (
        update.message.text.strip()
    )

    if not message_text:
        return

    user = (
        update.effective_user
    )

    conn = connect()

    try:

        replacements = (
            get_user_replacements(
                user,
                conn
            )
        )

        # =================================================
        # الردود المميزة
        # =================================================

        cur = conn.cursor()

        try:

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

            special_replies = (
                cur.fetchall()
            )

        finally:

            cur.close()

        lower_message = (
            message_text.lower()
        )

        for reply in special_replies:

            name = reply[0]
            content = reply[1]
            reply_type = reply[2]
            caption = reply[3]
            entities_json = reply[4]

            if (
                name.lower()
                in lower_message
            ):

                (
                    content,
                    caption,
                    entities
                ) = prepare_reply(
                    content,
                    caption,
                    entities_json,
                    replacements
                )

                await send_reply_content(
                    update=update,
                    content=content,
                    reply_type=reply_type,
                    caption=caption,
                    entities=entities
                )

                return

        # =================================================
        # الردود العادية
        # =================================================

        cur = conn.cursor()

        try:

            cur.execute(
                """
                SELECT
                    text,
                    type,
                    caption,
                    entities
                FROM replies
                WHERE name = ?
                """,
                (message_text,)
            )

            reply = cur.fetchone()

        finally:

            cur.close()

        if not reply:
            return

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
            replacements
        )

        await send_reply_content(
            update=update,
            content=content,
            reply_type=reply_type,
            caption=caption,
            entities=entities
        )

    except Exception as e:

        print(
            "❌ خطأ في check_replies:",
            e
        )

    finally:

        conn.close()


# =========================================================
# قائمة الردود
# =========================================================

async def replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT name
            FROM replies
            """
        )

        data = cur.fetchall()

    finally:

        cur.close()
        conn.close()

    if not data:

        await update.message.reply_text(
            "📭 لا يوجد ردود"
        )

        return

    msg = (
        "📋 الردود:\n\n"
    )

    for item in data:

        msg += (
            f"• {item[0]}\n"
        )

    await update.message.reply_text(
        msg
    )


# =========================================================
# قائمة الردود المميزة
# =========================================================

async def special_replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT name
            FROM special_replies
            """
        )

        replies = cur.fetchall()

    finally:

        cur.close()
        conn.close()

    if not replies:

        await update.message.reply_text(
            "📭 لا توجد ردود مميزة"
        )

        return

    text = (
        "⭐ قائمة الردود المميزة:\n\n"
    )

    for reply in replies:

        text += (
            f"• {reply[0]}\n"
        )

    await update.message.reply_text(
        text
    )


# =========================================================
# حذف رد
# =========================================================

async def delete_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    user_id = (
        update.effective_user.id
    )

    delete_reply_sessions[
        user_id
    ] = True

    await update.message.reply_text(
        "🗑️ أرسل اسم الرد الذي تريد حذفه"
    )


# =========================================================
# حذف رد
# =========================================================

async def delete_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "مسح رد":
        return

    user_id = (
        update.effective_user.id
    )

    if user_id not in delete_reply_sessions:
        return

    name = (
        update.message.text.strip()
    )

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM replies
            WHERE name = ?
            """,
            (name,)
        )

        deleted = (
            cur.rowcount
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()

    del delete_reply_sessions[
        user_id
    ]

    load_replies_cache()

    if deleted:

        await update.message.reply_text(
            f"✅ تم حذف الرد: {name}"
        )

    else:

        await update.message.reply_text(
            "❌ لا يوجد رد بهذا الاسم"
        )


# =========================================================
# حذف جميع الردود
# =========================================================

async def delete_all_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM replies
            """
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()

    replies_cache.clear()

    await update.message.reply_text(
        "✅ تم حذف جميع الردود العادية"
    )


# =========================================================
# حذف رد مميز
# =========================================================

async def delete_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    user_id = (
        update.effective_user.id
    )

    delete_special_reply_sessions[
        user_id
    ] = True

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد حذفه"
    )


# =========================================================
# حذف رد مميز
# =========================================================

async def delete_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "مسح رد مميز":
        return

    user_id = (
        update.effective_user.id
    )

    if (
        user_id
        not in delete_special_reply_sessions
    ):
        return

    name = (
        update.message.text.strip()
    )

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM special_replies
            WHERE name = ?
            """,
            (name,)
        )

        deleted = (
            cur.rowcount
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()

    del delete_special_reply_sessions[
        user_id
    ]

    load_replies_cache()

    if deleted:

        await update.message.reply_text(
            f"⭐ تم حذف الرد المميز: {name}"
        )

    else:

        await update.message.reply_text(
            "❌ لم أجد رد مميز بهذا الاسم"
        )


# =========================================================
# حذف جميع الردود المميزة
# =========================================================

async def delete_all_special_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM special_replies
            """
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()

    special_replies_cache.clear()

    await update.message.reply_text(
        "⭐ تم حذف جميع الردود المميزة"
    )


# =========================================================
# تعديل رد مميز - البداية
# =========================================================

async def edit_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    user_id = (
        update.effective_user.id
    )

    edit_special_reply_sessions[
        user_id
    ] = {
        "step": "name"
    }

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد تعديله"
    )


# =========================================================
# تعديل رد مميز
# =========================================================

async def edit_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "تعديل رد مميز":
        return

    user_id = (
        update.effective_user.id
    )

    if (
        user_id
        not in edit_special_reply_sessions
    ):
        return

    session = (
        edit_special_reply_sessions[user_id]
    )

    # =====================================================
    # اسم الرد
    # =====================================================

    if session["step"] == "name":

        if not update.message.text:
            return

        name = (
            update.message.text.strip()
        )

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                SELECT name
                FROM special_replies
                WHERE name = ?
                """,
                (name,)
            )

            reply = cur.fetchone()

        finally:

            cur.close()
            conn.close()

        if not reply:

            await update.message.reply_text(
                "❌ لا يوجد رد مميز بهذا الاسم"
            )

            del edit_special_reply_sessions[
                user_id
            ]

            return

        session["name"] = name
        session["step"] = "content"

        await update.message.reply_text(
            "✅ تم العثور على الرد\n\n"
            "أرسل المحتوى الجديد للرد المميز"
        )

        return

    # =====================================================
    # المحتوى الجديد
    # =====================================================

    if session["step"] == "content":

        result = extract_reply_content(
            update.message
        )

        if not result:

            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )

            return

        (
            content,
            reply_type,
            caption,
            entities
        ) = result

        save_reply(
            name=session["name"],
            content=content,
            reply_type=reply_type,
            caption=caption,
            entities=entities,
            special=True
        )

        del edit_special_reply_sessions[
            user_id
        ]

        await update.message.reply_text(
            f"⭐ تم تعديل الرد المميز: {session['name']}"
        )


# =========================================================
# تعديل رد عادي - البداية
# =========================================================

async def edit_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    user_id = (
        update.effective_user.id
    )

    edit_reply_sessions[
        user_id
    ] = {
        "step": "name"
    }

    await update.message.reply_text(
        "✏️ أرسل اسم الرد الذي تريد تعديله"
    )


# =========================================================
# تعديل رد عادي
# =========================================================

async def edit_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "تعديل رد":
        return

    user_id = (
        update.effective_user.id
    )

    if user_id not in edit_reply_sessions:
        return

    session = (
        edit_reply_sessions[user_id]
    )

    # =====================================================
    # الاسم
    # =====================================================

    if session["step"] == "name":

        if not update.message.text:
            return

        name = (
            update.message.text.strip()
        )

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                SELECT name
                FROM replies
                WHERE name = ?
                """,
                (name,)
            )

            reply = cur.fetchone()

        finally:

            cur.close()
            conn.close()

        if not reply:

            await update.message.reply_text(
                "❌ لا يوجد رد بهذا الاسم"
            )

            del edit_reply_sessions[
                user_id
            ]

            return

        session["name"] = name
        session["step"] = "content"

        await update.message.reply_text(
            "✅ تم العثور على الرد\n\n"
            "أرسل المحتوى الجديد"
        )

        return

    # =====================================================
    # المحتوى
    # =====================================================

    if session["step"] == "content":

        result = extract_reply_content(
            update.message
        )

        if not result:

            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )

            return

        (
            content,
            reply_type,
            caption,
            entities
        ) = result

        save_reply(
            name=session["name"],
            content=content,
            reply_type=reply_type,
            caption=caption,
            entities=entities,
            special=False
        )

        del edit_reply_sessions[
            user_id
        ]

        await update.message.reply_text(
            f"✅ تم تعديل الرد: {session['name']}"
        )


# =========================================================
# تشغيل عند استيراد الملف
# =========================================================

try:

    ensure_entities_columns()
    load_replies_cache()

    print(
        "✅ تم تحميل نظام الردود"
    )

except Exception as e:

    print(
        "⚠️ تعذر تحميل الردود:",
        e
    )
