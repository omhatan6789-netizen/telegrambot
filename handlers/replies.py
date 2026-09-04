import json
import re

from telegram import Update, MessageEntity
from telegram.ext import ContextTypes

from permissions import is_admin
from database import connect


# ==================================================
# جلسات إضافة / تعديل / حذف الردود
# ==================================================

add_reply_sessions = {}
add_special_reply_sessions = {}

delete_special_reply_sessions = {}
edit_special_reply_sessions = {}
edit_reply_sessions = {}
delete_reply_sessions = {}


# ==================================================
# Cache
# ==================================================

replies_cache = None
special_replies_cache = None


# ==================================================
# قاعدة البيانات - إضافة أعمدة Custom Emoji
# ==================================================

def ensure_entities_columns():

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute("""
            ALTER TABLE replies
            ADD COLUMN IF NOT EXISTS entities TEXT
        """)

        cur.execute("""
            ALTER TABLE special_replies
            ADD COLUMN IF NOT EXISTS entities TEXT
        """)

        conn.commit()
        cur.close()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# ==================================================
# MessageEntity -> JSON
# ==================================================

def entities_to_json(entities):

    if not entities:
        return None

    try:

        data = []

        for entity in entities:

            item = entity.to_dict()

            # نتأكد من حفظ custom_emoji_id
            if entity.custom_emoji_id:
                item["custom_emoji_id"] = (
                    entity.custom_emoji_id
                )

            data.append(item)

        return json.dumps(
            data,
            ensure_ascii=False
        )

    except Exception as e:

        print(
            f"⚠️ خطأ في حفظ MessageEntity: {e}"
        )

        return None


# ==================================================
# JSON -> MessageEntity
# ==================================================

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

            if not isinstance(entity_data, dict):
                continue

            try:

                entity = MessageEntity.de_json(
                    entity_data,
                    None
                )

                if entity:
                    result.append(entity)

            except Exception as e:

                print(
                    f"⚠️ تعذر تحويل MessageEntity: {e}"
                )

        return result

    except Exception as e:

        print(
            f"⚠️ خطأ في قراءة entities: {e}"
        )

        return []


# ==================================================
# UTF-16
# ==================================================

def utf16_len(text):

    if not text:
        return 0

    return len(
        text.encode("utf-16-le")
    ) // 2


# ==================================================
# استبدال المتغيرات العادية
# ==================================================

def replace_data(
    text,
    messages=0,
    rank="عضو",
    points=0,
    user_name=None,
    user_username=None,
    user_id=None
):

    if not text:
        return text

    user_name = (
        user_name
        if user_name
        else "مستخدم"
    )

    user_username = (
        user_username
        if user_username
        else "لا يوجد"
    )

    user_id = (
        str(user_id)
        if user_id is not None
        else ""
    )

    replacements = {

        "#الاسم": user_name,

        "#يوزره": user_username,

        "#اليوزر": user_username,

        "#الرسائل": str(messages),

        "#الايدي": user_id,

        "#الرتبه": rank,

        "#التعديل": "0",

        "#النقاط": str(points)
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    return text


# ==================================================
# استبدال المتغيرات + تعديل UTF-16 entities
# ==================================================

def replace_text_and_entities(
    text,
    entities,
    messages=0,
    rank="عضو",
    points=0,
    user_name="مستخدم",
    user_username="لا يوجد",
    user_id=0
):

    if not text:
        return text, []

    entities = entities or []

    replacements = {

        "#الاسم": (
            user_name
            if user_name
            else "مستخدم"
        ),

        "#يوزره": (
            user_username
            if user_username
            else "لا يوجد"
        ),

        "#اليوزر": (
            user_username
            if user_username
            else "لا يوجد"
        ),

        "#الرسائل": str(messages),

        "#الايدي": str(user_id),

        "#الرتبه": (
            rank
            if rank
            else "عضو"
        ),

        "#التعديل": "0",

        "#النقاط": str(points)
    }

    pattern = re.compile(
        "|".join(
            re.escape(key)
            for key in replacements.keys()
        )
    )

    matches = list(
        pattern.finditer(text)
    )

    # --------------------------------------------------
    # لا يوجد أي متغير
    # --------------------------------------------------

    if not matches:
        return text, entities

    # --------------------------------------------------
    # خريطة UTF-16
    #
    # Telegram يستخدم UTF-16 offsets
    # وليس Python character indexes.
    # --------------------------------------------------

    boundaries = {}

    old_utf16 = 0
    new_utf16 = 0

    boundaries[0] = 0

    result_parts = []

    old_python_pos = 0

    for match in matches:

        # ----------------------------------------------
        # الجزء الذي قبل المتغير
        # ----------------------------------------------

        before = text[
            old_python_pos:match.start()
        ]

        result_parts.append(before)

        for char in before:

            old_utf16 += utf16_len(char)
            new_utf16 += utf16_len(char)

            boundaries[old_utf16] = new_utf16

        # ----------------------------------------------
        # بداية المتغير
        # ----------------------------------------------

        placeholder_start_utf16 = (
            utf16_len(
                text[:match.start()]
            )
        )

        boundaries[
            placeholder_start_utf16
        ] = new_utf16

        # ----------------------------------------------
        # الاستبدال
        # ----------------------------------------------

        replacement = replacements[
            match.group(0)
        ]

        result_parts.append(
            replacement
        )

        new_utf16 += utf16_len(
            replacement
        )

        placeholder_end_utf16 = (
            utf16_len(
                text[:match.end()]
            )
        )

        boundaries[
            placeholder_end_utf16
        ] = new_utf16

        old_utf16 = placeholder_end_utf16

        old_python_pos = match.end()

    # --------------------------------------------------
    # الجزء الأخير
    # --------------------------------------------------

    after = text[
        old_python_pos:
    ]

    result_parts.append(after)

    for char in after:

        old_utf16 += utf16_len(char)
        new_utf16 += utf16_len(char)

        boundaries[old_utf16] = new_utf16

    new_text = "".join(
        result_parts
    )

    # --------------------------------------------------
    # تعديل entities
    # --------------------------------------------------

    new_entities = []

    for entity in entities:

        old_start = entity.offset

        old_end = (
            entity.offset
            + entity.length
        )

        new_start = boundaries.get(
            old_start
        )

        new_end = boundaries.get(
            old_end
        )

        # --------------------------------------------------
        # إذا لم نجد الحدود
        # --------------------------------------------------

        if (
            new_start is None
            or new_end is None
        ):

            # لا نرسل Entity غير صحيحة
            # حتى لا يرفض Telegram الرسالة.

            print(
                "⚠️ تعذر إعادة حساب Entity:",
                entity
            )

            continue

        # --------------------------------------------------
        # إنشاء Entity جديدة
        # --------------------------------------------------

        new_entity = MessageEntity(

            type=entity.type,

            offset=new_start,

            length=(
                new_end
                - new_start
            ),

            url=entity.url,

            user=entity.user,

            language=entity.language,

            custom_emoji_id=(
                entity.custom_emoji_id
            )
        )

        new_entities.append(
            new_entity
        )

    return (
        new_text,
        new_entities
    )


# ==================================================
# Cache
# ==================================================

def load_replies_cache():

    global replies_cache
    global special_replies_cache

    ensure_entities_columns()

    conn = connect()

    try:

        cur = conn.cursor()

        # ----------------------------------------------
        # الردود العادية
        # ----------------------------------------------

        cur.execute("""
            SELECT
                name,
                text,
                type,
                caption,
                entities
            FROM replies
        """)

        rows = cur.fetchall()

        replies_cache = {

            row[0]: (
                row[1],
                row[2],
                row[3],
                row[4]
            )

            for row in rows
        }

        # ----------------------------------------------
        # الردود المميزة
        # ----------------------------------------------

        cur.execute("""
            SELECT
                name,
                text,
                type,
                caption,
                entities
            FROM special_replies
        """)

        special_replies_cache = (
            cur.fetchall()
        )

        cur.close()

    finally:

        conn.close()


def invalidate_replies_cache():

    load_replies_cache()


def get_replies_cache():

    global replies_cache
    global special_replies_cache

    if (
        replies_cache is None
        or special_replies_cache is None
    ):

        load_replies_cache()

    return (
        replies_cache,
        special_replies_cache
    )


# ==================================================
# استخراج محتوى الرسالة
# ==================================================

def extract_reply_content(message):

    content = None
    reply_type = None
    caption = None
    entities = None

    # --------------------------------------------------
    # نص
    # --------------------------------------------------

    if message.text:

        content = message.text

        reply_type = "text"

        entities = entities_to_json(
            message.entities
        )

    # --------------------------------------------------
    # صورة
    # --------------------------------------------------

    elif message.photo:

        content = (
            message.photo[-1].file_id
        )

        reply_type = "photo"

        caption = message.caption

        entities = entities_to_json(
            message.caption_entities
        )

    # --------------------------------------------------
    # فيديو
    # --------------------------------------------------

    elif message.video:

        content = message.video.file_id

        reply_type = "video"

        caption = message.caption

        entities = entities_to_json(
            message.caption_entities
        )

    # --------------------------------------------------
    # متحركة
    # --------------------------------------------------

    elif message.animation:

        content = (
            message.animation.file_id
        )

        reply_type = "animation"

        caption = message.caption

        entities = entities_to_json(
            message.caption_entities
        )

    # --------------------------------------------------
    # ملصق
    # --------------------------------------------------

    elif message.sticker:

        content = (
            message.sticker.file_id
        )

        reply_type = "sticker"

    # --------------------------------------------------
    # بصمة
    # --------------------------------------------------

    elif message.voice:

        content = message.voice.file_id

        reply_type = "voice"

    # --------------------------------------------------
    # أغنية
    # --------------------------------------------------

    elif message.audio:

        content = message.audio.file_id

        reply_type = "audio"

        caption = message.caption

        entities = entities_to_json(
            message.caption_entities
        )

    # --------------------------------------------------
    # ملف
    # --------------------------------------------------

    elif message.document:

        content = (
            message.document.file_id
        )

        reply_type = "document"

        caption = message.caption

        entities = entities_to_json(
            message.caption_entities
        )

    else:

        return None

    return (
        content,
        reply_type,
        caption,
        entities
    )


# ==================================================
# حفظ الرد في قاعدة البيانات
# ==================================================

def save_reply(
    table,
    name,
    content,
    reply_type,
    caption,
    entities
):

    conn = connect()

    try:

        cur = conn.cursor()

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
            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?
            )
            ON CONFLICT (name)
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
                entities
            )
        )

        conn.commit()

        cur.close()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# ==================================================
# بدء إضافة رد
# ==================================================

async def add_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

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


# ==================================================
# إضافة رد
# ==================================================

async def add_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if user_id not in add_reply_sessions:
        return

    session = add_reply_sessions[user_id]

    if update.message.text == "اضف رد":
        return

    # --------------------------------------------------
    # الاسم
    # --------------------------------------------------

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
            "▹ #النقاط - نقاط المستخدم .\n\n"

            "✨ ويمكنك أيضًا إضافة إيموجي مميز من تيليجرام."
        )

        return

    # --------------------------------------------------
    # المحتوى
    # --------------------------------------------------

    if session["step"] == "content":

        name = session["name"]

        result = extract_reply_content(
            update.message
        )

        if result is None:

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

        try:

            save_reply(
                "replies",
                name,
                content,
                reply_type,
                caption,
                entities
            )

        except Exception as e:

            print(
                f"❌ خطأ في حفظ الرد: {e}"
            )

            await update.message.reply_text(
                "❌ حدث خطأ أثناء حفظ الرد"
            )

            return

        invalidate_replies_cache()

        del add_reply_sessions[user_id]

        await update.message.reply_text(
            f"✅ تم إضافة الرد: {name}"
        )


# ==================================================
# إرسال الرد
# ==================================================

async def send_reply_content(
    message,
    content,
    reply_type,
    caption=None,
    entities=None
):

    # --------------------------------------------------
    # نص
    # --------------------------------------------------

    if reply_type == "text":

        await message.reply_text(
            text=content,
            entities=entities
        )

    # --------------------------------------------------
    # صورة
    # --------------------------------------------------

    elif reply_type == "photo":

        await message.reply_photo(
            photo=content,
            caption=caption,
            caption_entities=entities
        )

    # --------------------------------------------------
    # فيديو
    # --------------------------------------------------

    elif reply_type == "video":

        await message.reply_video(
            video=content,
            caption=caption,
            caption_entities=entities
        )

    # --------------------------------------------------
    # متحركة
    # --------------------------------------------------

    elif reply_type == "animation":

        await message.reply_animation(
            animation=content,
            caption=caption,
            caption_entities=entities
        )

    # --------------------------------------------------
    # ملصق
    # --------------------------------------------------

    elif reply_type == "sticker":

        await message.reply_sticker(
            sticker=content
        )

    # --------------------------------------------------
    # بصمة
    # --------------------------------------------------

    elif reply_type == "voice":

        await message.reply_voice(
            voice=content
        )

    # --------------------------------------------------
    # أغنية
    # --------------------------------------------------

    elif reply_type == "audio":

        await message.reply_audio(
            audio=content,
            caption=caption,
            caption_entities=entities
        )

    # --------------------------------------------------
    # ملف
    # --------------------------------------------------

    elif reply_type == "document":

        await message.reply_document(
            document=content,
            caption=caption,
            caption_entities=entities
        )


# ==================================================
# بيانات المستخدم
# ==================================================

def get_user_data(user_id):

    messages = 0
    rank = "عضو"
    points = 0

    conn = connect()

    try:

        cur = conn.cursor()

        # --------------------------------------------------
        # الرسائل والرتبة
        # --------------------------------------------------

        cur.execute(
            """
            SELECT messages, rank
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        user_data = cur.fetchone()

        if user_data:

            messages = (
                user_data[0]
                or 0
            )

            rank = (
                user_data[1]
                or "عضو"
            )

        # --------------------------------------------------
        # النقاط
        # --------------------------------------------------

        cur.execute(
            """
            SELECT points
            FROM points
            WHERE user_id = ?
            """,
            (user_id,)
        )

        points_data = cur.fetchone()

        if points_data:

            points = (
                points_data[0]
                or 0
            )

        cur.close()

    finally:

        conn.close()

    return (
        messages,
        rank,
        points
    )


# ==================================================
# تجهيز الرد النهائي
# ==================================================

def prepare_reply(
    content,
    reply_type,
    caption,
    entities_json,
    user
):

    messages = 0
    rank = "عضو"
    points = 0

    combined_text = (
        (content or "")
        + " "
        + (caption or "")
    )

    # --------------------------------------------------
    # نحتاج بيانات المستخدم فقط إذا استخدم placeholders
    # --------------------------------------------------

    if any(
        placeholder in combined_text

        for placeholder in (

            "#الرسائل",
            "#الرتبه",
            "#النقاط"
        )
    ):

        (
            messages,
            rank,
            points
        ) = get_user_data(
            user.id
        )

    user_name = (
        user.first_name
        or "مستخدم"
    )

    user_username = (

        f"@{user.username}"

        if user.username

        else "لا يوجد"
    )

    entities = json_to_entities(
        entities_json
    )

    # --------------------------------------------------
    # النص
    # --------------------------------------------------

    if reply_type == "text":

        content, entities = (
            replace_text_and_entities(

                content,

                entities,

                messages,

                rank,

                points,

                user_name,

                user_username,

                user.id
            )
        )

    # --------------------------------------------------
    # Caption
    # --------------------------------------------------

    elif caption:

        caption, entities = (
            replace_text_and_entities(

                caption,

                entities,

                messages,

                rank,

                points,

                user_name,

                user_username,

                user.id
            )
        )

    return (
        content,
        reply_type,
        caption,
        entities
    )


# ==================================================
# فحص الردود
# ==================================================

async def check_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    message_text = (
        update.message.text.lower()
    )

    user = update.effective_user

    replies_cache, special_replies = (
        get_replies_cache()
    )

    # ==================================================
    # الردود المميزة
    # ==================================================

    for reply in special_replies:

        name = reply[0]

        content = reply[1]

        reply_type = reply[2]

        caption = reply[3]

        entities_json = (
            reply[4]
            if len(reply) > 4
            else None
        )

        if name.lower() not in message_text:
            continue

        (
            content,
            reply_type,
            caption,
            entities
        ) = prepare_reply(

            content,

            reply_type,

            caption,

            entities_json,

            user
        )

        await send_reply_content(

            update.message,

            content,

            reply_type,

            caption,

            entities
        )

        return

    # ==================================================
    # الردود العادية
    # ==================================================

    reply = replies_cache.get(
        update.message.text
    )

    if not reply:
        return

    content = reply[0]

    reply_type = reply[1]

    caption = reply[2]

    entities_json = (
        reply[3]
        if len(reply) > 3
        else None
    )

    (
        content,
        reply_type,
        caption,
        entities
    ) = prepare_reply(

        content,

        reply_type,

        caption,

        entities_json,

        user
    )

    await send_reply_content(

        update.message,

        content,

        reply_type,

        caption,

        entities
    )


# ==================================================
# قائمة الردود
# ==================================================

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

    cur.execute(
        """
        SELECT name
        FROM replies
        """
    )

    data = cur.fetchall()

    cur.close()
    conn.close()

    if not data:

        await update.message.reply_text(
            "📭 لا يوجد ردود"
        )

        return

    msg = "📋 الردود:\n\n"

    for item in data:

        msg += (
            f"• {item[0]}\n"
        )

    await update.message.reply_text(
        msg
    )


# ==================================================
# بدء إضافة رد مميز
# ==================================================

async def add_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )

        return

    user_id = update.effective_user.id

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


# ==================================================
# إضافة رد مميز
# ==================================================

async def add_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "اضف رد مميز":
        return

    user_id = update.effective_user.id

    if user_id not in add_special_reply_sessions:
        return

    session = (
        add_special_reply_sessions[user_id]
    )

    # --------------------------------------------------
    # الاسم
    # --------------------------------------------------

    if session.get("step") == "name":

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
            "▹ #النقاط - نقاط المستخدم .\n\n"

            "✨ يدعم أيضًا الإيموجي المميز."
        )

        return

    # --------------------------------------------------
    # المحتوى
    # --------------------------------------------------

    if session.get("step") == "content":

        name = session["name"]

        result = extract_reply_content(
            update.message
        )

        if result is None:

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

        try:

            save_reply(
                "special_replies",
                name,
                content,
                reply_type,
                caption,
                entities
            )

        except Exception as e:

            print(
                f"❌ خطأ في حفظ الرد المميز: {e}"
            )

            await update.message.reply_text(
                "❌ حدث خطأ أثناء حفظ الرد المميز"
            )

            return

        invalidate_replies_cache()

        del add_special_reply_sessions[
            user_id
        ]

        await update.message.reply_text(
            f"⭐ تم حفظ الرد المميز: {name}"
        )


# ==================================================
# قائمة الردود المميزة
# ==================================================

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

    cur.execute(
        """
        SELECT name
        FROM special_replies
        """
    )

    replies = cur.fetchall()

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


# ==================================================
# حذف رد مميز - البداية
# ==================================================

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

    user_id = update.effective_user.id

    delete_special_reply_sessions[
        user_id
    ] = True

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد حذفه"
    )


# ==================================================
# حذف رد مميز
# ==================================================

async def delete_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "مسح رد مميز":
        return

    user_id = update.effective_user.id

    if (
        user_id
        not in delete_special_reply_sessions
    ):
        return

    if not update.message.text:
        return

    name = update.message.text.strip()

    conn = connect()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM special_replies
        WHERE name = ?
        """,
        (name,)
    )

    deleted = cur.rowcount

    conn.commit()

    cur.close()
    conn.close()

    invalidate_replies_cache()

    del delete_special_reply_sessions[
        user_id
    ]

    if deleted:

        await update.message.reply_text(
            f"✅ تم حذف الرد المميز: {name}"
        )

    else:

        await update.message.reply_text(
            "❌ لم أجد رد مميز بهذا الاسم"
        )


# ==================================================
# تعديل رد مميز - البداية
# ==================================================

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

    user_id = update.effective_user.id

    edit_special_reply_sessions[
        user_id
    ] = {
        "step": "name"
    }

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد تعديله"
    )


# ==================================================
# تعديل رد مميز
# ==================================================

async def edit_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "تعديل رد مميز":
        return

    user_id = update.effective_user.id

    if (
        user_id
        not in edit_special_reply_sessions
    ):
        return

    session = (
        edit_special_reply_sessions[user_id]
    )

    # --------------------------------------------------
    # الاسم
    # --------------------------------------------------

    if session["step"] == "name":

        if not update.message.text:

            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )

            return

        name = update.message.text.strip()

        conn = connect()

        cur = conn.cursor()

        cur.execute(
            """
            SELECT name
            FROM special_replies
            WHERE name = ?
            """,
            (name,)
        )

        reply = cur.fetchone()

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

    # --------------------------------------------------
    # المحتوى الجديد
    # --------------------------------------------------

    if session["step"] == "content":

        name = session["name"]

        result = extract_reply_content(
            update.message
        )

        if result is None:

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

        conn = connect()

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE special_replies

            SET
                text = ?,
                type = ?,
                caption = ?,
                entities = ?

            WHERE name = ?
            """,
            (
                content,
                reply_type,
                caption,
                entities,
                name
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        invalidate_replies_cache()

        del edit_special_reply_sessions[
            user_id
        ]

        await update.message.reply_text(
            f"⭐ تم تعديل الرد المميز: {name}"
        )


# ==================================================
# تعديل رد عادي - البداية
# ==================================================

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

    user_id = update.effective_user.id

    edit_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "✏️ أرسل اسم الرد الذي تريد تعديله"
    )


# ==================================================
# تعديل رد عادي
# ==================================================

async def edit_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "تعديل رد":
        return

    user_id = update.effective_user.id

    if user_id not in edit_reply_sessions:
        return

    session = edit_reply_sessions[user_id]

    # --------------------------------------------------
    # الاسم
    # --------------------------------------------------

    if session["step"] == "name":

        if not update.message.text:

            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )

            return

        name = update.message.text.strip()

        conn = connect()

        cur = conn.cursor()

        cur.execute(
            """
            SELECT name
            FROM replies
            WHERE name = ?
            """,
            (name,)
        )

        reply = cur.fetchone()

        cur.close()
        conn.close()

        if not reply:

            await update.message.reply_text(
                "❌ لا يوجد رد بهذا الاسم"
            )

            del edit_reply_sessions[user_id]

            return

        session["name"] = name

        session["step"] = "content"

        await update.message.reply_text(
            "✅ تم العثور على الرد\n\n"
            "أرسل المحتوى الجديد"
        )

        return

    # --------------------------------------------------
    # المحتوى
    # --------------------------------------------------

    if session["step"] == "content":

        name = session["name"]

        result = extract_reply_content(
            update.message
        )

        if result is None:

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

        conn = connect()

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE replies

            SET
                text = ?,
                type = ?,
                caption = ?,
                entities = ?

            WHERE name = ?
            """,
            (
                content,
                reply_type,
                caption,
                entities,
                name
            )
        )

        conn.commit()

        cur.close()
        conn.close()

        invalidate_replies_cache()

        del edit_reply_sessions[user_id]

        await update.message.reply_text(
            f"✅ تم تعديل الرد: {name}"
        )


# ==================================================
# حذف رد عادي - البداية
# ==================================================

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

    user_id = update.effective_user.id

    delete_reply_sessions[user_id] = True

    await update.message.reply_text(
        "🗑️ أرسل اسم الرد الذي تريد حذفه"
    )


# ==================================================
# حذف رد عادي
# ==================================================

async def delete_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.message.text == "مسح رد":
        return

    user_id = update.effective_user.id

    if user_id not in delete_reply_sessions:
        return

    if not update.message.text:
        return

    name = update.message.text.strip()

    conn = connect()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT name
        FROM replies
        WHERE name = ?
        """,
        (name,)
    )

    reply = cur.fetchone()

    if not reply:

        cur.close()
        conn.close()

        await update.message.reply_text(
            "❌ لا يوجد رد بهذا الاسم"
        )

        del delete_reply_sessions[user_id]

        return

    cur.execute(
        """
        DELETE FROM replies
        WHERE name = ?
        """,
        (name,)
    )

    conn.commit()

    cur.close()
    conn.close()

    invalidate_replies_cache()

    del delete_reply_sessions[user_id]

    await update.message.reply_text(
        f"✅ تم حذف الرد: {name}"
    )


# ==================================================
# حذف جميع الردود العادية
# ==================================================

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

    cur.execute(
        """
        DELETE FROM replies
        """
    )

    conn.commit()

    cur.close()
    conn.close()

    invalidate_replies_cache()

    await update.message.reply_text(
        "✅ تم حذف جميع الردود العادية"
    )


# ==================================================
# حذف جميع الردود المميزة
# ==================================================

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

    cur.execute(
        """
        DELETE FROM special_replies
        """
    )

    conn.commit()

    cur.close()
    conn.close()

    invalidate_replies_cache()

    await update.message.reply_text(
        "⭐ تم حذف جميع الردود المميزة"
    )
