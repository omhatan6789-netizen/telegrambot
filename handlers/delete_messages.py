from telegram import Update
from telegram.ext import ContextTypes
from handlers.roles import get_rank_level


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

    # ==========================================
    # القروبات فقط
    # ==========================================

    if chat.type not in ("group", "supergroup"):
        return

    # ==========================================
    # الرتبة
    # ==========================================

    rank = get_rank_level(user.id)

    text = update.message.text.strip()

    # ==========================================
    # مسح بالرد على رسالة
    # ==========================================

    if text == "مسح":

        # لازم يكون رد على رسالة
        if not update.message.reply_to_message:
            return

        target_message = update.message.reply_to_message

        # ==========================================
        # الأدمن وفوق
        # يقدر يحذف أي رسالة
        # ==========================================

        if rank > 0:

            target_id = target_message.message_id
            command_id = update.message.message_id

            # حذف الرسالة المحددة
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

            return

        # ==========================================
        # العضو / المميز
        #
        # يسمح له بحذف رسالته هو فقط
        # ==========================================

        if target_message.from_user:

            if target_message.from_user.id != user.id:
                # رسالة شخص ثاني → تجاهل تمامًا
                return

        else:
            return

        target_id = target_message.message_id
        command_id = update.message.message_id

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

        return

    # ==========================================
    # مسح + عدد
    #
    # مسح100
    # مسح 100
    # ==========================================

    if not text.startswith("مسح"):
        return

    number_text = text[3:].strip()

    # أي صيغة غير رقمية يتم تجاهلها
    if not number_text.isdigit():
        return

    amount = int(number_text)

    # ==========================================
    # الحد الأدنى
    # ==========================================

    if amount < 3:

        # فقط الأدمن وفوق يشوفون الرسالة
        if rank > 0:

            await update.message.reply_text(
                "الحد الادنى 3 رسائل ."
            )

        return

    # ==========================================
    # الحد الأقصى
    # ==========================================

    if amount > 800:

        # فقط الأدمن وفوق يشوفون الرسالة
        if rank > 0:

            await update.message.reply_text(
                "الحد الأقصى 800 رسالة ."
            )

        return

    # ==========================================
    # المسح بالعدد للأدمن وفوق فقط
    # ==========================================

    if rank <= 0:
        return

    command_id = update.message.message_id

    # ==========================================
    # الرسائل المطلوب حذفها
    #
    # مسح100
    #
    # 100 رسالة قبل الأمر
    # + أمر مسح100 نفسه
    # ==========================================

    message_ids = list(
        range(
            command_id - amount,
            command_id + 1
        )
    )

    # ==========================================
    # الحذف على دفعات
    # ==========================================

    for i in range(0, len(message_ids), 100):

        batch = message_ids[i:i + 100]

        try:

            await context.bot.delete_messages(
                chat_id=chat.id,
                message_ids=batch
            )

        except Exception:

            # إذا فشلت الدفعة نحاول واحدة واحدة
            for message_id in batch:

                try:

                    await context.bot.delete_message(
                        chat_id=chat.id,
                        message_id=message_id
                    )

                except Exception:
                    pass

    return

