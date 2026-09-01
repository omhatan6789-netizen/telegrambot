import re

from telegram import InlineKeyboardButton

from database import connect


# ==================================================
# الألوان
# ==================================================

COLOR_STYLES = {
    "احمر": "danger",
    "ازرق": "primary",
    "اخضر": "success",
    "شفاف": None
}


# ==================================================
# تسجيل الزر
# ==================================================

def register_button(button_text):
    if not button_text:
        return

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO button_colors
        (
            button_text,
            color
        )
        VALUES
        (
            ?,
            'شفاف'
        )
        """,
        (button_text,)
    )

    conn.commit()
    conn.close()


# ==================================================
# جلب لون الزر
# ==================================================

def get_button_color(button_text):
    if not button_text:
        return "شفاف"

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT color
        FROM button_colors
        WHERE button_text=?
        """,
        (button_text,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return "شفاف"

    return result[0]


# ==================================================
# تغيير لون الزر
# ==================================================

def set_button_color(button_text, color):
    if color not in COLOR_STYLES:
        return False

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT button_text
        FROM button_colors
        WHERE button_text=?
        """,
        (button_text,)
    )

    exists = cur.fetchone()

    if not exists:
        conn.close()
        return False

    cur.execute(
        """
        UPDATE button_colors
        SET color=?
        WHERE button_text=?
        """,
        (
            color,
            button_text
        )
    )

    conn.commit()
    conn.close()

    return True


# ==================================================
# إصلاح ألوان الأزرار تلقائيًا
# ==================================================

def patch_inline_keyboard_buttons():

    original_init = InlineKeyboardButton.__init__

    def new_init(self, *args, **kwargs):

        text = kwargs.get("text")

        if text is None and args:
            text = args[0]

        if text:
            register_button(text)

            saved_color = get_button_color(text)

            if saved_color in COLOR_STYLES:
                style = COLOR_STYLES[saved_color]

                if style is not None:
                    kwargs["style"] = style
                else:
                    kwargs.pop("style", None)

        original_init(
            self,
            *args,
            **kwargs
        )

    InlineKeyboardButton.__init__ = new_init


# ==================================================
# تسجيل الأزرار الموجودة مسبقًا في panel_buttons
# ==================================================

def register_existing_panel_buttons():

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT button_text
        FROM panel_buttons
        WHERE button_text IS NOT NULL
        """
    )

    buttons = cur.fetchall()

    conn.close()

    for row in buttons:
        register_button(row[0])