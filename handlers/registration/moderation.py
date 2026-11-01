
from telegram.ext import (
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from handlers.command_guard import command_guard

from handlers.moderation import (
    moderation_command,
    check_muted_message,
    unmute_command,
    unrestrict_command,
    unban_command,
    clear_restrictions_command,
    moderation_lists_command,
    clear_list_callback,
    enable_durations_command,
    disable_durations_command,
    enable_reasons_command,
    disable_reasons_command,
    warning_command,
    clear_warnings_command,
    reveal_restrictions_command,
    reveal_command,
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
    set_mute_duration,
    set_restrict_duration,
    set_repetition_rank,
    clear_user_repetition_warnings,
    repetition_action_callback,
    receive_repetition_duration,
)

from handlers.mandatory_subscription import (
    mandatory_subscription_guard,
    mandatory_subscription_commands,
)


def build_moderation_handlers(app):
    handlers = []

    # ==================================================
    # حارس الأوامر
    # ==================================================

    handlers.append((
        100,
        -22,
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            command_guard,
        ),
    ))

    # ==================================================
    # الاشتراك الإجباري
    # ==================================================

    handlers.append((
        200,
        -100,
        MessageHandler(
            filters.ChatType.GROUPS,
            mandatory_subscription_guard,
        ),
    ))

    handlers.append((
        210,
        -90,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & filters.Regex(
                r"^(?:ضع اجباري\s+.+|حذف اجباري\s+.+|مسح الاجباري|عرض الاجباري|الاجباري|تفعيل الاجباري|تعطيل الاجباري)$"
            ),
            mandatory_subscription_commands,
        ),
    ))

    # ==================================================
    # الكتم
    # ==================================================

    handlers.append((
        300,
        -30,
        MessageHandler(
            filters.ChatType.GROUPS,
            check_muted_message,
        ),
    ))

    # ==================================================
    # إعدادات المدة والأسباب
    # ==================================================

    handlers.append((
        400,
        -20,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تفعيل المدة للمشرفين$"),
            enable_durations_command,
        ),
    ))

    handlers.append((
        410,
        -20,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تعطيل المدة للمشرفين$"),
            disable_durations_command,
        ),
    ))

    handlers.append((
        420,
        -20,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تفعيل الاسباب$"),
            enable_reasons_command,
        ),
    ))

    handlers.append((
        430,
        -20,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تعطيل الاسباب$"),
            disable_reasons_command,
        ),
    ))

    # ==================================================
    # الكلمات المحظورة
    # ==================================================

    handlers.append((
        440,
        -20,
        MessageHandler(
            filters.TEXT
            & (
                filters.ChatType.GROUPS
                | filters.ChatType.PRIVATE
            ),
            blocked_words_message_handler,
        ),
    ))

    handlers.append((
        450,
        -20,
        CallbackQueryHandler(
            blocked_words_callback,
            pattern=r"^bw:",
        ),
    ))

    # ==================================================
    # كشف
    # ==================================================

    handlers.append((
        500,
        -19,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^كشف(?:\s+@[A-Za-z0-9_]+|\s+\d+)?$"
            ),
            reveal_command,
        ),
    ))

    # ==================================================
    # كشف القيود
    # ==================================================

    handlers.append((
        510,
        -19,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^كشف القيود(?:\s+@[A-Za-z0-9_]+|\s+\d+)?$"
            ),
            reveal_restrictions_command,
        ),
    ))

    # ==================================================
    # الكتم والتقييد والحظر
    # ==================================================

    handlers.append((
        600,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^(كتم|تقييد|حظر)(?:\s+.+)?$"
            ),
            moderation_command,
        ),
    ))

    handlers.append((
        610,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^الغاء الكتم(?:\s+.+)?$"
            ),
            unmute_command,
        ),
    ))

    handlers.append((
        620,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^الغاء التقييد(?:\s+.+)?$"
            ),
            unrestrict_command,
        ),
    ))

    handlers.append((
        630,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^الغاء الحظر(?:\s+.+)?$"
            ),
            unban_command,
        ),
    ))

    handlers.append((
        640,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^رفع القيود(?:\s+.+)?$"
            ),
            clear_restrictions_command,
        ),
    ))

    handlers.append((
        650,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^(المكتومين|المقيدين|المحظورين)$"
            ),
            moderation_lists_command,
        ),
    ))

    handlers.append((
        660,
        -18,
        CallbackQueryHandler(
            clear_list_callback,
            pattern=r"^moderation:clear:",
        ),
    ))

    # ==================================================
    # الإنذارات
    # ==================================================

    handlers.append((
        700,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^انذار(?:\s+.+)?$"),
            warning_command,
        ),
    ))

    handlers.append((
        710,
        -18,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^مسح انذاراته$"),
            clear_warnings_command,
        ),
    ))

    # ==================================================
    # التكرار
    # ==================================================

    handlers.append((
        800,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تفعيل التكرار$"),
            enable_repetition,
        ),
    ))

    handlers.append((
        810,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تعطيل التكرار$"),
            disable_repetition,
        ),
    ))

    handlers.append((
        820,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^ضع تكرار \d+$"),
            set_repetition_start,
        ),
    ))

    handlers.append((
        830,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^ضع كتم تكرار \S+$"),
            set_mute_duration,
        ),
    ))

    handlers.append((
        840,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^ضع تقييد تكرار \S+$"),
            set_restrict_duration,
        ),
    ))

    handlers.append((
        850,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^(?:ضع|تغيير) رتبة التكرار "
                r"(عضو|مميز|ادمن|ادمن اساسي|نائب المالك|المالك|Dev)$"
            ),
            set_repetition_rank,
        ),
    ))

    handlers.append((
        860,
        -17,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^مسح انذاراته$"),
            clear_user_repetition_warnings,
        ),
    ))

    handlers.append((
        870,
        -17,
        CallbackQueryHandler(
            repetition_action_callback,
            pattern=r"^repetition_punish:(?:mute|restrict):\d+$",
        ),
    ))

    # --------------------------------------------------
    # استقبال مدة التكرار
    # --------------------------------------------------

    handlers.append((
        880,
        -16,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            receive_repetition_duration,
        ),
    ))

    # --------------------------------------------------
    # مراقبة التكرار
    # --------------------------------------------------

    handlers.append((
        890,
        -15,
        MessageHandler(
            filters.ChatType.GROUPS,
            repetition_message_handler,
        ),
    ))

    return handlers
