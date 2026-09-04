from telegram import Update
from telegram.ext import ContextTypes
from permissions import is_admin
from database import connect

# جلسات إضافة الردود
add_reply_sessions = {}
add_special_reply_sessions = {}
delete_special_reply_sessions = {}
edit_special_reply_sessions = {}
edit_reply_sessions = {}
delete_reply_sessions = {}

# =========================
# Cache للردود
# =========================
replies_cache = None
special_replies_cache = None
def load_replies_cache():
    global replies_cache
    global special_replies_cache
    conn = connect()
    try:
        cur = conn.cursor()
        # الردود العادية
        cur.execute(
            """
            SELECT name, text, type, caption
            FROM replies
            """
        )
        rows = cur.fetchall()
        replies_cache = {
            row[0]: (
                row[1],
                row[2],
                row[3]
            )
            for row in rows
        }
        # الردود المميزة
        cur.execute(
            """
            SELECT name, text, type, caption
            FROM special_replies
            """
        )
        special_rows = cur.fetchall()
        special_replies_cache = special_rows
        cur.close()
    finally:
        conn.close()
def invalidate_replies_cache():
    """
    تحديث كاش الردود مباشرة بعد الإضافة
    أو التعديل أو الحذف.
    """
    # نعيد تحميل الكاش فورًا
    # حتى الرد الجديد يشتغل بدون إعادة تشغيل البوت
    load_replies_cache()
def get_replies_cache():
    global replies_cache
    global special_replies_cache
    if replies_cache is None or special_replies_cache is None:
        load_replies_cache()
    return replies_cache, special_replies_cache

# =====================
# بدء إضافة رد
# =====================

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

    # =====================
    # إلغاء جلسات الألعاب
    # =====================

    try:

        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )

        add_game_sessions.pop(user_id, None)
        add_question_sessions.pop(user_id, None)

    except:
        pass

    # =====================
    # إلغاء أي جلسة رد قديمة
    # =====================

    add_reply_sessions.pop(user_id, None)

    # =====================
    # بدء جلسة جديدة
    # =====================

    add_reply_sessions[user_id] = {

        "step": "name"

    }

    await update.message.reply_text(
        "حسنًا، ارسل اسم الرد"
    )

# =====================
# إضافة الرد
# =====================

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

    # منع تكرار أمر الإضافة
    if update.message.text == "اضف رد":
        return

    # =====================
    # اسم الرد
    # =====================

    if session["step"] == "name":

        if not update.message.text:

            await update.message.reply_text(
                "❌ أرسل الاسم كنص"
            )

            return

        session["name"] = update.message.text.strip()

        session["step"] = "content"

        await update.message.reply_text(
            "• حسناً يمكنك اضافة\n"
            "( نص, صوره, فيديو, متحركه, بصمه, اغنيه, ملف )\n\n"
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

    # =====================
    # محتوى الرد
    # =====================

    if session["step"] == "content":

        name = session["name"]

        content = None
        reply_type = None
        caption = None

        if update.message.text:

            content = update.message.text
            reply_type = "text"

        elif update.message.photo:

            content = update.message.photo[-1].file_id
            reply_type = "photo"
            caption = update.message.caption

        elif update.message.video:

            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption

        elif update.message.animation:

            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption

        elif update.message.sticker:

            content = update.message.sticker.file_id
            reply_type = "sticker"

        elif update.message.voice:

            content = update.message.voice.file_id
            reply_type = "voice"

        elif update.message.audio:

            content = update.message.audio.file_id
            reply_type = "audio"

        elif update.message.document:

            content = update.message.document.file_id
            reply_type = "document"

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
                caption
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT (name)
            DO UPDATE SET
                text = EXCLUDED.text,
                type = EXCLUDED.type,
                caption = EXCLUDED.caption
            """,
            (
                name,
                content,
                reply_type,
                caption
            )
        )

        conn.commit()
        conn.close()

        invalidate_replies_cache()

        del add_reply_sessions[user_id]

        await update.message.reply_text(
            f"✅ تم إضافة الرد: {name}"
        )

        return

# =====================
# تشغيل الردود
# =====================

async def check_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    message_text = update.message.text.lower()

    user = update.effective_user

    user_name = user.first_name or "مستخدم"

    user_username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )

    # =====================
    # Cache الردود
    # =====================

    replies_cache, special_replies = get_replies_cache()

    # =====================
    # استبدال البيانات
    # =====================

    def replace_data(
        text,
        messages=0,
        rank="عضو",
        points=0
    ):

        if not text:
            return text

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
            str(user.id)
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

    # =====================
    # الردود المميزة
    # =====================

    for reply in special_replies:

        name = reply[0]
        content = reply[1]
        reply_type = reply[2]
        caption = reply[3]

        if name.lower() in message_text:

            # =====================
            # بيانات المستخدم
            # يتم جلبها فقط عند الحاجة
            # =====================

            messages = 0
            rank = "عضو"
            points = 0

            needs_user_data = any(
                placeholder in (content or "") or
                placeholder in (caption or "")
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

                        messages = user_data[0] or 0

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

            content = replace_data(
                content,
                messages,
                rank,
                points
            )

            caption = replace_data(
                caption,
                messages,
                rank,
                points
            )

            # =====================
            # إرسال الرد
            # =====================

            if reply_type == "text":

                await update.message.reply_text(
                    content
                )

            elif reply_type == "photo":

                await update.message.reply_photo(
                    photo=content,
                    caption=caption
                )

            elif reply_type == "video":

                await update.message.reply_video(
                    video=content,
                    caption=caption
                )

            elif reply_type == "animation":

                await update.message.reply_animation(
                    animation=content,
                    caption=caption
                )

            elif reply_type == "sticker":

                await update.message.reply_sticker(
                    sticker=content
                )

            elif reply_type == "voice":

                await update.message.reply_voice(
                    voice=content
                )

            elif reply_type == "audio":

                await update.message.reply_audio(
                    audio=content
                )

            elif reply_type == "document":

                await update.message.reply_document(
                    document=content
                )

            return

    # =====================
    # الردود العادية
    # =====================

    reply = replies_cache.get(
        update.message.text
    )

    if not reply:

        return

    content = reply[0]
    reply_type = reply[1]
    caption = reply[2]

    # =====================
    # بيانات المستخدم
    # يتم جلبها فقط عند الحاجة
    # =====================

    messages = 0
    rank = "عضو"
    points = 0

    needs_user_data = any(
        placeholder in (content or "") or
        placeholder in (caption or "")
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

    content = replace_data(
        content,
        messages,
        rank,
        points
    )

    caption = replace_data(
        caption,
        messages,
        rank,
        points
    )

    # =====================
    # إرسال الرد
    # =====================

    if reply_type == "text":

        await update.message.reply_text(
            content
        )

    elif reply_type == "photo":

        await update.message.reply_photo(
            photo=content,
            caption=caption
        )

    elif reply_type == "video":

        await update.message.reply_video(
            video=content,
            caption=caption
        )

    elif reply_type == "animation":

        await update.message.reply_animation(
            animation=content,
            caption=caption
        )

    elif reply_type == "sticker":

        await update.message.reply_sticker(
            sticker=content
        )

    elif reply_type == "voice":

        await update.message.reply_voice(
            voice=content
        )

    elif reply_type == "audio":

        await update.message.reply_audio(
            audio=content,
            caption=caption
        )

    elif reply_type == "document":

        await update.message.reply_document(
            document=content,
            caption=caption
        )

# =====================
# قائمة الردود
# =====================

async def replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
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

async def add_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not is_admin(update.effective_user.id):

        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return

    user_id = update.effective_user.id

    # =====================
    # إلغاء جلسات الألعاب
    # =====================

    try:

        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )

        add_game_sessions.pop(user_id, None)
        add_question_sessions.pop(user_id, None)

    except:
        pass

    # =====================
    # إلغاء أي جلسة قديمة
    # =====================

    add_special_reply_sessions.pop(
        user_id,
        None
    )

    # =====================
    # بدء جلسة جديدة
    # =====================

    add_special_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز"
    )

async def add_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    # تجاهل أمر البداية
    if update.message.text == "اضف رد مميز":
        return

    user_id = update.effective_user.id

    if user_id not in add_special_reply_sessions:
        return

    session = add_special_reply_sessions[user_id]

    # =====================
    # اسم الرد
    # =====================

    if session.get("step") == "name":

        if not update.message.text:

            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )

            return

        session["name"] = update.message.text.strip()

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

    # =====================
    # محتوى الرد
    # =====================

    if session.get("step") == "content":

        name = session["name"]

        content = None
        reply_type = None
        caption = None

        if update.message.text:

            content = update.message.text
            reply_type = "text"

        elif update.message.photo:

            content = update.message.photo[-1].file_id
            reply_type = "photo"
            caption = update.message.caption

        elif update.message.video:

            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption

        elif update.message.animation:

            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption

        elif update.message.sticker:

            content = update.message.sticker.file_id
            reply_type = "sticker"

        elif update.message.voice:

            content = update.message.voice.file_id
            reply_type = "voice"

        elif update.message.audio:

            content = update.message.audio.file_id
            reply_type = "audio"

        elif update.message.document:

            content = update.message.document.file_id
            reply_type = "document"

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
                caption
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT (name)
            DO UPDATE SET
                text = EXCLUDED.text,
                type = EXCLUDED.type,
                caption = EXCLUDED.caption
            """,
            (
                name,
                content,
                reply_type,
                caption
            )
        )

        conn.commit()
        conn.close()

        invalidate_replies_cache()

        del add_special_reply_sessions[user_id]

        await update.message.reply_text(
            f"⭐ تم حفظ الرد المميز: {name}"
        )

        return

async def special_replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
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

    conn.close()

    if not replies:

        await update.message.reply_text(
            "📭 لا توجد ردود مميزة"
        )

        return

    text = "⭐ قائمة الردود المميزة:\n\n"

    for reply in replies:

        text += f"• {reply[0]}\n"

    await update.message.reply_text(text)

async def delete_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return

    user_id = update.effective_user.id

    delete_special_reply_sessions[user_id] = True

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد حذفه"
    )

async def delete_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
 
               
    if not update.message:
        return

    if update.message.text == "مسح رد مميز":
        return

    user_id = update.effective_user.id

    if user_id not in delete_special_reply_sessions:
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
    conn.close()

    invalidate_replies_cache()

    del delete_special_reply_sessions[user_id]

    if deleted:

        await update.message.reply_text(
            f"✅ تم حذف الرد المميز: {name}"
        )

    else:

        await update.message.reply_text(
            "❌ لم أجد رد مميز بهذا الاسم"
        )

async def edit_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return

    user_id = update.effective_user.id

    edit_special_reply_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد تعديله"
    )

async def edit_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
     

    if not update.message:
        return

    # تجاهل رسالة بدء الأمر
    if update.message.text == "تعديل رد مميز":
        return

    user_id = update.effective_user.id

    if user_id not in edit_special_reply_sessions:
        return

    session = edit_special_reply_sessions[user_id]

    # =====================
    # اسم الرد القديم
    # =====================

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

        conn.close()

        if not reply:

            await update.message.reply_text(
                "❌ لا يوجد رد مميز بهذا الاسم"
            )

            del edit_special_reply_sessions[user_id]

            return

        session["name"] = name
        session["step"] = "content"

        await update.message.reply_text(
            "✅ تم العثور على الرد\n\n"
            "أرسل المحتوى الجديد للرد المميز"
        )

        return

    if session["step"] == "content":

        name = session["name"]

        content = None
        reply_type = None
        caption = None

        if update.message.text:

            content = update.message.text
            reply_type = "text"

        elif update.message.photo:

            content = update.message.photo[-1].file_id
            reply_type = "photo"
            caption = update.message.caption

        elif update.message.video:

            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption

        elif update.message.animation:

            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption

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

        elif update.message.document:

            content = update.message.document.file_id
            reply_type = "document"
            caption = update.message.caption

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
            SET text = ?, type = ?, caption = ?
            WHERE name = ?
            """,
            (
                content,
                reply_type,
                caption,
                name
            )
        )

        conn.commit()
        conn.close()

        invalidate_replies_cache()

        del edit_special_reply_sessions[user_id]

        await update.message.reply_text(
            f"⭐ تم تعديل الرد المميز: {name}"
        )

        return

async def edit_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
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

async def edit_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return

    # تجاهل أمر البداية
    if update.message.text == "تعديل رد":
        return

    user_id = update.effective_user.id

    if user_id not in edit_reply_sessions:
        return

    session = edit_reply_sessions[user_id]

    # =====================
    # اسم الرد
    # =====================

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

    # =====================
    # المحتوى الجديد
    # =====================

    if session["step"] == "content":

        name = session["name"]

        content = None
        reply_type = None
        caption = None

        if update.message.text:

            content = update.message.text
            reply_type = "text"

        elif update.message.photo:

            content = update.message.photo[-1].file_id
            reply_type = "photo"
            caption = update.message.caption

        elif update.message.video:

            content = update.message.video.file_id
            reply_type = "video"
            caption = update.message.caption

        elif update.message.animation:

            content = update.message.animation.file_id
            reply_type = "animation"
            caption = update.message.caption

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

        elif update.message.document:

            content = update.message.document.file_id
            reply_type = "document"
            caption = update.message.caption

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
            SET text = ?, type = ?, caption = ?
            WHERE name = ?
            """,
            (
                content,
                reply_type,
                caption,
                name
            )
        )

        conn.commit()
        conn.close()

        invalidate_replies_cache()

        del edit_reply_sessions[user_id]

        await update.message.reply_text(
            f"✅ تم تعديل الرد: {name}"
        )

        return

async def delete_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return

    user_id = update.effective_user.id

    delete_reply_sessions[user_id] = True

    await update.message.reply_text(
        "🗑️ أرسل اسم الرد الذي تريد حذفه"
    )

async def delete_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return

    # تجاهل أمر البداية
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
    conn.close()

    invalidate_replies_cache()

    del delete_reply_sessions[user_id]

    await update.message.reply_text(
        f"✅ تم حذف الرد: {name}"
    )

async def delete_all_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
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
    conn.close()

    invalidate_replies_cache()

    await update.message.reply_text(
        "✅ تم حذف جميع الردود العادية"
    )

async def delete_all_special_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update.effective_user.id):
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
    conn.close()

    invalidate_replies_cache()

    await update.message.reply_text(
        "⭐ تم حذف جميع الردود المميزة"
    ) 
