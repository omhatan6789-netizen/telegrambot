import random
import secrets
import string
import time
from datetime import datetime, timezone, timedelta
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import TelegramError
from telegram.helpers import mention_html
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import connect
from handlers.points import (
    get_points,
    add_points,
)


# ==================================================
# الوظائف
# ==================================================

JOBS = [
    ("دكتور", "👨🏻‍⚕️", 3900),
    ("مهندس", "👷🏻", 3000),
    ("معلّم", "👨🏻‍🏫", 2500),
    ("محامي", "⚖️", 3200),
    ("مبرمج", "👨🏻‍💻", 1800),
    ("طيار", "👨🏻‍✈️", 4000),
    ("شرطي", "👮🏻", 1700),
    ("صيدلي", "💊", 1000),
    ("مصمم", "🎨", 1400),
    ("طباخ", "👨🏻‍🍳", 1200),
    ("ممرض", "🧑🏻‍⚕️", 1500),
    ("سائق", "🚗", 900),
    ("رقاصة", "💃🏻", 600),
    ("كاشير", "🧑🏻‍💼", 800),
    ("كهربائي", "⚡️", 1400),
    ("محاسب", "🧑🏻‍💼", 2000),
    ("قاضي", "👨🏻‍⚖️", 3800),
    ("مزارع", "👨🏻‍🌾", 1100),
]


STORE_ITEMS = {
    "برج": {
        "emoji": "🏰",
        "base": 3500,
        "min": 2188,
        "max": 4375,
    },
    "جزيرة": {
        "emoji": "🏝",
        "base": 4200,
        "min": 2625,
        "max": 5250,
    },
    "بيت": {
        "emoji": "🏠",
        "base": 2400,
        "min": 1500,
        "max": 3000,
    },
    "طيارة": {
        "emoji": "🛩",
        "base": 1800,
        "min": 1125,
        "max": 2250,
    },
    "سيارة": {
        "emoji": "🏎",
        "base": 1200,
        "min": 750,
        "max": 1500,
    },
    "سفينة": {
        "emoji": "🛳",
        "base": 1600,
        "min": 1000,
        "max": 2000,
    },
    "قطار": {
        "emoji": "🚂",
        "base": 2800,
        "min": 1750,
        "max": 3500,
    },
    "قصر": {
        "emoji": "🏯",
        "base": 3900,
        "min": 2438,
        "max": 4875,
    },
    "ماسة": {
        "emoji": "💎",
        "base": 1000,
        "min": 625,
        "max": 1250,
    },
    "طعمية": {
        "emoji": "🧆",
        "base": 20,
        "min": 13,
        "max": 25,
    },
    "شاورما": {
        "emoji": "🌯",
        "base": 35,
        "min": 22,
        "max": 44,
    },
    "مزرعة": {
        "emoji": "🌾",
        "base": 800,
        "min": 500,
        "max": 1000,
    },
}


STORE_ORDER = [
    "برج",
    "جزيرة",
    "بيت",
    "طيارة",
    "سيارة",
    "سفينة",
    "قطار",
    "قصر",
    "ماسة",
    "طعمية",
    "شاورما",
    "مزرعة",
]


BANKS = {
    "ahli": {
        "name": "الاهلي",
        "card": "فيزا",
    },
    "inma": {
        "name": "الانماء",
        "card": "مدى",
    },
    "rajhi": {
        "name": "الراجحي",
        "card": "ماستر كارد",
    },
}


# ==================================================
# جلسات التحويل
# ==================================================

_transfer_sessions = {}

_transfer_message_sessions = {}


# ==================================================
# المنطقة الزمنية للسعودية
# ==================================================

SAUDI_TZ = timezone(timedelta(hours=3))


SCRATCH_CODE_COUNT = 10
SCRATCH_MIN_AMOUNT = 70
SCRATCH_MAX_AMOUNT = 10_000_000
SCRATCH_COOLDOWN_SECONDS = 2 * 60 * 60


# ==================================================
# إرسال خاص إذا كان المستخدم قد بدأ البوت
# ==================================================

async def _send_private_if_possible(
    bot,
    user_id,
    text,
    reply_markup=None,
    parse_mode=None,
):
    try:
        return await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramError:
        return None


# ==================================================
# رابط الرسالة
# ==================================================

def _message_link(message):
    if not message or not message.chat:
        return None

    chat = message.chat

    if chat.username:
        return (
            f"https://t.me/"
            f"{chat.username}/"
            f"{message.message_id}"
        )

    chat_id = str(chat.id)

    if chat_id.startswith("-100"):
        return (
            f"https://t.me/c/"
            f"{chat_id[4:]}/"
            f"{message.message_id}"
        )

    return None


# ==================================================
# التحقق من تفعيل الألعاب
# ==================================================

def _games_enabled():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT status
            FROM games_settings
            WHERE id = 1
            """
        )

        row = cur.fetchone()

        if not row:
            return True

        return row[0] != "off"

    finally:
        cur.close()
        conn.close()


# ==================================================
# أدوات الوقت
# ==================================================

def _now():
    return int(time.time())


def _format_arabic_duration(seconds):
    seconds = max(0, int(seconds))

    minutes, secs = divmod(seconds, 60)

    if minutes <= 0:
        if secs == 1:
            return "ثانية"
        return f"{secs} ثانية"

    if secs == 0:
        if minutes == 1:
            return "دقيقة"

        if minutes == 2:
            return "دقيقتين"

        if 3 <= minutes <= 10:
            names = {
                3: "ثلاث",
                4: "أربع",
                5: "خمس",
                6: "ست",
                7: "سبع",
                8: "ثمان",
                9: "تسع",
                10: "عشر",
            }

            return f"{names.get(minutes, minutes)} دقائق"

        return f"{minutes} دقيقة"

    if minutes == 1:
        minute_text = "دقيقة"

    elif minutes == 2:
        minute_text = "دقيقتين"

    elif 3 <= minutes <= 10:
        names = {
            3: "ثلاث",
            4: "أربع",
            5: "خمس",
            6: "ست",
            7: "سبع",
            8: "ثمان",
            9: "تسع",
            10: "عشر",
        }

        minute_text = f"{names.get(minutes, minutes)} دقائق"

    else:
        minute_text = f"{minutes} دقيقة"

    if secs == 1:
        second_text = "ثانية"
    else:
        second_text = f"{secs} ثانية"

    return f"{minute_text} و {second_text}"


def _format_clock(seconds):
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)

    return f"{minutes:02d}:{secs:02d}"


# ==================================================
# قاعدة بيانات التسليات
# ==================================================

def _get_cooldowns(user_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                salary_until,
                tip_until,
                robber_until,
                victim_rob_until,
                investment_until,
                luck_until
            FROM tasliyat_cooldowns
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        if not row:
            cur.execute(
                """
                INSERT INTO tasliyat_cooldowns
                (
                    user_id,
                    salary_until,
                    tip_until,
                    robber_until,
                    victim_rob_until,
                    investment_until,
                    luck_until
                )
                VALUES (?, 0, 0, 0, 0, 0, 0)
                """,
                (user_id,)
            )

            conn.commit()

            return {
                "salary_until": 0,
                "tip_until": 0,
                "robber_until": 0,
                "victim_rob_until": 0,
                "investment_until": 0,
                "luck_until": 0,
            }

        return {
            "salary_until": row[0] or 0,
            "tip_until": row[1] or 0,
            "robber_until": row[2] or 0,
            "victim_rob_until": row[3] or 0,
            "investment_until": row[4] or 0,
            "luck_until": row[5] or 0,
        }

    finally:
        cur.close()
        conn.close()


def _set_cooldown(user_id, column, until_time):
    allowed = {
        "salary_until",
        "tip_until",
        "robber_until",
        "victim_rob_until",
        "investment_until",
        "luck_until",
    }

    if column not in allowed:
        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO tasliyat_cooldowns (user_id)
            VALUES (?)
            ON CONFLICT (user_id)
            DO NOTHING
            """,
            (user_id,)
        )

        cur.execute(
            f"""
            UPDATE tasliyat_cooldowns
            SET {column} = ?
            WHERE user_id = ?
            """,
            (until_time, user_id)
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


# ==================================================
# البنك
# ==================================================

def _get_bank(user_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                user_id,
                account_number,
                bank,
                card_type,
                robbery_balance
            FROM bank_accounts
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        if not row:
            return None

        return {
            "user_id": row[0],
            "account_number": row[1],
            "bank": row[2],
            "card_type": row[3],
            "robbery_balance": row[4] or 0,
        }

    finally:
        cur.close()
        conn.close()


def _get_bank_by_number(account_number):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                user_id,
                account_number,
                bank,
                card_type,
                robbery_balance
            FROM bank_accounts
            WHERE account_number = ?
            """,
            (account_number,)
        )

        row = cur.fetchone()

        if not row:
            return None

        return {
            "user_id": row[0],
            "account_number": row[1],
            "bank": row[2],
            "card_type": row[3],
            "robbery_balance": row[4] or 0,
        }

    finally:
        cur.close()
        conn.close()


def _generate_account_number():
    while True:
        number = str(
            secrets.randbelow(90000000000000000)
            + 10000000000000000
        )

        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT 1
                FROM bank_accounts
                WHERE account_number = ?
                """,
                (number,)
            )

            if not cur.fetchone():
                return number

        finally:
            cur.close()
            conn.close()


def _bank_name(key):
    return BANKS[key]["name"]


# ==================================================
# منشن حقيقي
# ==================================================

def _mention(user):
    return mention_html(
        user.id,
        user.full_name
    )


def _get_user_mention(user_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT first_name, username
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        if row:
            name = row[0] or row[1] or str(user_id)
        else:
            name = str(user_id)

        return mention_html(
            user_id,
            name
        )

    finally:
        cur.close()
        conn.close()


# ==================================================
# التأكد من وجود حساب
# ==================================================

async def _require_bank(update):
    user = update.effective_user

    if not user:
        return None

    bank = _get_bank(user.id)

    if not bank:
        if update.message:
            await update.message.reply_text(
                "• ماعندك حساب بنكي ."
            )

        return None

    return bank



# ==================================================
# أكواد الكشط
# ==================================================

def _scratch_hour_data():
    now = datetime.now(SAUDI_TZ)

    hour_start = now.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    next_hour = hour_start + timedelta(hours=1)

    hour_key = int(
        hour_start.timestamp() // 3600
    )

    return (
        hour_key,
        hour_start,
        next_hour
    )


def _generate_scratch_code():
    chars = string.ascii_uppercase + string.digits

    return "".join(
        secrets.choice(chars)
        for _ in range(12)
    )


def _ensure_scratch_codes():
    (
        hour_key,
        hour_start,
        next_hour
    ) = _scratch_hour_data()

    conn = connect()

    try:
        cur = conn.cursor()

        # منع إنشاء مجموعة ثانية لنفس الساعة
        cur.execute(
            """
            SELECT pg_advisory_xact_lock(?)
            """,
            (918273645,)
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM scratch_codes
            WHERE hour_key = ?
            """,
            (hour_key,)
        )

        count = int(cur.fetchone()[0] or 0)

        while count < SCRATCH_CODE_COUNT:

            code = _generate_scratch_code()

            amount = random.randint(
                SCRATCH_MIN_AMOUNT,
                SCRATCH_MAX_AMOUNT
            )

            cur.execute(
                """
                INSERT INTO scratch_codes
                (
                    code,
                    amount,
                    hour_key,
                    expires_at
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?
                )
                ON CONFLICT (code)
                DO NOTHING
                """,
                (
                    code,
                    amount,
                    hour_key,
                    next_hour
                )
            )

            if cur.rowcount:
                count += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        try:
            cur.close()
        except Exception:
            pass

        conn.close()


def _format_scratch_remaining(seconds):
    seconds = max(0, int(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


async def show_scratch_codes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    if (update.message.text or "").strip() != "عرض الاكواد":
        return

    if not _games_enabled():
        return

    _ensure_scratch_codes()

    now = datetime.now(timezone.utc)

    conn = connect()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT code
            FROM scratch_codes
            WHERE used = FALSE
              AND expires_at > ?
            ORDER BY id ASC
            """,
            (now,)
        )

        rows = cur.fetchall()

    finally:
        try:
            cur.close()
        except Exception:
            pass

        conn.close()

    text = (
        "• اكواد الكشط الموجوده بالبوت :\n\n"
    )

    for index, row in enumerate(rows, 1):
        text += (
            f"{index}- <code>{row[0]}</code>\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


async def scratch_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    text = (
        update.message.text or ""
    ).strip()

    if not text.startswith("كشط "):
        return

    parts = text.split(maxsplit=1)

    if len(parts) != 2:
        return

    code = parts[1].strip().upper()

    if not code:
        return

    if not _games_enabled():
        return

    # إنشاء أكواد الساعة الحالية إن لم تكن موجودة
    _ensure_scratch_codes()

    now = datetime.now(timezone.utc)

    conn = connect()

    try:
        cur = conn.cursor()

        # ==================================================
        # التحقق من وقت الكشط للمستخدم
        # ==================================================

        cur.execute(
            """
            SELECT last_scratched_at
            FROM scratch_limits
            WHERE user_id = ?
            """,
            (user.id,)
        )

        limit_row = cur.fetchone()

        if limit_row:
            last_scratched_at = limit_row[0]

            next_allowed = (
                last_scratched_at
                + timedelta(
                    seconds=SCRATCH_COOLDOWN_SECONDS
                )
            )

            if now < next_allowed:
                remaining = int(
                    (
                        next_allowed - now
                    ).total_seconds()
                )

                await update.message.reply_text(
                    "• مب حلى هو مايمديك تكشط اي كود الحين .\n"
                    f"• الوقت المتبقي: "
                    f"{_format_scratch_remaining(remaining)} ⏰"
                )

                return

        # ==================================================
        # استهلاك الكود بشكل ذري
        # ==================================================

        cur.execute(
            """
            UPDATE scratch_codes
            SET
                used = TRUE,
                used_by = ?
            WHERE code = ?
              AND used = FALSE
              AND expires_at > ?
            RETURNING amount
            """,
            (
                user.id,
                code,
                now
            )
        )

        result = cur.fetchone()

        if not result:
            conn.rollback()

            await update.message.reply_text(
                "• للأسف الكود انتهى وقته او فيه شخص استعمله قبلك"
            )

            return

        amount = int(result[0])

        # ==================================================
        # تسجيل وقت آخر كشط
        # ==================================================

        cur.execute(
            """
            INSERT INTO scratch_limits
            (
                user_id,
                last_scratched_at
            )
            VALUES
            (
                ?,
                ?
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
                last_scratched_at =
                    EXCLUDED.last_scratched_at
            """,
            (
                user.id,
                now
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        try:
            cur.close()
        except Exception:
            pass

        conn.close()

    # إضافة النقاط باستخدام نظام النقاط الموجود عندك
    add_points(
        user.id,
        amount
    )

    await update.message.reply_text(
        "• تم كشط الكود بنجاح 🎉 .\n\n"
        f"- الاسم ↤︎ {_mention(user)}\n"
        f"- المبلغ ↤︎ {amount} نقطة 💸 \n"
        "-",
        parse_mode="HTML"
    )
# ==================================================
# إنشاء حساب بنكي
# ==================================================

async def create_bank_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    user = update.effective_user

    if not user or not update.message:
        return

    target_user = user

    if update.message.reply_to_message:

        if user.id != 8453977662:
            return

        replied_user = update.message.reply_to_message.from_user

        if not replied_user:
            return

        target_user = replied_user

    if _get_bank(target_user.id):
        await update.message.reply_text(
            "• عنده حساب بنكي 😅\n\n"
            "• لعرض معلومات حسابه اكتب\n"
            "↤︎ حسابي"
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "الاهلي",
                callback_data=f"tasliyat:bank:ahli:{target_user.id}"
            )
        ],
        [
            InlineKeyboardButton(
                "الانماء",
                callback_data=f"tasliyat:bank:inma:{target_user.id}"
            )
        ],
        [
            InlineKeyboardButton(
                "الراجحي",
                callback_data=f"tasliyat:bank:rajhi:{target_user.id}"
            )
        ],
    ]

    await update.message.reply_text(
        "• عشان تسوي حساب لازم تختار نوع البطاقة\n"
        "↤︎ الاهلي\n"
        "↤︎ الانماء\n"
        "↤︎ الراجحي\n",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================================================
# Callback البنك
# ==================================================

async def bank_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    if not _games_enabled():
        return

    parts = query.data.split(":")

    if len(parts) != 4:
        return

    bank_key = parts[2]

    try:
        target_user_id = int(parts[3])
    except ValueError:
        return

    if bank_key not in BANKS:
        return

    creator = query.from_user

    if creator.id != target_user_id and creator.id != 8453977662:
        return

    if _get_bank(target_user_id):
        await query.edit_message_text(
            "• عنده حساب بنكي 😅\n\n"
            "• لعرض معلومات حسابه اكتب\n"
            "↤︎ حسابي"
        )

        return

    bank_info = BANKS[bank_key]
    account_number = _generate_account_number()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO bank_accounts
            (
                user_id,
                account_number,
                bank,
                card_type,
                robbery_balance
            )
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                target_user_id,
                account_number,
                bank_info["name"],
                bank_info["card"],
            )
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()

    points = get_points(target_user_id)

    await query.edit_message_text(
        f"• سويت لك حساب في البنك ( {bank_info['name']} 💳 )\n"
        f"• رقم حسابك ↢ ( <code>{account_number}</code> )\n"
        f"• نوع البطاقة ↢ ( {bank_info['card']} )\n"
        f"• نقاطك ↢ ( {points} 💵 )",
        parse_mode="HTML"
    )


# ==================================================
# حسابي
# ==================================================

async def my_bank_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    user = update.effective_user

    if not user or not update.message:
        return

    bank = _get_bank(user.id)

    if not bank:
        await update.message.reply_text(
            "• ماعندك حساب بنكي ارسل ↢ ( انشاء حساب بنكي )"
        )

        return

    points = get_points(user.id)

    await update.message.reply_text(
        f"• الاسم ↢ {_mention(user)}\n"
        f"• الحساب ↢ <code>{bank['account_number']}</code>\n"
        f"• بنك ↢ ( {bank['bank']} )\n"
        f"• نوع ↢ ( {bank['card_type']} )\n"
        f"• الرصيد ↢ ( {points} نقطة 💵 )\n"
        f"• الزرف ↢ ( {bank['robbery_balance']} نقطة 🥷🏻 )",
        parse_mode="HTML"
    )


# ==================================================
# مسح حسابي
# ==================================================

async def delete_bank_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    user = update.effective_user

    if not user or not update.message:
        return

    bank = _get_bank(user.id)

    if not bank:
        await update.message.reply_text(
            "• ماعندك حساب بنكي ."
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            DELETE FROM bank_accounts
            WHERE user_id = ?
            """,
            (user.id,)
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()

    await update.message.reply_text(
        "• تم مسح حسابك البنكي ."
    )


# ==================================================
# الراتب
# ==================================================

async def salary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    user = update.effective_user

    if not user or not update.message:
        return

    if not await _require_bank(update):
        return

    cooldowns = _get_cooldowns(user.id)
    now = _now()

    if cooldowns["salary_until"] > now:
        remaining = cooldowns["salary_until"] - now

        await update.message.reply_text(
            f"• راتبك بينزل بعد {_format_arabic_duration(remaining)} ."
        )

        return

    job, emoji, amount = random.choice(JOBS)

    new_points = add_points(
        user.id,
        amount
    )

    _set_cooldown(
        user.id,
        "salary_until",
        now + 600
    )

    await update.message.reply_text(
        f"اشعار ايداع {_mention(user)}\n"
        f"المبلغ: {amount} نقطة\n"
        f"وظيفتك: {job} {emoji}\n"
        f"نوع العملية: اضافة راتب\n"
        f"رصيدك الحين: {new_points} نقطة 💸",
        parse_mode="HTML"
    )


# ==================================================
# بخشيش
# ==================================================

async def tip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    user = update.effective_user

    if not user or not update.message:
        return

    if not await _require_bank(update):
        return

    cooldowns = _get_cooldowns(user.id)
    now = _now()

    if cooldowns["tip_until"] > now:
        remaining = cooldowns["tip_until"] - now

        await update.message.reply_text(
            "• بس بس مب حلاو هو !!\n"
            f"↤︎ تعال بعد {_format_arabic_duration(remaining)}"
        )

        return

    amount = random.randint(100, 2000)

    new_points = add_points(
        user.id,
        amount
    )

    _set_cooldown(
        user.id,
        "tip_until",
        now + 600
    )

    await update.message.reply_text(
        f"• شفقت عليك وعطيتك {amount} نقطة 💵"
    )


# ==================================================
# أسعار المتجر
# ==================================================

def _get_store_price(item_key):
    current_hour = _now() // 3600

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT price, hour_key
            FROM store_prices
            WHERE item_key = ?
            """,
            (item_key,)
        )

        row = cur.fetchone()

        if row and row[1] == current_hour:
            return row[0]

        item = STORE_ITEMS[item_key]

        price = random.randint(
            item["min"],
            item["max"]
        )

        cur.execute(
            """
            INSERT INTO store_prices
            (
                item_key,
                price,
                hour_key
            )
            VALUES (?, ?, ?)
            ON CONFLICT (item_key)
            DO UPDATE SET
                price = EXCLUDED.price,
                hour_key = EXCLUDED.hour_key
            """,
            (
                item_key,
                price,
                current_hour
            )
        )

        conn.commit()

        return price

    finally:
        cur.close()
        conn.close()


# ==================================================
# المتجر
# ==================================================

async def store(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    if not update.message:
        return

    lines = [
        "اهلًا يالتاجر هذا المتجر وأسعار المنتجات:"
    ]

    for index, item_key in enumerate(STORE_ORDER, 1):
        item = STORE_ITEMS[item_key]
        price = _get_store_price(item_key)

        lines.append(
            f"{index} - {item_key} {item['emoji']} ↤︎ {price} ."
        )

    lines.extend([
        "",
        "• يمديك تشتري كذا، مثال : شراء 2 سيارة",
        "• يمديك تشتري كذا، مثال : بيع 2 سيارة",
        "• يمديك تهدي شخص كذا، مثال : اهداء 2 سيارة بالرد",
    ])

    await update.message.reply_text(
        "\n".join(lines)
    )


# ==================================================
# الممتلكات
# ==================================================

def _get_possessions(user_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT item_key, quantity
            FROM possessions
            WHERE user_id = ?
              AND quantity > 0
            ORDER BY item_key
            """,
            (user_id,)
        )

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


def _get_possession_quantity(user_id, item_key):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT quantity
            FROM possessions
            WHERE user_id = ?
              AND item_key = ?
            """,
            (user_id, item_key)
        )

        row = cur.fetchone()

        return row[0] if row else 0

    finally:
        cur.close()
        conn.close()


def _change_possession(user_id, item_key, amount):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT quantity
            FROM possessions
            WHERE user_id = ?
              AND item_key = ?
            """,
            (user_id, item_key)
        )

        row = cur.fetchone()

        current = row[0] if row else 0
        new_quantity = current + amount

        if new_quantity <= 0:
            cur.execute(
                """
                DELETE FROM possessions
                WHERE user_id = ?
                  AND item_key = ?
                """,
                (user_id, item_key)
            )

        elif row:
            cur.execute(
                """
                UPDATE possessions
                SET quantity = ?
                WHERE user_id = ?
                  AND item_key = ?
                """,
                (
                    new_quantity,
                    user_id,
                    item_key
                )
            )

        else:
            cur.execute(
                """
                INSERT INTO possessions
                (
                    user_id,
                    item_key,
                    quantity
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    item_key,
                    new_quantity
                )
            )

        conn.commit()

    finally:
        cur.close()
        conn.close()


async def my_possessions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    user = update.effective_user

    if not user or not update.message:
        return

    possessions = _get_possessions(user.id)

    if not possessions:
        await update.message.reply_text(
            "• مسكين ماعندك شي رح اشتغل على نفسك بعدين تعال 😂 ."
        )

        return

    lines = [
        "• أهلاً بك في قائمة ممتلكاتك ."
    ]

    for item_key, quantity in possessions:
        lines.append(
            f"( {item_key} ↤︎ {quantity} )"
        )

    await update.message.reply_text(
        "\n".join(lines)
    )


async def other_possessions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message

    if not message or not message.reply_to_message:
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    possessions = _get_possessions(target.id)

    if not possessions:
        await message.reply_text(
            "• الرجال ماعنده شي رح تبرع له ."
        )

        return

    lines = [
        "• قائمة ممتلكاته ."
    ]

    for item_key, quantity in possessions:
        lines.append(
            f"( {item_key} ↤︎ {quantity} )"
        )

    await message.reply_text(
        "\n".join(lines)
    )


# ==================================================
# شراء / بيع
# ==================================================

async def buy_sell(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message

    if not message or not message.text:
        return

    parts = message.text.strip().split(maxsplit=2)

    if len(parts) != 3:
        return

    action = parts[0]

    try:
        quantity = int(parts[1])
    except ValueError:
        return

    item_key = parts[2].strip()

    if action not in ("شراء", "بيع"):
        return

    if quantity <= 0:
        return

    if item_key not in STORE_ITEMS:
        return

    user = update.effective_user

    if not user:
        return

    price = _get_store_price(item_key)
    total = price * quantity

    if action == "شراء":
        points = get_points(user.id)

        if points < total:
            await message.reply_text(
                "• نقاطك ماتكفي يا مطفر\n"
                "–"
            )

            return

        add_points(
            user.id,
            -total
        )

        _change_possession(
            user.id,
            item_key,
            quantity
        )

        await message.reply_text(
            f"• مبروك تم شراء : {item_key}\n"
            f"• العدد : {quantity}\n"
            f"• بقيمة : {total} نقطة 💸\n"
            f"• أصبحت نقاطك : ({get_points(user.id)} 💸)\n"
            f"• اكتب ( ممتلكاتي ) لمعرفة مملكاتك"
        )

        return

    current_quantity = _get_possession_quantity(
        user.id,
        item_key
    )

    if current_quantity <= 0:
        await message.reply_text(
            f"• انت اصلًا ماعندك {item_key} تاكد من ممتلكاتك ."
        )

        return

    if current_quantity < quantity:
        await message.reply_text(
            f"• عندك {current_quantity} من ({item_key}) فقط ."
        )

        return

    sell_value = (total * 50) // 100

    _change_possession(
        user.id,
        item_key,
        -quantity
    )

    add_points(
        user.id,
        sell_value
    )

    await message.reply_text(
        f"• مبروك تم بيع : {item_key}\n"
        f"• العدد : {quantity}\n"
        f"• بقيمة : {sell_value} نقطة بعد خصم 50% 💸\n"
        f"• نقاطك صارت : ({get_points(user.id)} 💸)\n"
        f"• اكتب ( ممتلكاتي ) لمعرفة مملكاتك"
    )


# ==================================================
# الإهداء
# ==================================================

async def gift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message

    if not message or not message.text:
        return

    if not message.reply_to_message:
        return

    parts = message.text.strip().split(maxsplit=2)

    if len(parts) != 3:
        return

    if parts[0] != "اهداء":
        return

    try:
        quantity = int(parts[1])
    except ValueError:
        return

    item_key = parts[2].strip()

    if quantity <= 0 or item_key not in STORE_ITEMS:
        return

    sender = update.effective_user
    recipient = message.reply_to_message.from_user

    if not sender or not recipient:
        return

    if sender.id == recipient.id:
        return

    owned = _get_possession_quantity(
        sender.id,
        item_key
    )

    if owned <= 0:
        await message.reply_text(
            f"• انت اصلًا ماعندك {item_key} تاكد من ممتلكاتك ."
        )

        return

    if owned < quantity:
        await message.reply_text(
            f"• عندك {owned} من ({item_key}) فقط ."
        )

        return

    _change_possession(
        sender.id,
        item_key,
        -quantity
    )

    _change_possession(
        recipient.id,
        item_key,
        quantity
    )

    await message.reply_text(
        "• عملية اهداء :\n"
        f"• الاهداء من : {_mention(sender)}\n"
        f"• نوع الهدية : ({item_key})\n"
        f"• العدد : {quantity}\n"
        f"المستلم : {_mention(recipient)}",
        parse_mode="HTML"
    )

    # ==================================================
    # إشعار خاص للمستلم
    # ==================================================

    await _send_private_if_possible(
        context.bot,
        recipient.id,
        "• وصلتك هدية :\n\n"
        f"• الاهداء من : {_mention(sender)}\n"
        f"• نوع الهدية : ({item_key})\n"
        f"• العدد : {quantity}\n"
        "-",
        parse_mode="HTML"
    )


# ==================================================
# الزرف
# ==================================================

async def rob(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message

    if not message or not message.reply_to_message:
        return

    robber = update.effective_user
    victim = message.reply_to_message.from_user

    if not robber or not victim:
        return

    if robber.id == victim.id:
        await message.reply_text(
            "• شوفو الغبي يبي يزرف نفسه 😭😭 ."
        )

        return

    robber_bank = _get_bank(robber.id)

    if not robber_bank:
        await message.reply_text(
            "• ماعندك حساب بنكي:"
        )

        return

    victim_bank = _get_bank(victim.id)

    if not victim_bank:
        await message.reply_text(
            "• ماعنده حساب بنكي"
        )

        return

    now = _now()
    cooldowns = _get_cooldowns(robber.id)

    if cooldowns["robber_until"] > now:
        remaining = cooldowns["robber_until"] - now

        await message.reply_text(
            "• انحش يارجال الشرطة تدور عليك 🚓\n"
            f"• يمديك تزرف بعد {_format_clock(remaining)} دقيقة ⏰"
        )

        return

    victim_cooldowns = _get_cooldowns(victim.id)

    if victim_cooldowns["victim_rob_until"] > now:
        remaining = victim_cooldowns["victim_rob_until"] - now

        await message.reply_text(
            "• المسكين توه مزروف ارحمه شوي 😭 .\n"
            f"• يمديك تزرفه بعد {_format_clock(remaining)} دقيقة"
        )

        return

    victim_points = get_points(victim.id)

    if victim_points <= 0:
        return

    amount = random.randint(20, 1000)
    amount = min(amount, victim_points)

    add_points(
        victim.id,
        -amount
    )

    add_points(
        robber.id,
        amount
    )

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE bank_accounts
            SET robbery_balance = robbery_balance + ?
            WHERE user_id = ?
            """,
            (
                amount,
                robber.id
            )
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()

    _set_cooldown(
        robber.id,
        "robber_until",
        now + 300
    )

    _set_cooldown(
        victim.id,
        "victim_rob_until",
        now + 600
    )

    # ==================================================
    # رسالة الزرف في القروب
    # ==================================================

    sent_message = await message.reply_text(
        f"• خذ يالحرامي زرفته {amount} نقطة 💵 ."
    )

    # ==================================================
    # إشعار خاص للمزروف
    # ==================================================

    now_dt = datetime.fromtimestamp(
        now,
        SAUDI_TZ
    )

    date_text = now_dt.strftime("%Y/%m/%d")
    time_text = now_dt.strftime("%I:%M%p").lstrip("0")

    group_name = message.chat.title or "القروب"

    message_url = _message_link(sent_message)

    keyboard = None

    if message_url:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    group_name,
                    url=message_url
                )
            ]
        ])

    await _send_private_if_possible(
        context.bot,
        victim.id,
        "• الحق على حلالك هههههه\n"
        f"• الشخص ذا : {_mention(robber)}\n"
        f"• زرفك {amount} نقطة 💸\n"
        f"• التاريخ ↤︎ {date_text}\n"
        f"• الساعة ↤︎ {time_text}\n"
        "-",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==================================================
# التحويل
# ==================================================

async def transfer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message
    user = update.effective_user

    if not message or not message.text or not user:
        return

    bank = await _require_bank(update)

    if not bank:
        return

    parts = message.text.strip().split()

    if len(parts) != 2:
        return

    try:
        amount = int(parts[1])
    except ValueError:
        return

    if amount < 200:
        return

    points = get_points(user.id)

    if points < amount:
        await message.reply_text(
            "• نقاطك ماتكفي يا مطفر\n"
            "–"
        )

        return

    _transfer_sessions[user.id] = {
        "amount": amount,
        "created_at": _now(),
    }

    await message.reply_text(
        "• الحين ارسل رقم الحساب البنكي الي تبي تحول له\n"
        "–"
    )


async def transfer_account_number(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message
    user = update.effective_user

    if not message or not message.text or not user:
        return

    session = _transfer_sessions.get(user.id)

    if not session:
        return

    account_number = message.text.strip()

    if not account_number.isdigit():
        return

    if len(account_number) != 17:
        return

    amount = session["amount"]

    recipient_bank = _get_bank_by_number(
        account_number
    )

    if not recipient_bank:
        _transfer_sessions.pop(
            user.id,
            None
        )

        await message.reply_text(
            "• مالقيت رقم الحساب البنكي\n"
            "–"
        )

        return

    sender_bank = _get_bank(user.id)

    if not sender_bank:
        _transfer_sessions.pop(
            user.id,
            None
        )

        return

    if recipient_bank["user_id"] == user.id:
        _transfer_sessions.pop(
            user.id,
            None
        )

        return

    if get_points(user.id) < amount:
        _transfer_sessions.pop(
            user.id,
            None
        )

        await message.reply_text(
            "• نقاطك ماتكفي يا مطفر\n"
            "–"
        )

        return

    if sender_bank["bank"] == recipient_bank["bank"]:
        fee_percent = 5
        received = (amount * 95) // 100

        fee_text = (
            f"خصمت 5% لبنك {recipient_bank['bank']}"
        )

    else:
        fee_percent = 10
        received = (amount * 90) // 100

        fee_text = "خصمت 10% من بنك لبنك"

    add_points(
        user.id,
        -amount
    )

    add_points(
        recipient_bank["user_id"],
        received
    )

    _transfer_sessions.pop(
        user.id,
        None
    )

    recipient_mention = _get_user_mention(
        recipient_bank["user_id"]
    )

    await message.reply_text(
        f"حوالة صادرة من البنك ↢ ( {sender_bank['bank']} )\n"
        f"المرسل : {_mention(user)}\n"
        f"الحساب رقم : <code>{sender_bank['account_number']}</code>\n"
        f"نوع البطاقة : {sender_bank['card_type']}\n"
        f"المستلم : {recipient_mention}\n"
        f"الحساب رقم : <code>{recipient_bank['account_number']}</code>\n"
        f"البنك : {recipient_bank['bank']}\n"
        f"نوع البطاقة : {recipient_bank['card_type']}\n"
        f"{fee_text}\n"
        f"المبلغ : {received} نقطة 💵",
        parse_mode="HTML"
    )

    # ==================================================
    # إشعار خاص للمستلم
    # ==================================================

    recipient_id = recipient_bank["user_id"]

    _transfer_message_sessions.pop(
        recipient_id,
        None
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "ارسل رسالة للمُرسل 🌹",
                callback_data=(
                    f"tasliyat:transfer_message:"
                    f"{recipient_id}:{user.id}"
                )
            )
        ]
    ])

    await _send_private_if_possible(
        context.bot,
        recipient_id,
        f"حوالة واردة من البنك ↢ ( {sender_bank['bank']} )\n\n"
        f"المرسل : {_mention(user)}\n"
        f"الحساب رقم : <code>{sender_bank['account_number']}</code>\n"
        f"نوع البطاقة : {sender_bank['card_type']}\n"
        f"المبلغ : {received} نقطة 💸",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==================================================
# Callback إرسال رسالة للمرسل
# ==================================================

async def transfer_message_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query or not query.data:
        return

    parts = query.data.split(":")

    if len(parts) != 4:
        return

    try:
        recipient_id = int(parts[2])
        sender_id = int(parts[3])
    except ValueError:
        return

    if query.from_user.id != recipient_id:
        await query.answer()
        return

    _transfer_message_sessions[recipient_id] = sender_id

    await query.answer()

    if query.message:
        await query.message.reply_text(
            "• تمام، ارسل الرسالة وبرسلها للمرسل فورًا ."
        )


# ==================================================
# استقبال رسالة المستلم وإرسالها للمرسل
# يدعم النص والصوت والفيديو والصورة والملصق و GIF وغيرها
# ==================================================

async def transfer_message_receiver(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    if chat.type != "private":
        return

    sender_id = _transfer_message_sessions.pop(
        user.id,
        None
    )

    if not sender_id:
        return

    # ==================================================
    # الرسائل النصية
    # ==================================================

    if message.text:
        notification = (
            "• جتك رسالة من الشخص الي حولت له🌹\n"
            f"• اسمه: {_mention(user)}\n"
            f"• الرسالة: {escape(message.text)}"
        )

        try:
            await context.bot.send_message(
                chat_id=sender_id,
                text=notification,
                parse_mode="HTML"
            )

        except TelegramError:
            raise ApplicationHandlerStop()

        await message.reply_text(
            "• تم ارسال الرسالة بنجاح ✅ ."
        )

        raise ApplicationHandlerStop()

    # ==================================================
    # الرسائل التي تحتوي على Caption
    # ==================================================

    caption = message.caption

    notification = (
        "• جتك رسالة من الشخص الي حولت له🌹\n"
        f"• اسمه: {_mention(user)}\n"
        "• الرسالة:"
    )

    if caption:
        notification += f" {escape(caption)}"

    # ==================================================
    # إرسال الإشعار + نسخ الرسالة نفسها
    # ==================================================

    try:
        await context.bot.send_message(
            chat_id=sender_id,
            text=notification,
            parse_mode="HTML"
        )

        await context.bot.copy_message(
            chat_id=sender_id,
            from_chat_id=user.id,
            message_id=message.message_id,
        )

    except TelegramError:
        raise ApplicationHandlerStop()

    await message.reply_text(
        "• تم ارسال الرسالة بنجاح ✅ ."
    )

    raise ApplicationHandlerStop()


# ==================================================
# الاستثمار
# ==================================================

def _investment_percent():
    roll = random.randint(1, 100)

    if roll <= 50:
        return random.randint(1, 20)

    if roll <= 90:
        return random.randint(21, 30)

    return random.randint(31, 40)


async def invest(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message
    user = update.effective_user

    if not message or not message.text or not user:
        return

    if not await _require_bank(update):
        return

    cooldowns = _get_cooldowns(user.id)
    now = _now()

    if cooldowns["investment_until"] > now:
        remaining = cooldowns["investment_until"] - now

        await message.reply_text(
            "• مايمديك تستثمر الحين\n"
            f"• تعال بعد {_format_arabic_duration(remaining)}"
        )

        return

    parts = message.text.strip().split()

    if len(parts) == 1:
        amount = get_points(user.id)

    elif len(parts) == 2:
        if parts[1] == "نقاطي":
            amount = get_points(user.id)
        else:
            try:
                amount = int(parts[1])
            except ValueError:
                return

    else:
        return

    if amount <= 0:
        return

    if get_points(user.id) < amount:
        await message.reply_text(
            "• نقاطك ماتكفي يا مطفر\n"
            "–"
        )

        return

    _set_cooldown(
        user.id,
        "investment_until",
        now + 1200
    )

    success = random.randint(1, 100) <= 90

    if not success:
        current = get_points(user.id)

        await message.reply_text(
            "• استثمار فاشل\n"
            "• نسبة الربح ↢ 0%\n"
            "• مبلغ الربح ↢ ( 0 )\n"
            f"• نقاطك صارت ↢ ( {current} )"
        )

        return

    percent = _investment_percent()

    profit = (amount * percent) // 100

    new_points = add_points(
        user.id,
        profit
    )

    await message.reply_text(
        "• استثمار ناجح\n"
        f"• نسبة الربح ↢ {percent}%\n"
        f"• مبلغ الربح ↢ ( {profit} )\n"
        f"• نقاطك صارت ↢ ( {new_points} )"
    )


# ==================================================
# الحظ
# ==================================================

async def luck(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not _games_enabled():
        return

    message = update.message
    user = update.effective_user

    if not message or not message.text or not user:
        return

    if not await _require_bank(update):
        return

    cooldowns = _get_cooldowns(user.id)
    now = _now()

    if cooldowns["luck_until"] > now:
        remaining = cooldowns["luck_until"] - now

        await message.reply_text(
            "• مايمديك تسوي حظ الحين\n"
            f"• تعال بعد {_format_arabic_duration(remaining)}"
        )

        return

    parts = message.text.strip().split()

    if len(parts) == 1:
        amount = get_points(user.id)

    elif len(parts) == 2:
        if parts[1] == "نقاطي":
            amount = get_points(user.id)
        else:
            try:
                amount = int(parts[1])
            except ValueError:
                return

    else:
        return

    if amount <= 0:
        return

    before = get_points(user.id)

    if before < amount:
        await message.reply_text(
            "• نقاطك ماتكفي يا مطفر\n"
            "–"
        )

        return

    _set_cooldown(
        user.id,
        "luck_until",
        now + 1200
    )

    won = random.randint(1, 2) == 1

    if won:
        after = add_points(
            user.id,
            amount
        )

        await message.reply_text(
            "• مبروك فزت بالحظ\n"
            f"• نقاطك قبل ↢ ( {before} نقطة 💵 )\n"
            f"• نقاطك الحين ↢ ( {after} نقطة 💵 )"
        )

        return

    add_points(
        user.id,
        -amount
    )

    after = get_points(user.id)

    await message.reply_text(
        "• للاسف خسرت بالحظ \n"
        f"• نقاطك قبل ↢ ( {before} نقطة 💵 )\n"
        f"• نقاطك  الحين ↢ ( {after} نقطة 💵 )\n"
        "-"
    )
