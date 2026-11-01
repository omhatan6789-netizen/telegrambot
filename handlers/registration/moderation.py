
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

from handlers.command_guard import command_guard

from handlers.mandatory_subscription import (
    mandatory_subscription_guard,
    mandatory_subscription_commands,
)

from handlers.moderation import (
    check_muted_message,
    enable_durations_command,
    disable_durations_command,
    enable_reasons_command,
    disable_reasons_command,
    reveal_command,
    reveal_restrictions_command,
    moderation_command,
    unmute_command,
    unrestrict_command,
    unban_command,
    clear_restrictions_command,
    moderation_lists_command,
    clear_list_callback,
    warning_command,
    clear_warnings_command,
)

from handlers.blocked_words import (
    blocked_words_message_handler,
    blocked_words_callback,
)

from handlers.repetition import (
    repetition_message_handler,
    enable_repetition,
    disable_repetition,
    set_repetition_start,
    receive_repetition_duration,
    set_mute_duration,
    set_restrict_duration,
    set_repetition_rank,
    clear_user_repetition_warnings,
    repetition_action_callback,
)


def build_moderation_handlers(app):
    return [
        (
            9,
            -100,
            MessageHandler(
                filters.ChatType.GROUPS,
                mandatory_subscription_guard,
            ),
        ),
        (
            10,
            -90,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & filters.Regex(
                    r"^(?:ضع اجباري\s+.+|حذف اجباري\s+.+|مسح الاجباري|عرض الاجباري|الاجباري|تفعيل الاجباري|تعطيل الاجباري)$"
                ),
                mandatory_subscription_commands,
            ),
        ),
        (
            32,
            -22,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                command_guard,
            ),
        ),
        (
            33,
            -30,
            MessageHandler(
                filters.ChatType.GROUPS,
                check_muted_message,
            ),
        ),
        (
            34,
            -20,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تفعيل المدة للمشرفين$"),
                enable_durations_command,
            ),
        ),
        (
            35,
            -20,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تعطيل المدة للمشرفين$"),
                disable_durations_command,
            ),
        ),
        (
            36,
            -20,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تفعيل الاسباب$"),
                enable_reasons_command,
            ),
        ),
        (
            37,
            -20,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تعطيل الاسباب$"),
                disable_reasons_command,
            ),
        ),
        (
            39,
            -20,
            MessageHandler(
                filters.TEXT
                & (
                    filters.ChatType.GROUPS
                    | filters.ChatType.PRIVATE
                ),
                blocked_words_message_handler,
            ),
        ),
        (
            40,
            -20,
            CallbackQueryHandler(
                blocked_words_callback,
                pattern=r"^bw:",
            ),
        ),
        (
            41,
            -19,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(
                    r"^كشف(?:\s+@[A-Za-z0-9_]+|\s+\d+)?$"
                ),
                reveal_command,
            ),
        ),
        (
            42,
            -19,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(
                    r"^كشف القيود(?:\s+@[A-Za-z0-9_]+|\s+\d+)?$"
                ),
                reveal_restrictions_command,
            ),
        ),
        (
            43,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^(كتم|تقييد|حظر)(?:\s+.+)?$"),
                moderation_command,
            ),
        ),
        (
            44,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^الغاء الكتم(?:\s+.+)?$"),
                unmute_command,
            ),
        ),
        (
            45,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^الغاء التقييد(?:\s+.+)?$"),
                unrestrict_command,
            ),
        ),
        (
            46,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^الغاء الحظر(?:\s+.+)?$"),
                unban_command,
            ),
        ),
        (
            47,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^رفع القيود(?:\s+.+)?$"),
                clear_restrictions_command,
            ),
        ),
        (
            48,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^(المكتومين|المقيدين|المحظورين)$"),
                moderation_lists_command,
            ),
        ),
        (
            49,
            -18,
            CallbackQueryHandler(
                clear_list_callback,
                pattern=r"^moderation:clear:",
            ),
        ),
        (
            50,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^انذار(?:\s+.+)?$"),
                warning_command,
            ),
        ),
        (
            51,
            -18,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^مسح انذاراته$"),
                clear_warnings_command,
            ),
        ),
        (
            52,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تفعيل التكرار$"),
                enable_repetition,
            ),
        ),
        (
            53,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تعطيل التكرار$"),
                disable_repetition,
            ),
        ),
        (
            54,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^ضع تكرار \d+$"),
                set_repetition_start,
            ),
        ),
        (
            55,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^ضع كتم تكرار \S+$"),
                set_mute_duration,
            ),
        ),
        (
            56,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^ضع تقييد تكرار \S+$"),
                set_restrict_duration,
            ),
        ),
        (
            57,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(
                    r"^(?:ضع|تغيير) رتبة التكرار "
                    r"(عضو|مميز|ادمن|ادمن اساسي|نائب المالك|المالك|Dev)$"
                ),
                set_repetition_rank,
            ),
        ),
        (
            58,
            -17,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^مسح انذاراته$"),
                clear_user_repetition_warnings,
            ),
        ),
        (
            59,
            -17,
            CallbackQueryHandler(
                repetition_action_callback,
                pattern=r"^repetition_punish:(?:mute|restrict):\d+$",
            ),
        ),
        (
            60,
            -16,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                receive_repetition_duration,
            ),
        ),
        (
            61,
            -15,
            MessageHandler(
                filters.ChatType.GROUPS,
                repetition_message_handler,
            ),
        ),
    ]
