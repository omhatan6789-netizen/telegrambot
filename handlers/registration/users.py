
from telegram.ext import (
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    filters,
)

from handlers.users import (
    user_id_command,
    save_join_date,
    save_user_message,
)

from handlers.roles import (
    roles_command,
    change_rank,
    dev_list_command,
    rank_list_command,
    clear_dev_command,
    clear_rank_command,
    clear_all_ranks_command,
    roles_clear_callback,
)


def build_users_handlers(app):
    handlers = [
        # ايدي المستخدم
        (
            72,
            0,
            MessageHandler(
                filters.Regex(r"^ايدي$"),
                user_id_command
            )
        ),

        # رتبتي / رتبته
        (
            73,
            0,
            MessageHandler(
                filters.Regex(
                    r"^(رتبتي|رتبته(?:\s+@[A-Za-z0-9_]+|\s+\d+)?)$"
                ),
                roles_command
            )
        ),

        # قوائم الرتب
        (
            74,
            -9,
            MessageHandler(
                filters.Regex(r"^قائمة (?:Dev|dev)$"),
                dev_list_command
            )
        ),

        (
            75,
            -9,
            MessageHandler(
                filters.Regex(
                    r"^(المميزين|الادمنية|الادمنية الاساسيين|نواب المالك|المالكين)$"
                ),
                rank_list_command
            )
        ),

        # مسح الرتب
        (
            76,
            -9,
            MessageHandler(
                filters.Regex(r"^مسح (?:Dev|dev)$"),
                clear_dev_command
            )
        ),

        (
            77,
            -9,
            MessageHandler(
                filters.Regex(
                    r"^مسح (?:المميزين|الادمنية|الادمنية الاساسيين|نواب المالك|المالكين)$"
                ),
                clear_rank_command
            )
        ),

        (
            78,
            -9,
            MessageHandler(
                filters.Regex(r"^مسح الرتب$"),
                clear_all_ranks_command
            )
        ),

        (
            79,
            -9,
            CallbackQueryHandler(
                roles_clear_callback,
                pattern=r"^roles_clear:"
            )
        ),

        # كشف المجموعة
        (
            92,
            0,
            MessageHandler(
                filters.Regex(r"^كشف المجموعة$"),
                roles_command
            )
        ),

        # تنزيل جميع الرتب
        (
            93,
            -9,
            MessageHandler(
                filters.Regex(r"^تنزيل الكل$"),
                change_rank
            )
        ),

        # رفع / تنزيل الرتب
        (
            94,
            0,
            MessageHandler(
                filters.Regex(
                    r"^(رفع|تنزيل) "
                    r"(Dev|المالك|نائب المالك|ادمن اساسي|ادمن|مميز)"
                    r"(?:\s+(@[A-Za-z0-9_]+|\d+))?$"
                ),
                change_rank
            )
        ),

        # تسجيل انضمام الأعضاء
        (
            165,
            0,
            ChatMemberHandler(
                save_join_date,
                ChatMemberHandler.CHAT_MEMBER
            )
        ),

        # حفظ رسائل المستخدمين
        (
            166,
            50,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                save_user_message
            )
        ),
    ]

    return handlers
