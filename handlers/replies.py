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
# Cache للردود
# ==================================================
replies_cache = None
special_replies_cache = None
# ==================================================
# تجهيز أعمدة الـ Custom Emoji
# ==================================================
def ensure_entities_columns():
    """
    إضافة عمود entities إذا لم يكن موجودًا.
    يستخدم PostgreSQL / Supabase.
    """
    conn = connect()
    try:
        cur = conn.cursor()
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
        cur.close()
    finally:
        conn.close()
# ==================================================
# تحويل MessageEntity إلى JSON
# ==================================================
def entities_to_json(entities):
    """
    يحفظ MessageEntity الخاصة بالرسالة،
    ومنها custom_emoji.
    """
    if not entities:
        return None
    try:
        return json.dumps(
            [entity.to_dict() for entity in entities],
            ensure_ascii=False
        )
    except Exception:
        return None
# ==================================================
# تحويل JSON إلى MessageEntity
# ==================================================
def json_to_entities(data):
    """
    يعيد entities من قاعدة البيانات إلى
    MessageEntity objects.
    """
    if not data:
        return []
    try:
        if isinstance(data, str):
            data = json.loads(data)
        result = []
        for entity_data in data:
            try:
                entity = MessageEntity.de_json(
                    entity_data,
                    None
                )
                if entity:
                    result.append(entity)
            except Exception:
                continue
        return result
    except Exception:
        return []
# ==================================================
# استخراج entities من الرسالة
# ==================================================
def get_message_entities(message):
    """
    يستخرج entities الصحيحة سواء كانت:
    - رسالة نصية
    - Caption
    """
    if message.text is not None:
        return entities_to_json(
            message.entities
        )
    if message.caption is not None:
        return entities_to_json(
            message.caption_entities
        )
    return None
# ==================================================
# استبدال المتغيرات مع المحافظة على أماكن entities
# ==================================================
def replace_data_with_entities(
    text,
    entities,
    messages=0,
    rank="عضو",
    points=0
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
    مع تعديل offsets الخاصة بـ Telegram
    حتى لا يخترب مكان الـ Custom Emoji.
    """
    if not text:
        return text, entities or []
    if not entities:
        return (
            replace_data(
                text,
                messages,
                rank,
                points
            ),
            []
        )
    # ------------------------------------------
    # التحويلات
    # ------------------------------------------
    user_username = None
    # هذه القيم يتم تمريرها لاحقًا من check_replies
    # لذلك هنا نستخدم placeholders مؤقتة
    replacements = {}
    # ------------------------------------------
    # سنقوم بالاستبدال باستخدام regex
    # ------------------------------------------
    replacement_values = {
        "#الاسم": None,
        "#يوزره": None,
        "#اليوزر": None,
        "#الرسائل": str(messages),
        "#الايدي": None,
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points)
    }
    # القيم None سيتم تعويضها قبل الاستدعاء
    # من خلال replace_data_with_entities_full
    return text, entities
# ==================================================
# استبدال البيانات الأساسي
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
    user_name = user_name or "مستخدم"
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
    text = text.replace(
        "#الاسم",
        user_name
    )
    text = text.replace(
        "#يوزره",
        user_username
    )
    text = text.replace(
        "#اليوزر",
        user_username
    )
    text = text.replace(
        "#الرسائل",
        str(messages)
    )
    text = text.replace(
        "#الايدي",
        user_id
    )
    text = text.replace(
        "#الرتبه",
        rank
    )
    text = text.replace(
        "#التعديل",
        "0"
    )
    text = text.replace(
        "#النقاط",
        str(points)
    )
    return text
# ==================================================
# UTF-16 length
# ==================================================
def utf16_len(text):
    """
    Telegram offsets تعتمد على UTF-16.
    """
    return len(
        text.encode("utf-16-le")
    ) // 2
# ==================================================
# تعديل entities بعد استبدال المتغيرات
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
        "#الاسم": user_name,
        "#يوزره": user_username,
        "#اليوزر": user_username,
        "#الرسائل": str(messages),
        "#الايدي": str(user_id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points)
    }
    # ------------------------------------------
    # العثور على كل الاستبدالات
    # ------------------------------------------
    pattern = re.compile(
        "|".join(
            re.escape(key)
            for key in replacements
        )
    )
    matches = list(
        pattern.finditer(text)
    )
    if not matches:
        return text, entities
    # ------------------------------------------
    # بناء النص الجديد
    # ------------------------------------------
    result_parts = []
    old_position = 0
    # mapping:
    # old UTF16 boundary -> new UTF16 boundary
    boundaries = {
        0: 0
    }
    new_utf16_position = 0
    for match in matches:
        before = text[
            old_position:match.start()
        ]
        result_parts.append(before)
        # تسجيل حدود characters داخل الجزء القديم
        old_cursor = match.start()
        for char in before:
            old_cursor += 1
            new_utf16_position += utf16_len(char)
            boundaries[
                utf16_len(
                    text[:old_cursor]
                )
            ] = new_utf16_position
        replacement = replacements[
            match.group(0)
        ]
        result_parts.append(
            replacement
        )
        # نهاية الـ placeholder القديم
        old_end = match.end()
        new_utf16_position += utf16_len(
            replacement
        )
        boundaries[
            utf16_len(
                text[:old_end]
            )
        ] = new_utf16_position
        old_position = old_end
    # ------------------------------------------
    # الجزء الأخير
    # ------------------------------------------
    after = text[old_position:]
    result_parts.append(after)
    old_cursor = old_position
    for char in after:
        old_cursor += 1
        new_utf16_position += utf16_len(char)
        boundaries[
            utf16_len(
                text[:old_cursor]
            )
        ] = new_utf16_position
    new_text = "".join(result_parts)
    # ------------------------------------------
    # تحويل entities
    # ------------------------------------------
    new_entities = []
    for entity in entities:
        old_start = entity.offset
        old_end = (
            entity.offset
            + entity.length
        )
        # إذا لم نجد boundary مباشر،
        # نحسبه من النص الأصلي.
        new_start = boundaries.get(
            old_start
        )
        new_end = boundaries.get(
            old_end
        )
        if new_start is None:
            prefix = text[
                :len(
                    text.encode(
                        "utf-16-le"
                    )[:old_start * 2]
                    .decode(
                        "utf-16-le"
                    )
                )
            ]
            new_prefix = replace_data(
                prefix,
                messages,
                rank,
                points,
                user_name,
                user_username,
                user_id
            )
            new_start = utf16_len(
                new_prefix
            )
        if new_end is None:
            prefix = text[
                :len(
                    text.encode(
                        "utf-16-le"
                    )[:old_end * 2]
                    .decode(
                        "utf-16-le"
                    )
                )
            ]
            new_prefix = replace_data(
                prefix,
                messages,
                rank,
                points,
                user_name,
                user_username,
                user_id
            )
            new_end = utf16_len(
                new_prefix
            )
        new_entity = MessageEntity(
            type=entity.type,
            offset=new_start,
            length=new_end - new_start,
            url=entity.url,
            user=entity.user,
            language=entity.language,
            custom_emoji_id=entity.custom_emoji_id
        )
        new_entities.append(
            new_entity
        )
    return new_text, new_entities
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
        # --------------------------------------
        # الردود العادية
        # --------------------------------------
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
        replies_cache = {
            row[0]: (
                row[1],
                row[2],
                row[3],
                row[4]
            )
            for row in rows
        }
        # --------------------------------------
        # الردود المميزة
        # --------------------------------------
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
        special_rows = cur.fetchall()
        special_replies_cache = special_rows
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
    except:
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
# إضافة الرد
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
    # --------------------------------------
    # اسم الرد
    # --------------------------------------
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
    # --------------------------------------
    # المحتوى
    # --------------------------------------
    if session["step"] == "content":
        name = session["name"]
        content = None
        reply_type = None
        caption = None
        entities = None
        # نص
        if update.message.text:
            content = update.message.text
            reply_type = "text"
            entities = entities_to_json(
                update.message.entities
            )
        # صورة
        elif update.message.photo:
            content = (
                update.message.photo[-1].file_id
            )
            reply_type = "photo"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        # فيديو
        elif update.message.video:
            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        # متحركة
        elif update.message.animation:
            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        # ملصق
        elif update.message.sticker:
            content = update.message.sticker.file_id
            reply_type = "sticker"
        # بصمة
        elif update.message.voice:
            content = update.message.voice.file_id
            reply_type = "voice"
        # أغنية
        elif update.message.audio:
            content = update.message.audio.file_id
            reply_type = "audio"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        # ملف
        elif update.message.document:
            content = update.message.document.file_id
            reply_type = "document"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        else:
            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )
            return
        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO replies
            (
                name,
                text,
                type,
                caption,
                entities
            )
            VALUES (?, ?, ?, ?, ?)
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
        conn.close()
        invalidate_replies_cache()
        del add_reply_sessions[user_id]
        await update.message.reply_text(
            f"✅ تم إضافة الرد: {name}"
        )
        return
# ==================================================
# إرسال محتوى الرد
# ==================================================
async def send_reply_content(
    message,
    content,
    reply_type,
    caption=None,
    entities=None
):
    # --------------------------------------
    # نص
    # --------------------------------------
    if reply_type == "text":
        await message.reply_text(
            content,
            entities=entities
        )
    # --------------------------------------
    # صورة
    # --------------------------------------
    elif reply_type == "photo":
        await message.reply_photo(
            photo=content,
            caption=caption,
            caption_entities=entities
        )
    # --------------------------------------
    # فيديو
    # --------------------------------------
    elif reply_type == "video":
        await message.reply_video(
            video=content,
            caption=caption,
            caption_entities=entities
        )
    # --------------------------------------
    # متحركة
    # --------------------------------------
    elif reply_type == "animation":
        await message.reply_animation(
            animation=content,
            caption=caption,
            caption_entities=entities
        )
    # --------------------------------------
    # ملصق
    # --------------------------------------
    elif reply_type == "sticker":
        await message.reply_sticker(
            sticker=content
        )
    # --------------------------------------
    # بصمة
    # --------------------------------------
    elif reply_type == "voice":
        await message.reply_voice(
            voice=content
        )
    # --------------------------------------
    # أغنية
    # --------------------------------------
    elif reply_type == "audio":
        await message.reply_audio(
            audio=content,
            caption=caption,
            caption_entities=entities
        )
    # --------------------------------------
    # ملف
    # --------------------------------------
    elif reply_type == "document":
        await message.reply_document(
            document=content,
            caption=caption,
            caption_entities=entities
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
    user_name = (
        user.first_name
        or "مستخدم"
    )
    user_username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )
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
        # entities موجودة في العمود الخامس
        entities_json = (
            reply[4]
            if len(reply) > 4
            else None
        )
        if name.lower() in message_text:
            messages = 0
            rank = "عضو"
            points = 0
            needs_user_data = any(
                placeholder in (content or "")
                or placeholder in (caption or "")
                for placeholder in (
                    "#الرسائل",
                    "#الرتبه",
                    "#النقاط"
                )
            )
            if needs_user_data:
                conn = connect()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT messages, rank
                        FROM users
                        WHERE user_id=?
                        """,
                        (user.id,)
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
                    cur.execute(
                        """
                        SELECT points
                        FROM points
                        WHERE user_id=?
                        """,
                        (user.id,)
                    )
                    points_data = (
                        cur.fetchone()
                    )
                    if points_data:
                        points = (
                            points_data[0]
                            or 0
                        )
                finally:
                    conn.close()
            # --------------------------------------
            # تحويل entities
            # --------------------------------------
            entities = json_to_entities(
                entities_json
            )
            # --------------------------------------
            # النص
            # --------------------------------------
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
            # --------------------------------------
            # Caption
            # --------------------------------------
            else:
                if caption:
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
    messages = 0
    rank = "عضو"
    points = 0
    needs_user_data = any(
        placeholder in (content or "")
        or placeholder in (caption or "")
        for placeholder in (
            "#الرسائل",
            "#الرتبه",
            "#النقاط"
        )
    )
    if needs_user_data:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT messages, rank
                FROM users
                WHERE user_id=?
                """,
                (user.id,)
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
            cur.execute(
                """
                SELECT points
                FROM points
                WHERE user_id=?
                """,
                (user.id,)
            )
            points_data = cur.fetchone()
            if points_data:
                points = (
                    points_data[0]
                    or 0
                )
        finally:
            conn.close()
    entities = json_to_entities(
        entities_json
    )
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
    else:
        if caption:
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
        msg += f"• {item[0]}\n"
    await update.message.reply_text(msg)
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
    except:
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
    # --------------------------------------
    # الاسم
    # --------------------------------------
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
    # --------------------------------------
    # المحتوى
    # --------------------------------------
    if session.get("step") == "content":
        name = session["name"]
        content = None
        reply_type = None
        caption = None
        entities = None
        if update.message.text:
            content = update.message.text
            reply_type = "text"
            entities = entities_to_json(
                update.message.entities
            )
        elif update.message.photo:
            content = (
                update.message.photo[-1].file_id
            )
            reply_type = "photo"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.video:
            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.animation:
            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.sticker:
            content = update.message.sticker.file_id
            reply_type = "sticker"
        elif update.message.voice:
            content = update.message.voice.file_id
            reply_type = "voice"
        elif update.message.audio:
            content = update.message.audio.file_id
            reply_type = "audio"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.document:
            content = update.message.document.file_id
            reply_type = "document"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        else:
            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )
            return
        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO special_replies
            (
                name,
                text,
                type,
                caption,
                entities
            )
            VALUES (?, ?, ?, ?, ?)
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
        conn.close()
        invalidate_replies_cache()
        del add_special_reply_sessions[user_id]
        await update.message.reply_text(
            f"⭐ تم حفظ الرد المميز: {name}"
        )
        return
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
        "SELECT name FROM special_replies"
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
    await update.message.reply_text(text)
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
    # --------------------------------------
    # الاسم
    # --------------------------------------
    if session["step"] == "name":
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
    # --------------------------------------
    # المحتوى الجديد
    # --------------------------------------
    if session["step"] == "content":
        name = session["name"]
        content = None
        reply_type = None
        caption = None
        entities = None
        if update.message.text:
            content = update.message.text
            reply_type = "text"
            entities = entities_to_json(
                update.message.entities
            )
        elif update.message.photo:
            content = (
                update.message.photo[-1].file_id
            )
            reply_type = "photo"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.video:
            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.animation:
            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.sticker:
            content = update.message.sticker.file_id
            reply_type = "sticker"
        elif update.message.voice:
            content = update.message.voice.file_id
            reply_type = "voice"
        elif update.message.audio:
            content = update.message.audio.file_id
            reply_type = "audio"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.document:
            content = update.message.document.file_id
            reply_type = "document"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        else:
            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )
            return
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
        return
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
    # --------------------------------------
    # الاسم
    # --------------------------------------
    if session["step"] == "name":
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
    # --------------------------------------
    # المحتوى
    # --------------------------------------
    if session["step"] == "content":
        name = session["name"]
        content = None
        reply_type = None
        caption = None
        entities = None
        if update.message.text:
            content = update.message.text
            reply_type = "text"
            entities = entities_to_json(
                update.message.entities
            )
        elif update.message.photo:
            content = (
                update.message.photo[-1].file_id
            )
            reply_type = "photo"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.video:
            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.animation:
            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.sticker:
            content = update.message.sticker.file_id
            reply_type = "sticker"
        elif update.message.voice:
            content = update.message.voice.file_id
            reply_type = "voice"
        elif update.message.audio:
            content = update.message.audio.file_id
            reply_type = "audio"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        elif update.message.document:
            content = update.message.document.file_id
            reply_type = "document"
            caption = update.message.caption
            entities = entities_to_json(
                update.message.caption_entities
            )
        else:
            await update.message.reply_text(
                "❌ هذا النوع غير مدعوم"
            )
            return
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
        return
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
