import io
import random
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes
from telegram.ext.filters import BaseFilter

from handlers.points import add_points


# =========================================================
# الإعدادات
# =========================================================

TABLE_IMAGE_FILE_ID = (
    "AgACAgQAAxkBAAIEnmqsj8k7vw-CvrqUzRnmD7fPz9fi"
    "AAKzEmsbF1lhUe-eLSZyl-zLAQADAgADeQADPQQ"
)

WIN_POINTS = 150
TARGET_SCORE = 11

TURN_TIMEOUT = 15

MAX_PLAYERS = 4
MIN_PLAYERS = 2


# =========================================================
# الحالة
# =========================================================

@dataclass
class TTPlayer:
    user_id: int
    name: str
    team: str
    stamina: int = 100


@dataclass
class TableTennisGame:
    chat_id: int
    host_id: int

    players: list[TTPlayer] = field(default_factory=list)

    red_score: int = 0
    blue_score: int = 0

    started: bool = False
    finished: bool = False

    turn_index: int = 0

    # اللاعب المهاجم
    attacker_id: Optional[int] = None

    # اللاعب المدافع
    defender_id: Optional[int] = None

    attacker_action: Optional[str] = None
    attacker_direction: Optional[str] = None

    defender_action: Optional[str] = None

    last_action: str = "بداية المباراة 🏓"

    image_message_id: Optional[int] = None

    turn_task: Optional[asyncio.Task] = None

    # مكان الكرة:
    # center / red / blue
    ball_side: str = "center"


TABLE_TENNIS_GAMES: dict[int, TableTennisGame] = {}


# =========================================================
# فلتر اللعبة
# =========================================================

class TableTennisActiveFilter(BaseFilter):

    def __init__(self, patterns=None, name="TableTennisActiveFilter"):
        super().__init__(name=name)
        self.patterns = patterns or []

    def filter(self, message):

        if not message:
            return False

        chat_id = message.chat_id

        if chat_id not in TABLE_TENNIS_GAMES:
            return False

        if not self.patterns:
            return True

        text = message.text or ""

        import re

        return any(
            re.search(pattern, text)
            for pattern in self.patterns
        )


# =========================================================
# أدوات
# =========================================================

def get_game(chat_id: int):
    return TABLE_TENNIS_GAMES.get(chat_id)


def get_player(game: TableTennisGame, user_id: int):
    for player in game.players:
        if player.user_id == user_id:
            return player
    return None


def get_team_players(game: TableTennisGame, team: str):
    return [
        p for p in game.players
        if p.team == team
    ]


def team_name(game: TableTennisGame, team: str):
    players = get_team_players(game, team)

    if not players:
        return "فارغ"

    return " + ".join(
        p.name[:14]
        for p in players
    )


def current_attacker(game: TableTennisGame):
    if not game.players:
        return None

    if game.turn_index >= len(game.players):
        game.turn_index = 0

    return game.players[game.turn_index]


def current_defender(game: TableTennisGame):
    attacker = current_attacker(game)

    if not attacker:
        return None

    enemy_team = "blue" if attacker.team == "red" else "red"

    enemy = get_team_players(game, enemy_team)

    if not enemy:
        return None

    # في 1 ضد 1
    if len(enemy) == 1:
        return enemy[0]

    # في 2 ضد 2:
    # نختار لاعبًا عشوائيًا من الفريق الخصم
    return enemy[game.turn_index % len(enemy)]


def next_turn(game: TableTennisGame):

    if not game.players:
        return

    game.turn_index += 1

    if game.turn_index >= len(game.players):
        game.turn_index = 0


def get_font(size: int):

    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
    ]

    for path in possible_fonts:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    return ImageFont.load_default()


def fit_text(draw, text, max_width, font_size=22):

    size = font_size

    while size >= 10:

        font = get_font(size)

        box = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        width = box[2] - box[0]

        if width <= max_width:
            return font

        size -= 1

    return get_font(10)


# =========================================================
# تحميل قالب الصورة من Telegram
# =========================================================

async def get_template_image(context: ContextTypes.DEFAULT_TYPE):

    file = await context.bot.get_file(
        TABLE_IMAGE_FILE_ID
    )

    data = await file.download_as_bytearray()

    image = Image.open(
        io.BytesIO(data)
    ).convert("RGBA")

    return image


# =========================================================
# كتابة النص على الصورة
# =========================================================

def draw_centered_text(
    draw,
    text,
    center_x,
    y,
    font,
    fill="white",
):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    width = box[2] - box[0]

    draw.text(
        (
            center_x - width / 2,
            y
        ),
        text,
        font=font,
        fill=fill,
    )


# =========================================================
# إنشاء صورة المباراة
# =========================================================

def build_match_image(
    image: Image.Image,
    game: TableTennisGame,
):

    image = image.copy()

    draw = ImageDraw.Draw(image)

    # الصورة الأصلية = 1000 × 563
    # -----------------------------------------------------
    # أماكن مربعات الفريقين بالأعلى
    # -----------------------------------------------------

    red_icon_font = get_font(27)
    blue_icon_font = get_font(27)

    draw_centered_text(
        draw,
        "⚡️",
        301,
        18,
        red_icon_font,
        "white",
    )

    draw_centered_text(
        draw,
        "🎸",
        699,
        18,
        blue_icon_font,
        "white",
    )

    # -----------------------------------------------------
    # النتيجة
    # -----------------------------------------------------

    score_font = get_font(31)

    draw_centered_text(
        draw,
        str(game.red_score),
        454,
        20,
        score_font,
        "white",
    )

    draw_centered_text(
        draw,
        str(game.blue_score),
        545,
        20,
        score_font,
        "white",
    )

    # -----------------------------------------------------
    # أسماء الفريق الأحمر
    # -----------------------------------------------------

    red_players = get_team_players(
        game,
        "red"
    )

    blue_players = get_team_players(
        game,
        "blue"
    )

    # المستطيل السفلي الأحمر
    # تقريبًا x=20 إلى 318
    # -----------------------------------------------------

    red_y = 443

    for index, player in enumerate(red_players[:2]):

        text = (
            f"{player.name[:15]}  ⚡ {player.stamina}"
        )

        font = fit_text(
            draw,
            text,
            270,
            19
        )

        draw.text(
            (
                40,
                red_y + index * 23
            ),
            text,
            font=font,
            fill="white",
        )

    # -----------------------------------------------------
    # أسماء الفريق الأزرق
    # -----------------------------------------------------

    blue_y = 443

    for index, player in enumerate(blue_players[:2]):

        text = (
            f"{player.name[:15]}  ⚡ {player.stamina}"
        )

        font = fit_text(
            draw,
            text,
            270,
            19
        )

        # نبدأ من اليمين تقريبًا
        box = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        text_width = box[2] - box[0]

        draw.text(
            (
                960 - text_width,
                blue_y + index * 23
            ),
            text,
            font=font,
            fill="white",
        )

    # -----------------------------------------------------
    # معلومات وسط الملعب
    # -----------------------------------------------------

    if game.started and not game.finished:

        attacker = current_attacker(game)

        if attacker:

            turn_text = (
                f"دور: {attacker.name[:15]}"
            )

            font = fit_text(
                draw,
                turn_text,
                300,
                18
            )

            draw_centered_text(
                draw,
                turn_text,
                500,
                365,
                font,
                "white",
            )

    # -----------------------------------------------------
    # آخر حركة
    # -----------------------------------------------------

    action_font = fit_text(
        draw,
        game.last_action,
        500,
        20
    )

    draw_centered_text(
        draw,
        game.last_action,
        500,
        392,
        action_font,
        "white",
    )

    # -----------------------------------------------------
    # مؤشر الكرة
    # -----------------------------------------------------

    ball_positions = {
        "red": (245, 265),
        "center": (500, 265),
        "blue": (755, 265),
    }

    bx, by = ball_positions.get(
        game.ball_side,
        (500, 265)
    )

    # دائرة الكرة
    draw.ellipse(
        (
            bx - 8,
            by - 8,
            bx + 8,
            by + 8,
        ),
        fill="white",
        outline="black",
        width=2,
    )

    # -----------------------------------------------------
    # إذا المباراة لم تبدأ
    # -----------------------------------------------------

    if not game.started:

        draw_centered_text(
            draw,
            "بانتظار بدء المباراة 🏓",
            500,
            365,
            get_font(22),
            "white",
        )

    return image


# =========================================================
# تحويل الصورة إلى Bytes
# =========================================================

def image_to_bytes(image):

    output = io.BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output


# =========================================================
# إرسال / تحديث صورة المباراة
# =========================================================

async def send_or_update_image(
    update,
    context,
    game,
):

    template = await get_template_image(
        context
    )

    final_image = build_match_image(
        template,
        game
    )

    buffer = image_to_bytes(
        final_image
    )

    # أول مرة
    if not game.image_message_id:

        message = await context.bot.send_photo(
            chat_id=game.chat_id,
            photo=InputFile(
                buffer,
                filename="table_tennis.png"
            ),
        )

        game.image_message_id = message.message_id

        return message

    # تحديث الصورة
    try:

        await context.bot.edit_message_media(
            chat_id=game.chat_id,
            message_id=game.image_message_id,
            media=InputMediaPhoto(
                media=InputFile(
                    buffer,
                    filename="table_tennis.png"
                )
            )
        )

    except Exception:

        # إذا فشل التعديل نرسل صورة جديدة
        message = await context.bot.send_photo(
            chat_id=game.chat_id,
            photo=InputFile(
                buffer,
                filename="table_tennis.png"
            ),
        )

        game.image_message_id = message.message_id

    return None


# =========================================================
# أزرار المهاجم
# =========================================================

def attacker_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "↖️",
                callback_data="tt:dir:ul"
            ),
            InlineKeyboardButton(
                "⬆️",
                callback_data="tt:dir:u"
            ),
            InlineKeyboardButton(
                "↗️",
                callback_data="tt:dir:ur"
            ),
        ],

        [
            InlineKeyboardButton(
                "⬅️",
                callback_data="tt:dir:l"
            ),
            InlineKeyboardButton(
                "🎯",
                callback_data="tt:dir:c"
            ),
            InlineKeyboardButton(
                "➡️",
                callback_data="tt:dir:r"
            ),
        ],

        [
            InlineKeyboardButton(
                "↙️",
                callback_data="tt:dir:dl"
            ),
            InlineKeyboardButton(
                "⬇️",
                callback_data="tt:dir:d"
            ),
            InlineKeyboardButton(
                "↘️",
                callback_data="tt:dir:dr"
            ),
        ],

        [
            InlineKeyboardButton(
                "⚡️ سريعة",
                callback_data="tt:shot:fast"
            ),
            InlineKeyboardButton(
                "🎯 دقيقة",
                callback_data="tt:shot:precise"
            ),
        ],

        [
            InlineKeyboardButton(
                "🌀 Spin",
                callback_data="tt:shot:spin"
            ),
            InlineKeyboardButton(
                "💥 Smash",
                callback_data="tt:shot:smash"
            ),
        ],

    ])


# =========================================================
# أزرار المدافع
# =========================================================

def defender_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🛡️ صد",
                callback_data="tt:def:block"
            ),
            InlineKeyboardButton(
                "⚡️ صد سريع",
                callback_data="tt:def:quick"
            ),
        ],

        [
            InlineKeyboardButton(
                "↩️ إرجاع",
                callback_data="tt:def:return"
            ),
            InlineKeyboardButton(
                "🎯 رد دقيق",
                callback_data="tt:def:precise"
            ),
        ],

    ])


# =========================================================
# إرسال دور المهاجم
# =========================================================

async def send_attacker_controls(
    context,
    game,
):

    attacker = current_attacker(game)

    defender = current_defender(game)

    if not attacker or not defender:
        return

    game.attacker_id = attacker.user_id
    game.defender_id = defender.user_id

    game.attacker_action = None
    game.attacker_direction = None
    game.defender_action = None

    try:

        await context.bot.send_message(
            chat_id=attacker.user_id,
            text=(
                "🏓 <b>دورك في طاولة التنس!</b>\n\n"
                "اختر اتجاه الضربة أولًا، "
                "ثم اختر نوع الضربة.\n\n"
                "⏱ لديك 15 ثانية."
            ),
            reply_markup=attacker_keyboard(),
            parse_mode="HTML",
        )

    except Exception:

        await context.bot.send_message(
            chat_id=game.chat_id,
            text=(
                f"⚠️ <a href='tg://user?id={attacker.user_id}'>"
                f"{attacker.name}</a>\n"
                "افتح خاص البوت أولًا حتى تقدر تلعب."
            ),
            parse_mode="HTML",
        )


# =========================================================
# إرسال دور المدافع
# =========================================================

async def send_defender_controls(
    context,
    game,
):

    defender = get_player(
        game,
        game.defender_id
    )

    attacker = get_player(
        game,
        game.attacker_id
    )

    if not defender or not attacker:
        return

    try:

        await context.bot.send_message(
            chat_id=defender.user_id,
            text=(
                "🏓 <b>دورك للدفاع!</b>\n\n"
                f"🏓 اللاعب المهاجم: {attacker.name}\n"
                f"🎯 الاتجاه: {game.attacker_direction}\n"
                f"💥 الضربة: {game.attacker_action}\n\n"
                "اختر طريقة الصد:"
            ),
            reply_markup=defender_keyboard(),
            parse_mode="HTML",
        )

    except Exception:

        await context.bot.send_message(
            chat_id=game.chat_id,
            text=(
                f"⚠️ <a href='tg://user?id={defender.user_id}'>"
                f"{defender.name}</a>\n"
                "افتح خاص البوت أولًا حتى تقدر تلعب."
            ),
            parse_mode="HTML",
        )


# =========================================================
# قوة الضربات
# =========================================================

SHOT_POWER = {
    "fast": 20,
    "precise": 15,
    "spin": 25,
    "smash": 40,
}

SHOT_COST = {
    "fast": 12,
    "precise": 8,
    "spin": 10,
    "smash": 30,
}


DEFENSE_POWER = {
    "block": 25,
    "quick": 18,
    "return": 30,
    "precise": 35,
}


SHOT_NAMES = {
    "fast": "⚡️ سريعة",
    "precise": "🎯 دقيقة",
    "spin": "🌀 Spin",
    "smash": "💥 Smash",
}

DEFENSE_NAMES = {
    "block": "🛡️ صد",
    "quick": "⚡️ صد سريع",
    "return": "↩️ إرجاع",
    "precise": "🎯 رد دقيق",
}


# =========================================================
# حساب التبادل
# =========================================================

async def resolve_exchange(
    context,
    game,
):

    attacker = get_player(
        game,
        game.attacker_id
    )

    defender = get_player(
        game,
        game.defender_id
    )

    if not attacker or not defender:
        return

    shot = game.attacker_action
    defense = game.defender_action

    if not shot or not defense:
        return

    # -----------------------------------------------------
    # الطاقة
    # -----------------------------------------------------

    attacker.stamina = max(
        0,
        attacker.stamina - SHOT_COST.get(
            shot,
            10
        )
    )

    # -----------------------------------------------------
    # حساب قوة الهجوم
    # -----------------------------------------------------

    attack_power = SHOT_POWER.get(
        shot,
        15
    )

    # طاقة اللاعب تؤثر
    attack_power += (
        attacker.stamina // 20
    )

    # -----------------------------------------------------
    # قوة الدفاع
    # -----------------------------------------------------

    defense_power = DEFENSE_POWER.get(
        defense,
        20
    )

    defense_power += (
        defender.stamina // 25
    )

    # -----------------------------------------------------
    # بعض الضربات أقوى ضد أنواع معينة
    # -----------------------------------------------------

    bonus = 0

    if shot == "smash" and defense == "block":
        bonus = 12

    elif shot == "spin" and defense == "quick":
        bonus = 8

    elif shot == "precise" and defense == "return":
        bonus = 7

    elif shot == "fast" and defense == "precise":
        bonus = -5

    attack_power += bonus

    # عشوائية بسيطة حتى لا تصبح النتيجة مضمونة
    attack_power += random.randint(
        -8,
        8
    )

    defense_power += random.randint(
        -8,
        8
    )

    # -----------------------------------------------------
    # النتيجة
    # -----------------------------------------------------

    attacker_wins_exchange = (
        attack_power > defense_power
    )

    if attacker_wins_exchange:

        # نقطة للمهاجم
        if attacker.team == "red":
            game.red_score += 1
            game.ball_side = "red"
        else:
            game.blue_score += 1
            game.ball_side = "blue"

        game.last_action = (
            f"{SHOT_NAMES[shot]} — نقطة لـ"
            f"{'الأحمر 🔴' if attacker.team == 'red' else 'الأزرق 🔵'}"
        )

        # استرجاع بسيط للطاقة بعد النقطة
        defender.stamina = min(
            100,
            defender.stamina + 5
        )

    else:

        # الدفاع نجح
        defender.stamina = min(
            100,
            defender.stamina + 8
        )

        game.ball_side = defender.team

        game.last_action = (
            f"{DEFENSE_NAMES[defense]} — صد ناجح 🛡️"
        )

    # -----------------------------------------------------
    # تحديث الصورة
    # -----------------------------------------------------

    await send_or_update_image(
        None,
        context,
        game
    )

    # -----------------------------------------------------
    # هل انتهت المباراة؟
    # -----------------------------------------------------

    if check_winner(game):

        await finish_game(
            context,
            game
        )

        return

    # -----------------------------------------------------
    # الدور التالي
    # -----------------------------------------------------

    next_turn(game)

    await asyncio.sleep(1)

    await send_or_update_image(
        None,
        context,
        game
    )

    await send_attacker_controls(
        context,
        game
    )

    # مؤقت الدور
    if game.turn_task:

        try:
            game.turn_task.cancel()
        except Exception:
            pass

    game.turn_task = asyncio.create_task(
        attacker_timeout(
            context,
            game.chat_id
        )
    )


# =========================================================
# مؤقت الدور
# =========================================================

async def attacker_timeout(
    context,
    chat_id,
):

    await asyncio.sleep(
        TURN_TIMEOUT
    )

    game = TABLE_TENNIS_GAMES.get(
        chat_id
    )

    if not game:
        return

    if game.finished:
        return

    attacker = current_attacker(game)

    if not attacker:
        return

    game.last_action = (
        f"⏱ {attacker.name} تأخر عن الدور"
    )

    # خصم بسيط من الطاقة بدل نقطة مجانية
    attacker.stamina = max(
        0,
        attacker.stamina - 10
    )

    next_turn(game)

    await send_or_update_image(
        None,
        context,
        game
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏱ انتهى وقت <b>{attacker.name}</b>\n"
            "تم الانتقال للاعب التالي."
        ),
        parse_mode="HTML",
    )

    await send_attacker_controls(
        context,
        game
    )

    game.turn_task = asyncio.create_task(
        attacker_timeout(
            context,
            chat_id
        )
    )


# =========================================================
# التحقق من الفائز
# =========================================================

def check_winner(game):

    red = game.red_score
    blue = game.blue_score

    if red >= TARGET_SCORE and red - blue >= 2:
        return "red"

    if blue >= TARGET_SCORE and blue - red >= 2:
        return "blue"

    return None


# =========================================================
# إعطاء النقاط
# =========================================================

async def give_winner_points(
    user_id,
    chat_id,
):

    try:

        result = add_points(
            user_id,
            WIN_POINTS,
            chat_id
        )

        if asyncio.iscoroutine(result):
            await result

        return True

    except TypeError:

        try:

            result = add_points(
                chat_id,
                user_id,
                WIN_POINTS
            )

            if asyncio.iscoroutine(result):
                await result

            return True

        except Exception:
            pass

    except Exception:
        pass

    return False


# =========================================================
# إنهاء المباراة
# =========================================================

async def finish_game(
    context,
    game,
):

    if game.finished:
        return

    game.finished = True

    if game.turn_task:

        try:
            game.turn_task.cancel()
        except Exception:
            pass

        game.turn_task = None

    winner = check_winner(game)

    if not winner:
        return

    winner_players = get_team_players(
        game,
        winner
    )

    winner_text = (
        "🔴 الفريق الأحمر"
        if winner == "red"
        else
        "🔵 الفريق الأزرق"
    )

    for player in winner_players:

        await give_winner_points(
            player.user_id,
            game.chat_id
        )

    game.last_action = (
        f"🏆 {winner_text} فاز!"
    )

    await send_or_update_image(
        None,
        context,
        game
    )

    names = "\n".join(
        f"• {p.name}"
        for p in winner_players
    )

    await context.bot.send_message(
        chat_id=game.chat_id,
        text=(
            "🏓 <b>انتهت مباراة طاولة التنس!</b>\n\n"
            f"🏆 الفائز: <b>{winner_text}</b>\n"
            f"🔴 {game.red_score} — {game.blue_score} 🔵\n\n"
            f"🎉 الفائزون:\n{names}\n\n"
            f"💰 كل لاعب فائز حصل على <b>+{WIN_POINTS}</b> نقطة."
        ),
        parse_mode="HTML",
    )

    TABLE_TENNIS_GAMES.pop(
        game.chat_id,
        None
    )


# =========================================================
# إنشاء اللعبة
# =========================================================

async def start_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if chat.id in TABLE_TENNIS_GAMES:

        await message.reply_text(
            "🏓 توجد طاولة تنس مفتوحة بالفعل."
        )

        return

    game = TableTennisGame(
        chat_id=chat.id,
        host_id=user.id
    )

    TABLE_TENNIS_GAMES[
        chat.id
    ] = game

    await message.reply_text(
        "🏓 <b>تم إنشاء طاولة تنس!</b>\n\n"
        "👥 اللاعبين: <b>2 أو 4</b>\n"
        "🔴 لاعبان = 1 ضد 1\n"
        "🔵 أربعة لاعبين = 2 ضد 2\n\n"
        "اكتب <b>دخول</b> للانضمام.\n"
        "عند اكتمال اللاعبين اكتب <b>.ابدا</b>\n\n"
        "💰 الفائز يحصل على <b>+150 نقطة</b>\n"
        "❌ لا يوجد XP.",
        parse_mode="HTML",
    )

    await send_or_update_image(
        update,
        context,
        game
    )


# =========================================================
# دخول
# =========================================================

async def join_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    user = update.effective_user
    game = get_game(
        update.effective_chat.id
    )

    if not game:
        return

    if game.started:

        await message.reply_text(
            "🏓 المباراة بدأت بالفعل."
        )

        return

    if len(game.players) >= MAX_PLAYERS:

        await message.reply_text(
            "❌ الطاولة مكتملة."
        )

        return

    if get_player(game, user.id):

        await message.reply_text(
            "أنت داخل الطاولة بالفعل."
        )

        return

    # أول لاعبين أحمر
    if len(game.players) < 2:
        team = "red"
    else:
        team = "blue"

    player = TTPlayer(
        user_id=user.id,
        name=(
            user.first_name
            or user.username
            or str(user.id)
        ),
        team=team
    )

    game.players.append(
        player
    )

    team_text = (
        "🔴 الأحمر"
        if team == "red"
        else
        "🔵 الأزرق"
    )

    await message.reply_text(
        f"🏓 دخل <b>{player.name}</b>\n"
        f"الفريق: {team_text}\n\n"
        f"👥 العدد: {len(game.players)}/4",
        parse_mode="HTML",
    )

    await send_or_update_image(
        update,
        context,
        game
    )


# =========================================================
# خروج
# =========================================================

async def leave_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    user = update.effective_user

    game = get_game(
        update.effective_chat.id
    )

    if not game:
        return

    if game.started:

        await message.reply_text(
            "❌ لا يمكنك الخروج بعد بدء المباراة."
        )

        return

    player = get_player(
        game,
        user.id
    )

    if not player:

        await message.reply_text(
            "أنت لست داخل الطاولة."
        )

        return

    game.players.remove(
        player
    )

    # إعادة توزيع الفرق
    for index, p in enumerate(game.players):

        p.team = (
            "red"
            if index < 2
            else "blue"
        )

    await message.reply_text(
        f"🚪 خرج <b>{player.name}</b> من الطاولة.",
        parse_mode="HTML",
    )

    await send_or_update_image(
        update,
        context,
        game
    )


# =========================================================
# بدء المباراة
# =========================================================

async def begin_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    user = update.effective_user

    game = get_game(
        update.effective_chat.id
    )

    if not game:
        return

    if user.id != game.host_id:

        await message.reply_text(
            "❌ فقط صاحب الطاولة يقدر يبدأ المباراة."
        )

        return

    if game.started:

        await message.reply_text(
            "🏓 المباراة بدأت بالفعل."
        )

        return

    if len(game.players) not in (2, 4):

        await message.reply_text(
            "❌ لازم يكون عدد اللاعبين <b>2 أو 4</b>.",
            parse_mode="HTML",
        )

        return

    # في حال 2 لاعبين
    if len(game.players) == 2:

        game.players[0].team = "red"
        game.players[1].team = "blue"

    # في حال 4 لاعبين
    else:

        game.players[0].team = "red"
        game.players[1].team = "red"
        game.players[2].team = "blue"
        game.players[3].team = "blue"

    game.started = True
    game.finished = False
    game.turn_index = 0

    first = current_attacker(game)

    game.last_action = (
        f"🏓 المباراة بدأت!\n"
        f"الدور على {first.name}"
    )

    await message.reply_text(
        "🏓 <b>بدأت مباراة طاولة التنس!</b>\n\n"
        "🔴 الأحمر ضد 🔵 الأزرق\n"
        "🎯 المباراة إلى 11 نقطة\n"
        "📌 لازم يكون الفوز بفارق نقطتين\n\n"
        "💡 الضربات والصدود تؤثر على نتيجة كل تبادل.",
        parse_mode="HTML",
    )

    await send_or_update_image(
        update,
        context,
        game
    )

    await send_attacker_controls(
        context,
        game
    )

    game.turn_task = asyncio.create_task(
        attacker_timeout(
            context,
            game.chat_id
        )
    )


# =========================================================
# إنهاء يدوي
# =========================================================

async def end_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    user = update.effective_user

    game = get_game(
        update.effective_chat.id
    )

    if not game:
        return

    if user.id != game.host_id:

        await message.reply_text(
            "❌ فقط صاحب الطاولة يقدر ينهيها."
        )

        return

    if game.turn_task:

        try:
            game.turn_task.cancel()
        except Exception:
            pass

    TABLE_TENNIS_GAMES.pop(
        game.chat_id,
        None
    )

    await message.reply_text(
        "🏓 تم إنهاء طاولة التنس."
    )


# =========================================================
# Callback
# =========================================================

async def table_tennis_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    # نبحث عن اللعبة التي يكون اللاعب مشاركًا فيها
    game = None

    for candidate in TABLE_TENNIS_GAMES.values():

        if get_player(
            candidate,
            user.id
        ):

            game = candidate
            break

    if not game:
        await query.answer(
            "❌ أنت لست داخل مباراة.",
            show_alert=True
        )
        return

    if game.finished:
        await query.answer(
            "انتهت المباراة.",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # اختيار الاتجاه
    # -----------------------------------------------------

    if query.data.startswith(
        "tt:dir:"
    ):

        attacker = current_attacker(
            game
        )

        if not attacker:
            return

        if attacker.user_id != user.id:

            await query.answer(
                "❌ ليس دورك.",
                show_alert=True
            )

            return

        direction_map = {
            "ul": "↖️",
            "u": "⬆️",
            "ur": "↗️",
            "l": "⬅️",
            "c": "🎯",
            "r": "➡️",
            "dl": "↙️",
            "d": "⬇️",
            "dr": "↘️",
        }

        direction = query.data.split(
            ":"
        )[-1]

        game.attacker_direction = (
            direction_map.get(
                direction,
                "🎯"
            )
        )

        await query.edit_message_text(
            (
                "🏓 اختر نوع الضربة:\n\n"
                f"🎯 الاتجاه: "
                f"<b>{game.attacker_direction}</b>"
            ),
            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "⚡️ سريعة",
                        callback_data="tt:shot:fast"
                    ),
                    InlineKeyboardButton(
                        "🎯 دقيقة",
                        callback_data="tt:shot:precise"
                    ),
                ],

                [
                    InlineKeyboardButton(
                        "🌀 Spin",
                        callback_data="tt:shot:spin"
                    ),
                    InlineKeyboardButton(
                        "💥 Smash",
                        callback_data="tt:shot:smash"
                    ),
                ]

            ]),
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # اختيار الضربة
    # -----------------------------------------------------

    if query.data.startswith(
        "tt:shot:"
    ):

        attacker = current_attacker(
            game
        )

        if not attacker:
            return

        if attacker.user_id != user.id:

            await query.answer(
                "❌ ليس دورك.",
                show_alert=True
            )

            return

        shot = query.data.split(
            ":"
        )[-1]

        game.attacker_action = shot

        game.last_action = (
            f"{SHOT_NAMES.get(shot, shot)} "
            f"{game.attacker_direction}"
        )

        # تحديث الصورة
        await send_or_update_image(
            None,
            context,
            game
        )

        await query.edit_message_text(
            (
                "🏓 تم اختيار الضربة!\n\n"
                f"🎯 الاتجاه: "
                f"<b>{game.attacker_direction}</b>\n"
                f"💥 الضربة: "
                f"<b>{SHOT_NAMES.get(shot, shot)}</b>\n\n"
                "🛡️ بانتظار دفاع الخصم..."
            ),
            parse_mode="HTML"
        )

        await send_defender_controls(
            context,
            game
        )

        return

    # -----------------------------------------------------
    # دفاع
    # -----------------------------------------------------

    if query.data.startswith(
        "tt:def:"
    ):

        defender = get_player(
            game,
            game.defender_id
        )

        if not defender:
            return

        if defender.user_id != user.id:

            await query.answer(
                "❌ ليس دورك للدفاع.",
                show_alert=True
            )

            return

        defense = query.data.split(
            ":"
        )[-1]

        game.defender_action = defense

        game.last_action = (
            f"{DEFENSE_NAMES.get(defense, defense)}"
        )

        await query.edit_message_text(
            (
                "🛡️ تم اختيار الدفاع!\n\n"
                f"{DEFENSE_NAMES.get(defense, defense)}\n\n"
                "🏓 جاري حساب التبادل..."
            )
        )

        await asyncio.sleep(1)

        await resolve_exchange(
            context,
            game
        )

        return
