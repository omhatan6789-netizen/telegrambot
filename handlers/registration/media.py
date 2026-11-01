
from telegram.ext import (
    MessageHandler,
    ConversationHandler,
    filters,
)

from handlers.button_colors import (
    change_button_color_start,
    change_button_color_handler,
)

from handlers.photo_tools import (
    get_photo_id,
    show_photo_start,
    show_photo_by_id,
    WAIT_PHOTO_ID,
)


def build_media_handlers(app):
    show_photo_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^اعرض الصورة$"),
                show_photo_start
            )
        ],
        states={
            WAIT_PHOTO_ID: [
                MessageHandler(
                    filters.ChatType.PRIVATE
                    & filters.TEXT
                    & ~filters.COMMAND,
                    show_photo_by_id
                )
            ]
        },
        fallbacks=[],
        allow_reentry=True
    )

    handlers = [
        # بدء تعديل لون الزر
        (
            38,
            -20,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^تعديل لون$"),
                change_button_color_start
            )
        ),

        # استقبال اختيار اللون
        (
            62,
            -14,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                change_button_color_handler
            )
        ),

        # عرض الصورة بالـ ID في الخاص
        (
            161,
            -21,
            show_photo_conv
        ),

        # استخراج ID الصورة في الخاص
        (
            162,
            -20,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.PHOTO,
                get_photo_id
            )
        ),
    ]

    return handlers
