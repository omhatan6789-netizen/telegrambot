from telegram import InlineKeyboardButton
from database import connect


COLOR_STYLES = {
    "احمر": "danger",
    "ازرق": "primary",
    "اخضر": "success",
    "شفاف": None
}


_known_buttons = set()
_color_cache = {}
_cache_loaded = False
_patch_done = False


def normalize_button_name(text):
    if not text:
        return ""

    return " ".join(str(text).strip().split())


def _load_cache():
    global _cache_loaded

    if _cache_loaded:
        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT button_text, color
            FROM button_colors
            WHERE button_text IS NOT NULL
        """)

        rows = cur.fetchall()

        for button_text, color in rows:

            button_text = normalize_button_name(button_text)

            if not button_text:
                continue

            _known_buttons.add(button_text)

            if color in COLOR_STYLES:
                _color_cache[button_text] = color
            else:
                _color_cache[button_text] = "شفاف"

        _cache_loaded = True

    finally:
        cur.close()
        conn.close()


def register_button(button_text):
    button_text = normalize_button_name(button_text)

    if not button_text:
        return

    _load_cache()

    if button_text in _known_buttons:
        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO button_colors
            (
                button_text,
                color
            )
            VALUES
            (
                %s,
                'شفاف'
            )
            ON CONFLICT (button_text) DO NOTHING
            """,
            (button_text,)
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()

    _known_buttons.add(button_text)
    _color_cache[button_text] = "شفاف"


def register_button_memory(button_text):
    button_text = normalize_button_name(button_text)

    if not button_text:
        return

    _load_cache()

    if button_text not in _known_buttons:
        _known_buttons.add(button_text)

    if button_text not in _color_cache:
        _color_cache[button_text] = "شفاف"


def get_button_color(button_text):
    button_text = normalize_button_name(button_text)

    if not button_text:
        return "شفاف"

    _load_cache()

    return _color_cache.get(button_text, "شفاف")


def button_exists(button_text):
    button_text = normalize_button_name(button_text)

    if not button_text:
        return False

    _load_cache()

    return button_text in _known_buttons


def set_button_color(button_text, color):
    button_text = normalize_button_name(button_text)

    if not button_text:
        return False

    if color not in COLOR_STYLES:
        return False

    _load_cache()

    if button_text not in _known_buttons:
        return False

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE button_colors
            SET color = %s
            WHERE button_text = %s
            """,
            (color, button_text)
        )

        if cur.rowcount == 0:
            conn.rollback()
            return False

        conn.commit()

        _color_cache[button_text] = color

        return True

    except Exception:
        conn.rollback()
        return False

    finally:
        cur.close()
        conn.close()


def patch_inline_keyboard_buttons():

    global _patch_done

    if _patch_done:
        return

    _patch_done = True

    original_init = InlineKeyboardButton.__init__

    def new_init(self, *args, **kwargs):

        text = kwargs.get("text")

        if text is None and args:
            text = args[0]

        if text:

            # تسجيل في الذاكرة فقط
            # ممنوع الاتصال بالداتابيس هنا
            register_button_memory(text)

            saved_color = _color_cache.get(
                normalize_button_name(text),
                "شفاف"
            )

            style = COLOR_STYLES.get(saved_color)

            if style is not None:
                kwargs["style"] = style
            else:
                kwargs.pop("style", None)

        original_init(self, *args, **kwargs)

    InlineKeyboardButton.__init__ = new_init


def register_existing_panel_buttons():

    _load_cache()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT button_text
            FROM panel_buttons
            WHERE button_text IS NOT NULL
        """)

        buttons = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    for row in buttons:

        button_text = row[0]

        if button_text:
            register_button_memory(button_text)