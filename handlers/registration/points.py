
from telegram.ext import MessageHandler, filters

from handlers.points import (
    add_points_command,
    remove_points_command,
    sell_points,
    my_points,
    top_points,
)


def build_points_handlers(app):
    return [
        (112, -1, MessageHandler(
            filters.Regex(r"^اضف \d+$"),
            add_points_command
        )),

        (113, -1, MessageHandler(
            filters.Regex(r"^خصم \d+$"),
            remove_points_command
        )),

        (114, -1, MessageHandler(
            filters.Regex(r"^بيع نقاطي \d+$"),
            sell_points
        )),

        (115, 0, MessageHandler(
            filters.Regex(r"^نقاطي$"),
            my_points
        )),

        (116, 0, MessageHandler(
            filters.Regex(r"^توب$"),
            top_points
        )),
    ]
