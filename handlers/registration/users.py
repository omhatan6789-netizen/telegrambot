
from telegram.ext import MessageHandler, ChatMemberHandler, CallbackQueryHandler, filters

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
    return [
        (72, 0, MessageHandler(
            filters.Regex(r"^ايدي$"),
            user_id_command
        )),

        (73, 0, MessageHandler(
            filters.Regex(
                r"^(رتبتي|رتبته(?:\s+@[A-Za-z0-9_]+|\s+\d+)?)$"
            ),
            roles_command
        )),

        (74, -9, MessageHandler(
            filters.Regex(r"^قائمة (?:Dev|dev)$"),
            dev_list_command
        )),

        (75, -9, MessageHandler(
            filters.Regex(
                r"^(المميزين|الادمنية|الادمنية الاساسيين|نواب المالك|المالكين)$"
            ),
            rank_list_command
        )),

        (76, -9, MessageHandler(
            filters.Regex(r"^مسح (?:Dev|dev)$"),
            clear_dev_command
        )),

        (77, -9, MessageHandler(
            filters.Regex(
                r"^مسح (?:المميزين|الادمنية|الادمنية الاساسيين|نواب المالك|المالكين)$"
            ),
            clear_rank_command
        )),

        (78, -9, MessageHandler(
            filters.Regex(r"^مسح الرتب$"),
            clear_all_ranks_command
        )),

        (79, -9, CallbackQueryHandler(
            roles_clear_callback,
            pattern=r"^roles_clear:"
        )),

        (93, 0, MessageHandler(
            filters.Regex(r"^كشف المجموعة$"),
            roles_command
        )),

        (94, -9, MessageHandler(
            filters.Regex(r"^تنزيل الكل$"),
            change_rank
        )),

        (95, 0, MessageHandler(
            filters.Regex(
                r"^(رفع|تنزيل) "
                r"(Dev|المالك|نائب المالك|ادمن اساسي|ادمن|مميز)"
                r"(?:\s+(@[A-Za-z0-9_]+|\d+))?$"
            ),
            change_rank
        )),

        (166, 0, ChatMemberHandler(
            save_join_date,
            ChatMemberHandler.CHAT_MEMBER
        )),

        (167, 50, MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_user_message
        )),
    ]
