from collections import deque

from telegram import Update
from telegram.ext import ContextTypes

from handlers.roles import get_rank_level


# ==================================================
# تخزين آخر رسائل كل قروب
# ==================================================

recent_messages = {}

MAX_TRACKED_MESSAGES = 1000


# ==================================================
# تسجيل الرسائل
# ==================================================

async def track_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in ("group", "supergroup"):
        return

    chat_id = chat.id

    if chat_id not in recent_messages:
        recent_messages[chat_id] = deque(
            maxlen=MAX_TRACKED_MESSAGES
        )

    message_id = update.message.message_id

    # منع التكرار
    if message_id not in recent_messages[chat_id]:
        recent_messages[chat_id].append(message_id)


# ==================================================
# حذف الرسائل
# ==================================================

async def delete_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    # ==================================================
    # القروبات فقط
    # ==================================================

    if chat.type not in ("group", "supergroup"):
        return

    text = update.message.text

    if not text:
        return

    text = text.strip()

    # ==================================================
    # الرتبة
    #
    # عضو       = 0
    # مميز      = 1
    # ادمن      = 2
    # ادمن اساسي = 3
    # نائب المالك = 4
    # المالك     = 5
    # Dev        = 6
    #
    # الادمن وفوق = 2+
    # ==================================================

    rank = get_rank_level(user.id)

    # ==================================================
    # مسح
    # ==================================================

    if text == "مسح":

        # لازم يكون رد على رسالة
        if not update.message.reply_to_message:
            return

        target_message = update.message.reply_to_message

        target_id = target_message.message_id
        command_id = update.message.message_id

        # ==================================================
        # الادمن وفوق
        # يحذف أي رسالة
        # ==================================================

        if rank >= 2:

            try:
                await context.bot.delete_message(
                    chat_id=chat.id,
                    message_id=target_id
                )
            except Exception:
                pass

            try:
                await context.bot.delete_message(
                    chat_id=chat.id,
                    message_id=command_id
                )
            except Exception:
                pass

            # إزالة الرسائل من الذاكرة
            if chat.id in recent_messages:

                recent_messages[chat.id] = deque(
                    (
                        msg_id
                        for msg_id in recent_messages[chat.id]
                        if msg_id not in (
                            target_id,
                            command_id
                        )
                    ),
                    maxlen=MAX_TRACKED_MESSAGES
                )

            return

        # ==================================================
        # العضو / المميز
        #
        # يحذف رسالته هو فقط
        # ==================================================

        if not target_message.from_user:
            return

        if target_message.from_user.id != user.id:
            # رسالة شخص آخر → تجاهل
            return

        # حذف رسالة العضو
        try:
            await context.bot.delete_message(
                chat_id=chat.id,
                message_id=target_id
            )
        except Exception:
            pass

        # حذف أمر مسح
        try:
            await context.bot.delete_message(
                chat_id=chat.id,
                message_id=command_id
            )
        except Exception:
            pass

        # إزالة من الذاكرة
        if chat.id in recent_messages:

            recent_messages[chat.id] = deque(
                (
                    msg_id
                    for msg_id in recent_messages[chat.id]
                    if msg_id not in (
                        target_id,
                        command_id
                    )
                ),
                maxlen=MAX_TRACKED_MESSAGES
            )

        return

    # ==================================================
    # لازم تكون الصيغة:
    #
    # مسح100
    # مسح 100
    #
    # إذا كانت شيء ثاني → تجاهل
    # ==================================================

    if not text.startswith("مسح"):
        return

    number_text = text[3:].strip()

    if not number_text:
        return

    if not number_text.isdigit():
        return

    # ==================================================
    # العدد للأدمن وفوق فقط
    #
    # المميز والعضو:
    # تجاهل كامل بدون أي رسالة
    # ==================================================

    if rank < 2:
        return

    amount = int(number_text)

    # ==================================================
    # الحد الأدنى
    # ==================================================

    if amount < 3:

        await update.message.reply_text(
            "الحد الادنى 3 رسائل ."
        )

        return

    # ==================================================
    # الحد الأقصى
    # ==================================================

    if amount > 800:

        await update.message.reply_text(
            "الحد الأقصى 800 رسالة ."
        )

        return

    command_id = update.message.message_id

    # ==================================================
    # الحصول على الرسائل السابقة
    #
    # نستخدم الرسائل التي سجلها البوت فعليًا
    # بدل الاعتماد على message_id المتسلسل
    # ==================================================

    tracked = recent_messages.get(chat.id)

    if not tracked:
        return

    # الرسائل الموجودة قبل أمر مسح
    previous_messages = [
        msg_id
        for msg_id in tracked
        if msg_id < command_id
    ]

    # نأخذ آخر amount رسالة
    targets = previous_messages[-amount:]

    if not targets:
        return

    # ==================================================
    # حذف الرسائل على دفعات
    # ==================================================

    deleted_ids = []

    for i in range(0, len(targets), 100):

        batch = targets[i:i + 100]

        try:

            await context.bot.delete_messages(
                chat_id=chat.id,
                message_ids=batch
            )

            deleted_ids.extend(batch)

        except Exception:

            # إذا فشلت الدفعة نحاول رسالة رسالة
            for message_id in batch:

                try:

                    await context.bot.delete_message(
                        chat_id=chat.id,
                        message_id=message_id
                    )

                    deleted_ids.append(message_id)

                except Exception:
                    pass

    # ==================================================
    # حذف أمر مسح نفسه
    # ==================================================

    try:

        await context.bot.delete_message(
            chat_id=chat.id,
            message_id=command_id
        )

        deleted_ids.append(command_id)

    except Exception:
        pass

    # ==================================================
    # تنظيف الذاكرة
    # ==================================================

    if chat.id in recent_messages:

        recent_messages[chat.id] = deque(
            (
                msg_id
                for msg_id in recent_messages[chat.id]
                if msg_id not in deleted_ids
            ),
            maxlen=MAX_TRACKED_MESSAGES
        )

    return

