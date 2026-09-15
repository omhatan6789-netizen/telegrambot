from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.ext import MessageHandler

from database import connect


OWNER_ID = 8453977662

WAIT_OLD, WAIT_NEW = range(2)

add_command_sessions = {}


# ==================================================
# إضافة أمر
# ==================================================

async def add_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = update.effective_user.id

    add_command_sessions[user_id] = {}

    await update.message.reply_text(
        "حسناً، أرسل الأمر القديم"
    )

    return WAIT_OLD


# ==================================================
# استقبال الأمر القديم
# ==================================================

async def receive_old_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id not in add_command_sessions:
        return WAIT_OLD

    if not update.message or not update.message.text:
        return WAIT_OLD

    old = update.message.text.strip()

    if not old:
        await update.message.reply_text(
            "• أرسل الأمر القديم"
        )
        return WAIT_OLD

    add_command_sessions[user_id]["old"] = old

    await update.message.reply_text(
        "حسناً، أرسل الأمر الجديد"
    )

    return WAIT_NEW


# ==================================================
# استقبال الأمر الجديد
# ==================================================

async def receive_new_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id not in add_command_sessions:
        return ConversationHandler.END

    if not update.message or not update.message.text:
        return WAIT_NEW

    new = update.message.text.strip()

    if not new:
        await update.message.reply_text(
            "• أرسل الأمر الجديد"
        )
        return WAIT_NEW

    old = add_command_sessions[user_id]["old"]

    if old == new:
        await update.message.reply_text(
            "• الأمر الجديد لازم يكون مختلف عن الأمر القديم"
        )
        return WAIT_NEW

    conn = connect()
    cur = conn.cursor()

    # إذا كان الاختصار موجودًا من قبل
    # يتم تحديثه بدل إنشاء نسخة ثانية
    cur.execute(
        """
        DELETE FROM custom_commands
        WHERE new_command = ?
        """,
        (new,)
    )

    cur.execute(
        """
        INSERT INTO custom_commands
        (
            old_command,
            new_command
        )
        VALUES (?, ?)
        """,
        (
            old,
            new
        )
    )

    conn.commit()
    conn.close()

    del add_command_sessions[user_id]

    await update.message.reply_text(
        f"✅ تم إضافة الأمر\n\n"
        f"{new} يعمل الآن مثل {old}"
    )

    return ConversationHandler.END


# ==================================================
# قائمة الأوامر
# ==================================================

async def custom_commands_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT old_command, new_command
        FROM custom_commands
        ORDER BY new_command
        """
    )

    data = cur.fetchall()

    conn.close()

    if not data:
        await update.message.reply_text(
            "لا توجد أوامر مضافة"
        )
        return

    text = "📌 الأوامر المضافة:\n\n"

    for old, new in data:
        text += f"{new} ➜ {old}\n"

    await update.message.reply_text(text)


# ==================================================
# حذف أمر
# ==================================================

async def delete_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "أرسل الأمر الجديد الذي تريد حذفه"
    )

    context.user_data["delete_command"] = True


async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get("delete_command"):
        return

    if not update.message or not update.message.text:
        return

    command = update.message.text.strip()

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM custom_commands
        WHERE new_command = ?
        """,
        (command,)
    )

    deleted = cur.rowcount

    conn.commit()
    conn.close()

    context.user_data.pop(
        "delete_command",
        None
    )

    if deleted:
        await update.message.reply_text(
            "✅ تم حذف الأمر المضاف"
        )
    else:
        await update.message.reply_text(
            "• ما لقيت هذا الأمر ضمن الأوامر المضافة"
        )


# ==================================================
# حذف جميع الأوامر
# ==================================================

async def delete_all_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM custom_commands"
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ تم حذف جميع الأوامر المضافة"
    )


# ==================================================
# جلب الأمر الأصلي
# ==================================================

def get_custom_command(text):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT old_command
        FROM custom_commands
        WHERE new_command = ?
        LIMIT 1
        """,
        (text,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return None

    return result[0]


# ==================================================
# التحقق هل الـ Handler عبارة عن Handler عام
# ==================================================

def is_generic_handler(handler):

    callback = getattr(
        handler,
        "callback",
        None
    )

    if callback is None:
        return True

    name = getattr(
        callback,
        "__name__",
        ""
    )

    # هذه Handlers تستقبل إجابات/رسائل عامة
    # وليست أوامر بداية
    generic_names = {
        "check_speed_words",
        "check_anime_answer",
        "check_game_answer",
        "check_word_race_message",
        "check_liar_message",
        "check_replies",
        "save_user_message",
        "play_game",
        "add_reply_handler",
        "add_special_reply_handler",
        "edit_reply_handler",
        "edit_special_reply_handler",
        "delete_reply_handler",
        "delete_special_reply_handler",
        "add_game_handler",
        "add_question_handler",
        "delete_command",
        "save_lock_rank",
    }

    return name in generic_names


# ==================================================
# تشغيل الـ Handler الخاص بالأمر
# ==================================================

async def check_custom_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return False

    if not update.message.text:
        return False

    text = update.message.text.strip()

    old_command = get_custom_command(text)

    if not old_command:
        return False

    application = context.application

    # --------------------------------------------------
    # نبحث عن Handler يطابق الأمر الأصلي
    # --------------------------------------------------

    for group in sorted(application.handlers.keys()):

        handlers = application.handlers[group]

        for handler in handlers:

            # ConversationHandler يتم التعامل معه
            # بشكل منفصل
            if isinstance(
                handler,
                ConversationHandler
            ):
                continue

            # لا نختار الـ handlers العامة
            if is_generic_handler(handler):
                continue

            try:
                check_result = handler.check_update(
                    _make_fake_update(
                        update,
                        old_command
                    )
                )
            except Exception:
                continue

            if not check_result:
                continue

            callback = getattr(
                handler,
                "callback",
                None
            )

            if callback is None:
                continue

            fake_update = _make_fake_update(
                update,
                old_command
            )

            try:

                await callback(
                    fake_update,
                    context
                )

                return True

            except Exception as e:

                print(
                    "⚠️ خطأ في الأمر المضاف "
                    f"{text} -> {old_command}: {e}"
                )

                return True

    return False


# ==================================================
# إنشاء Update مؤقت
# ==================================================

def _make_fake_update(
    update,
    text
):

    message = update.message

    # Message objects في PTB يمكن نسخها
    # ونبقي جميع معلومات المستخدم والقروب
    # كما هي، ونغير النص فقط.

    fake_message = message.__class__(
        message_id=message.message_id,
        date=message.date,
        chat=message.chat,
        from_user=message.from_user,
        sender_chat=message.sender_chat,
        text=text,
        entities=message.entities,
        caption=message.caption,
        caption_entities=message.caption_entities,
        photo=message.photo,
        audio=message.audio,
        document=message.document,
        video=message.video,
        video_note=message.video_note,
        voice=message.voice,
        contact=message.contact,
        location=message.location,
        venue=message.venue,
        sticker=message.sticker,
        animation=message.animation,
        reply_to_message=message.reply_to_message,
        pinned_message=message.pinned_message,
        quote=message.quote,
        reply_markup=message.reply_markup,
        edit_date=message.edit_date,
        media_group_id=message.media_group_id,
        author_signature=message.author_signature,
        forward_origin=message.forward_origin,
        is_topic_message=message.is_topic_message,
        message_thread_id=message.message_thread_id,
        via_bot=message.via_bot,
        has_protected_content=message.has_protected_content,
        is_automatic_forward=message.is_automatic_forward,
        has_media_spoiler=message.has_media_spoiler,
        link_preview_options=message.link_preview_options,
        effect_id=message.effect_id,
        business_connection_id=message.business_connection_id,
        direct_messages_topic=message.direct_messages_topic,
        suggested_post_info=message.suggested_post_info,
    )

    return Update(
        update_id=update.update_id,
        message=fake_message
    )
