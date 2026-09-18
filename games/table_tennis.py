# games/table_tennis.py

import asyncio
import io
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import ContextTypes, filters


# ==================================================
# الصلاحيات
# ==================================================

try:
    from handlers.roles import (
        is_primary_developer,
        is_secondary_developer,
        get_rank,
    )
except Exception:
    is_primary_developer = lambda _uid: False
    is_secondary_developer = lambda _uid: False
    get_rank = lambda _uid: ""


try:
    from permissions import get_permission_level
except Exception:
    get_permission_level = lambda _uid: 0


# ==================================================
# النقاط
# ==================================================

try:
    from handlers.points import add_points
except Exception:
    add_points = None


# ==================================================
# إعدادات اللعبة
# ==================================================

MAX_PLAYERS = 4
MIN_PLAYERS = 2

WIN_POINTS = 150

TARGET_SCORE = 11

TURN_TIME = 15

MAX_STAMINA = 100

# تكلفة الضربات
SHOT_COSTS = {
    "fast": 15,
    "precise": 8,
    "spin": 10,
    "smash": 30,
    "block": 5,
}


# ==================================================
# الحالة
# ==================================================

@dataclass
class TTPlayer:

    user_id: int
    name: str

    team: str = ""

    score: int = 0

    stamina: int = MAX_STAMINA

    shots: int = 0
    successful_shots: int = 0
    failed_shots: int = 0

    smash_count: int = 0

    combo: int = 0
    best_combo: int = 0


@dataclass
class TableTennisState:

    chat_id: int

    host_id: int
    host_name: str

    players: List[TTPlayer] = field(default_factory=list)

    started: bool = False
    finished: bool = False

    mode: str = ""

    current_index: int = 0

    # آخر لاعب ضرب
    last_player_id: Optional[int] = None

    # آخر ضربة
    last_shot: str = ""

    last_direction: str = ""

    # مكان الكرة
    ball_position: str = "center"

    # من عليه الدور
    waiting_for: Optional[int] = None

    # هل الكرة في اللعب
    rally_active: bool = False

    # النتيجة
    score_red: int = 0
    score_blue: int = 0

    # الرسالة الرئيسية
    message_id: Optional[int] = None

    # المهمة المؤقتة
    turn_task: Optional[asyncio.Task] = None

    # ترتيب الأدوار في 2v2
    turn_order: List[int] = field(default_factory=list)

    # رقم التبادل
    rally_number: int = 0

    # آخر نتيجة
    last_result: str = ""

    # أفضل ضربة إحصائيًا فقط
    best_shot: str = ""

    # أعلى كومبو إحصائي فقط
    best_combo: int = 0


# ==================================================
# الألعاب النشطة
# ==================================================

TABLE_TENNIS_GAMES: Dict[int, TableTennisState] = {}


# ==================================================
# فلتر اللعبة النشطة
# ==================================================

class TableTennisActiveFilter(filters.MessageFilter):

    def __init__(self, patterns=None):

        super().__init__()

        self.patterns = patterns or []

    def filter(self, message):

        if not message:
            return False

        chat = message.chat

        if not chat:
            return False

        if chat.id not in TABLE_TENNIS_GAMES:
            return False

        if not self.patterns:
            return True

        text = message.text or ""

        import re

        return any(
            re.match(pattern, text)
            for pattern in self.patterns
        )


# ==================================================
# أدوات عامة
# ==================================================

def _get_rank_level(user_id: int) -> int:

    try:

        level = get_permission_level(user_id)

        if isinstance(level, int):
            return level

    except Exception:
        pass

    try:

        rank = get_rank(user_id)

    except Exception:

        rank = ""

    levels = {
        "عضو": 0,
        "مميز": 1,
        "ادمن": 2,
        "ادمن اساسي": 3,
        "نائب المالك": 4,
        "المالك": 5,
        "Dev": 6,
    }

    return levels.get(rank, 0)


def _is_admin_plus(user_id: int) -> bool:

    return _get_rank_level(user_id) >= 2


def _is_developer(user_id: int) -> bool:

    try:

        if is_primary_developer(user_id):
            return True

    except Exception:
        pass

    try:

        if is_secondary_developer(user_id):
            return True

    except Exception:
        pass

    return _get_rank_level(user_id) >= 6


def _is_controller(
    state: TableTennisState,
    user_id: int
) -> bool:

    return (
        user_id == state.host_id
        or _is_developer(user_id)
    )


def _ensure_group(update: Update) -> bool:

    chat = update.effective_chat

    if not chat:
        return False

    return chat.type in (
        "group",
        "supergroup",
    )


async def _give_points(
    user_id: int,
    amount: int = WIN_POINTS
):

    if not add_points:
        return

    attempts = [

        ((user_id, amount), {}),

        (
            (),
            {
                "user_id": user_id,
                "amount": amount,
            }
        ),

        (
            (),
            {
                "user_id": user_id,
                "points": amount,
            }
        ),

        (
            (user_id,),
            {
                "points": amount,
            }
        ),
    ]

    for args, kwargs in attempts:

        try:

            result = add_points(
                *args,
                **kwargs
            )

            if asyncio.iscoroutine(result):

                await result

            return

        except TypeError:

            continue

        except Exception:

            return


async def _safe_delete(
    context,
    chat_id: int,
    message_id: Optional[int]
):

    if not message_id:
        return

    try:

        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )

    except Exception:
        pass


# ==================================================
# الخطوط
# ==================================================

def _font(size: int):

    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in paths:

        try:
            return ImageFont.truetype(
                path,
                size
            )

        except Exception:
            continue

    return ImageFont.load_default()


# ==================================================
# إنشاء صورة المباراة
# ==================================================

def _create_match_image(
    state: TableTennisState
):

    WIDTH = 1200
    HEIGHT = 800

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (25, 25, 35)
    )

    draw = ImageDraw.Draw(image)

    # ==================================================
    # الخلفية
    # ==================================================

    draw.rectangle(
        (0, 0, WIDTH, HEIGHT),
        fill=(24, 28, 40)
    )

    # الجمهور
    for row in range(3):

        y = 80 + row * 45

        for x in range(
            40,
            WIDTH - 40,
            45
        ):

            radius = random.randint(
                5,
                9
            )

            draw.ellipse(
                (
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius
                ),
                fill=(
                    random.randint(70, 150),
                    random.randint(70, 150),
                    random.randint(70, 150)
                )
            )

    # ==================================================
    # لوحة النتيجة
    # ==================================================

    score_font = _font(55)
    title_font = _font(30)

    draw.rounded_rectangle(
        (380, 25, 820, 125),
        radius=25,
        fill=(15, 15, 20)
    )

    draw.text(
        (600, 48),
        f"{state.score_red}  —  {state.score_blue}",
        font=score_font,
        anchor="mm",
        fill=(255, 255, 255)
    )

    draw.text(
        (600, 105),
        "🏓 TABLE TENNIS",
        font=title_font,
        anchor="mm",
        fill=(220, 220, 220)
    )

    # ==================================================
    # الملعب
    # ==================================================

    table_x1 = 160
    table_y1 = 270

    table_x2 = 1040
    table_y2 = 620

    # أرضية
    draw.rectangle(
        (80, 200, 1120, 700),
        fill=(40, 90, 65)
    )

    # حدود الطاولة
    draw.rounded_rectangle(
        (
            table_x1,
            table_y1,
            table_x2,
            table_y2
        ),
        radius=15,
        fill=(30, 90, 150),
        outline=(255, 255, 255),
        width=6
    )

    # خط المنتصف
    center_x = (
        table_x1 + table_x2
    ) // 2

    draw.line(
        (
            center_x,
            table_y1,
            center_x,
            table_y2
        ),
        fill=(255, 255, 255),
        width=4
    )

    # الشبكة
    net_y = (
        table_y1 + table_y2
    ) // 2

    draw.rectangle(
        (
            table_x1 - 10,
            net_y - 10,
            table_x2 + 10,
            net_y + 10
        ),
        fill=(230, 230, 230)
    )

    # ==================================================
    # اللاعبين
    # ==================================================

    red_players = [
        p for p in state.players
        if p.team == "red"
    ]

    blue_players = [
        p for p in state.players
        if p.team == "blue"
    ]

    # الأحمر
    for i, player in enumerate(
        red_players
    ):

        x = 260 + i * 100
        y = 225

        active = (
            state.waiting_for
            == player.user_id
        )

        radius = 38 if active else 32

        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            fill=(190, 45, 55),
            outline=(
                255,
                230,
                80
            ) if active else None,
            width=5
        )

    # الأزرق
    for i, player in enumerate(
        blue_players
    ):

        x = 740 + i * 100
        y = 665

        active = (
            state.waiting_for
            == player.user_id
        )

        radius = 38 if active else 32

        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            fill=(45, 90, 200),
            outline=(
                255,
                230,
                80
            ) if active else None,
            width=5
        )

    # ==================================================
    # الكرة
    # ==================================================

    positions = {

        "center": (
            center_x,
            net_y
        ),

        "up": (
            center_x,
            table_y1 + 70
        ),

        "down": (
            center_x,
            table_y2 - 70
        ),

        "left": (
            table_x1 + 130,
            net_y
        ),

        "right": (
            table_x2 - 130,
            net_y
        ),

        "up_left": (
            table_x1 + 180,
            table_y1 + 80
        ),

        "up_right": (
            table_x2 - 180,
            table_y1 + 80
        ),

        "down_left": (
            table_x1 + 180,
            table_y2 - 80
        ),

        "down_right": (
            table_x2 - 180,
            table_y2 - 80
        ),
    }

    bx, by = positions.get(
        state.ball_position,
        positions["center"]
    )

    draw.ellipse(
        (
            bx - 12,
            by - 12,
            bx + 12,
            by + 12
        ),
        fill=(255, 255, 255),
        outline=(30, 30, 30),
        width=3
    )

    # ==================================================
    # أسماء اللاعبين والطاقة
    # ==================================================

    name_font = _font(22)
    small_font = _font(17)

    # الأحمر
    y = 725

    for player in red_players:

        text = (
            f"🔴 {player.name}  "
            f"⚡ {player.stamina}"
        )

        draw.text(
            (80, y),
            text,
            font=name_font,
            fill=(255, 255, 255)
        )

        y += 30

    # الأزرق
    y = 725

    for player in blue_players:

        text = (
            f"🔵 {player.name}  "
            f"⚡ {player.stamina}"
        )

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=name_font
        )

        draw.text(
            (
                WIDTH - (
                    bbox[2] - bbox[0]
                ) - 80,
                y
            ),
            text,
            font=name_font,
            fill=(255, 255, 255)
        )

        y += 30

    # ==================================================
    # آخر ضربة
    # ==================================================

    if state.last_shot:

        text = (
            f"{state.last_shot}"
            f"  {state.last_direction}"
        )

        draw.rounded_rectangle(
            (
                430,
                145,
                770,
                195
            ),
            radius=15,
            fill=(15, 15, 20)
        )

        draw.text(
            (
                600,
                170
            ),
            text,
            font=small_font,
            anchor="mm",
            fill=(255, 255, 255)
        )

    # ==================================================
    # تحسين بسيط
    # ==================================================

    image = image.filter(
        ImageFilter.SHARPEN
    )

    output = io.BytesIO()

    image.save(
        output,
        format="PNG"
    )

    output.seek(0)

    return output


# ==================================================
# إنشاء لوحة الأزرار
# ==================================================

def _shot_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "↖️",
                callback_data="tt:dir:up_left"
            ),
            InlineKeyboardButton(
                "⬆️",
                callback_data="tt:dir:up"
            ),
            InlineKeyboardButton(
                "↗️",
                callback_data="tt:dir:up_right"
            ),
        ],

        [
            InlineKeyboardButton(
                "⬅️",
                callback_data="tt:dir:left"
            ),
            InlineKeyboardButton(
                "🎯",
                callback_data="tt:dir:center"
            ),
            InlineKeyboardButton(
                "➡️",
                callback_data="tt:dir:right"
            ),
        ],

        [
            InlineKeyboardButton(
                "↙️",
                callback_data="tt:dir:down_left"
            ),
            InlineKeyboardButton(
                "⬇️",
                callback_data="tt:dir:down"
            ),
            InlineKeyboardButton(
                "↘️",
                callback_data="tt:dir:down_right"
            ),
        ],

        [
            InlineKeyboardButton(
                "⚡ سريعة",
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
            InlineKeyboardButton(
                "🛡️ صد",
                callback_data="tt:shot:block"
            ),
        ],
    ])


# ==================================================
# توزيع الفرق
# ==================================================

def _assign_teams(
    state: TableTennisState
):

    players = state.players[:]

    random.shuffle(players)

    if len(players) == 2:

        players[0].team = "red"
        players[1].team = "blue"

        state.mode = "1v1"

    elif len(players) == 4:

        players[0].team = "red"
        players[1].team = "red"

        players[2].team = "blue"
        players[3].team = "blue"

        state.mode = "2v2"


# ==================================================
# ترتيب الأدوار
# ==================================================

def _build_turn_order(
    state: TableTennisState
):

    if state.mode == "1v1":

        state.turn_order = [
            p.user_id
            for p in state.players
        ]

        return

    red = [
        p.user_id
        for p in state.players
        if p.team == "red"
    ]

    blue = [
        p.user_id
        for p in state.players
        if p.team == "blue"
    ]

    state.turn_order = []

    count = min(
        len(red),
        len(blue)
    )

    for i in range(count):

        state.turn_order.append(
            red[i]
        )

        state.turn_order.append(
            blue[i]
        )


# ==================================================
# اللاعب الحالي
# ==================================================

def _current_player(
    state: TableTennisState
) -> Optional[TTPlayer]:

    if not state.turn_order:
        return None

    user_id = state.turn_order[
        state.current_index
        % len(state.turn_order)
    ]

    for player in state.players:

        if player.user_id == user_id:

            return player

    return None


# ==================================================
# الفريق المقابل
# ==================================================

def _opponent_team(
    player: TTPlayer
):

    return (
        "blue"
        if player.team == "red"
        else "red"
    )


# ==================================================
# تحديد نجاح الضربة
# ==================================================

def _shot_success_probability(
    shot: str,
    direction: str,
    player: TTPlayer
) -> float:

    base = {

        "fast": 0.74,

        "precise": 0.82,

        "spin": 0.78,

        "smash": 0.58,

        "block": 0.88,
    }.get(
        shot,
        0.70
    )

    # الطاقة تؤثر
    if player.stamina < 30:

        base -= 0.15

    elif player.stamina < 50:

        base -= 0.07

    # الزوايا أصعب
    if direction in (
        "up_left",
        "up_right",
        "down_left",
        "down_right"
    ):

        base -= 0.03

    return max(
        0.15,
        min(
            base,
            0.95
        )
    )


# ==================================================
# حساب النقطة
# ==================================================

def _give_point_to_opponent(
    state: TableTennisState,
    player: TTPlayer
):

    opponent_team = _opponent_team(
        player
    )

    if opponent_team == "red":

        state.score_red += 1

    else:

        state.score_blue += 1


def _give_point_to_player_team(
    state: TableTennisState,
    player: TTPlayer
):

    if player.team == "red":

        state.score_red += 1

    else:

        state.score_blue += 1


# ==================================================
# هل انتهت المباراة؟
# ==================================================

def _winner_team(
    state: TableTennisState
):

    red = state.score_red
    blue = state.score_blue

    if (
        red >= TARGET_SCORE
        and red - blue >= 2
    ):

        return "red"

    if (
        blue >= TARGET_SCORE
        and blue - red >= 2
    ):

        return "blue"

    return None


# ==================================================
# تحديث الطاقة
# ==================================================

def _consume_stamina(
    player: TTPlayer,
    shot: str
):

    cost = SHOT_COSTS.get(
        shot,
        10
    )

    player.stamina = max(
        0,
        player.stamina - cost
    )


def _recover_stamina(
    state: TableTennisState
):

    for player in state.players:

        player.stamina = min(
            MAX_STAMINA,
            player.stamina + 3
        )


# ==================================================
# إرسال صورة المباراة
# ==================================================

async def _send_match(
    state: TableTennisState,
    context: ContextTypes.DEFAULT_TYPE,
    caption: str,
    keyboard=None
):

    image = _create_match_image(
        state
    )

    photo = InputFile(
        image,
        filename="table_tennis.png"
    )

    if state.message_id:

        try:

            message = (
                await context.bot.edit_message_media(
                    chat_id=state.chat_id,
                    message_id=state.message_id,
                    media=__import__(
                        "telegram"
                    ).InputMediaPhoto(
                        media=photo,
                        caption=caption
                    ),
                )
            )

            if keyboard:

                await context.bot.edit_message_reply_markup(
                    chat_id=state.chat_id,
                    message_id=state.message_id,
                    reply_markup=keyboard
                )

            return message

        except Exception:

            pass

    message = await context.bot.send_photo(
        chat_id=state.chat_id,
        photo=photo,
        caption=caption,
        reply_markup=keyboard
    )

    state.message_id = message.message_id

    return message


# ==================================================
# وصف المباراة
# ==================================================

def _match_caption(
    state: TableTennisState
):

    red = [
        p.name
        for p in state.players
        if p.team == "red"
    ]

    blue = [
        p.name
        for p in state.players
        if p.team == "blue"
    ]

    red_text = (
        " — ".join(red)
        if red
        else "لا يوجد"
    )

    blue_text = (
        " — ".join(blue)
        if blue
        else "لا يوجد"
    )

    current = _current_player(
        state
    )

    current_name = (
        current.name
        if current
        else "—"
    )

    text = (
        "🏓 <b>طاولة تنس</b>\n\n"
        f"🔴 <b>الفريق الأحمر:</b> "
        f"{red_text}\n"
        f"🔵 <b>الفريق الأزرق:</b> "
        f"{blue_text}\n\n"
        f"🏆 <b>{state.score_red} — "
        f"{state.score_blue}</b>\n\n"
        f"🎯 الدور: <b>{current_name}</b>"
    )

    if state.last_result:

        text += (
            f"\n\n{state.last_result}"
        )

    return text


# ==================================================
# انتهاء المهمة المؤقتة
# ==================================================

async def _cancel_turn_task(
    state: TableTennisState
):

    if not state.turn_task:
        return

    if state.turn_task.done():
        return

    state.turn_task.cancel()

    try:

        await state.turn_task

    except asyncio.CancelledError:
        pass

    except Exception:
        pass


# ==================================================
# مؤقت الدور
# ==================================================

async def _turn_timeout(
    state: TableTennisState,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int
):

    try:

        await asyncio.sleep(
            TURN_TIME
        )

    except asyncio.CancelledError:

        return

    if (
        state.finished
        or not state.started
        or state.waiting_for != user_id
    ):

        return

    player = next(
        (
            p for p in state.players
            if p.user_id == user_id
        ),
        None
    )

    if not player:
        return

    # الوقت انتهى = نقطة للخصم
    _give_point_to_opponent(
        state,
        player
    )

    player.failed_shots += 1
    player.combo = 0

    state.last_result = (
        f"⏰ <b>{player.name}</b> "
        "تأخر في الرد!\n"
        "🏓 نقطة للفريق الخصم."
    )

    state.current_index += 1

    winner = _winner_team(
        state
    )

    if winner:

        await _finish_match(
            state,
            context,
            winner
        )

        return

    state.waiting_for = (
        _current_player(state).user_id
    )

    state.rally_active = False

    await _send_match(
        state,
        context,
        _match_caption(state),
        _shot_keyboard()
    )

    state.turn_task = asyncio.create_task(
        _turn_timeout(
            state,
            context,
            state.waiting_for
        )
    )


# ==================================================
# إنشاء اللعبة
# ==================================================

async def start_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not _ensure_group(update):

        return

    chat_id = update.effective_chat.id

    if chat_id in TABLE_TENNIS_GAMES:

        await update.message.reply_text(
            "🏓 توجد لعبة طاولة تنس بالفعل في هذا القروب."
        )

        return

    user = update.effective_user

    if not user:

        return

    if not _is_admin_plus(
        user.id
    ) and not _is_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذه اللعبة متاحة للأدمن وفوق."
        )

        return

    state = TableTennisState(
        chat_id=chat_id,
        host_id=user.id,
        host_name=user.first_name
        or "الهوست"
    )

    TABLE_TENNIS_GAMES[
        chat_id
    ] = state

    await update.message.reply_text(

        "🏓 <b>طاولة تنس</b>\n\n"

        "🎮 تم إنشاء المباراة!\n\n"

        "👥 اللاعبين: <b>0/4</b>\n\n"

        "يمكن للاعبين الدخول بكتابة:\n"
        "👉 <code>دخول</code>\n\n"

        "🚪 للخروج:\n"
        "👉 <code>.خروج</code>\n\n"

        "▶️ عند اكتمال اللاعبين، "
        "الهوست يكتب:\n"
        "👉 <code>.ابدا</code>",

        parse_mode="HTML"
    )


# ==================================================
# الدخول
# ==================================================

async def join_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not _ensure_group(update):

        return

    chat_id = update.effective_chat.id

    state = TABLE_TENNIS_GAMES.get(
        chat_id
    )

    if not state:

        return

    if state.started:

        return

    if state.finished:

        return

    user = update.effective_user

    if not user:
        return

    if any(
        p.user_id == user.id
        for p in state.players
    ):

        await update.message.reply_text(
            "🏓 أنت داخل اللعبة بالفعل."
        )

        return

    if len(state.players) >= MAX_PLAYERS:

        await update.message.reply_text(
            "❌ اكتمل عدد اللاعبين."
        )

        return

    player = TTPlayer(
        user_id=user.id,
        name=user.first_name
        or "لاعب"
    )

    state.players.append(
        player
    )

    await update.message.reply_text(

        "🏓 تم دخولك في طاولة التنس!\n\n"

        f"👤 <b>{player.name}</b>\n"
        f"👥 اللاعبين: "
        f"<b>{len(state.players)}/{MAX_PLAYERS}</b>",

        parse_mode="HTML"
    )


# ==================================================
# الخروج
# ==================================================

async def leave_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not _ensure_group(update):

        return

    chat_id = update.effective_chat.id

    state = TABLE_TENNIS_GAMES.get(
        chat_id
    )

    if not state:

        return

    if state.started:

        await update.message.reply_text(
            "❌ لا يمكنك الخروج بعد بدء المباراة."
        )

        return

    user = update.effective_user

    if not user:
        return

    old_length = len(
        state.players
    )

    state.players = [
        p for p in state.players
        if p.user_id != user.id
    ]

    if len(state.players) == old_length:

        await update.message.reply_text(
            "❌ أنت لست داخل اللعبة."
        )

        return

    await update.message.reply_text(
        "🚪 تم خروجك من طاولة التنس."
    )


# ==================================================
# بدء المباراة
# ==================================================

async def begin_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not _ensure_group(update):

        return

    chat_id = update.effective_chat.id

    state = TABLE_TENNIS_GAMES.get(
        chat_id
    )

    if not state:

        return

    user = update.effective_user

    if not user:
        return

    if not _is_controller(
        state,
        user.id
    ):

        await update.message.reply_text(
            "❌ فقط الهوست أو المطور يستطيع بدء المباراة."
        )

        return

    if state.started:

        return

    if len(state.players) < MIN_PLAYERS:

        await update.message.reply_text(
            "❌ تحتاج إلى لاعبين على الأقل لبدء المباراة."
        )

        return

    _assign_teams(state)

    _build_turn_order(state)

    state.started = True

    state.finished = False

    state.current_index = 0

    state.score_red = 0

    state.score_blue = 0

    current = _current_player(
        state
    )

    state.waiting_for = (
        current.user_id
        if current
        else None
    )

    state.last_result = (
        "🎮 <b>بدأت المباراة!</b>"
    )

    # حذف رسالة الانتظار القديمة ليس ضروريًا
    # ونرسل صورة مستقلة للمباراة.

    await _send_match(
        state,
        context,
        _match_caption(state),
        _shot_keyboard()
    )

    if state.waiting_for:

        state.turn_task = asyncio.create_task(
            _turn_timeout(
                state,
                context,
                state.waiting_for
            )
        )


# ==================================================
# معالجة الأزرار
# ==================================================

async def table_tennis_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    message = query.message

    if not message:
        return

    chat_id = message.chat.id

    state = TABLE_TENNIS_GAMES.get(
        chat_id
    )

    if not state:

        await query.answer(
            "انتهت اللعبة.",
            show_alert=True
        )

        return

    if not state.started:

        await query.answer(
            "المباراة لم تبدأ بعد.",
            show_alert=True
        )

        return

    if state.finished:

        await query.answer(
            "انتهت المباراة.",
            show_alert=True
        )

        return

    user = query.from_user

    if not user:
        return

    if state.waiting_for != user.id:

        await query.answer(
            "⏳ ليس دورك الآن.",
            show_alert=True
        )

        return

    data = query.data or ""

    # ==================================================
    # اختيار الاتجاه
    # ==================================================

    if data.startswith(
        "tt:dir:"
    ):

        direction = data.split(
            ":",
            2
        )[2]

        context.user_data[
            "tt_direction"
        ] = direction

        names = {

            "up_left": "↖️",

            "up": "⬆️",

            "up_right": "↗️",

            "left": "⬅️",

            "center": "🎯",

            "right": "➡️",

            "down_left": "↙️",

            "down": "⬇️",

            "down_right": "↘️",
        }

        await query.answer(
            f"تم اختيار {names.get(direction, '🎯')}"
        )

        return

    # ==================================================
    # اختيار نوع الضربة
    # ==================================================

    if data.startswith(
        "tt:shot:"
    ):

        shot = data.split(
            ":",
            2
        )[2]

        direction = context.user_data.get(
            "tt_direction"
        )

        if not direction:

            await query.answer(
                "⚠️ اختر اتجاه الكرة أولًا.",
                show_alert=True
            )

            return

        await _perform_shot(
            state,
            context,
            user.id,
            shot,
            direction
        )

        context.user_data.pop(
            "tt_direction",
            None
        )


# ==================================================
# تنفيذ الضربة
# ==================================================

async def _perform_shot(
    state: TableTennisState,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    shot: str,
    direction: str
):

    player = next(
        (
            p for p in state.players
            if p.user_id == user_id
        ),
        None
    )

    if not player:

        return

    await _cancel_turn_task(
        state
    )

    # ==================================================
    # استهلاك الطاقة
    # ==================================================

    _consume_stamina(
        player,
        shot
    )

    player.shots += 1

    if shot == "smash":

        player.smash_count += 1

    # ==================================================
    # فرصة النجاح
    # ==================================================

    probability = (
        _shot_success_probability(
            shot,
            direction,
            player
        )
    )

    success = (
        random.random()
        < probability
    )

    state.last_player_id = user_id

    state.last_direction = {
        "up_left": "↖️",
        "up": "⬆️",
        "up_right": "↗️",
        "left": "⬅️",
        "center": "🎯",
        "right": "➡️",
        "down_left": "↙️",
        "down": "⬇️",
        "down_right": "↘️",
    }.get(
        direction,
        "🎯"
    )

    state.last_shot = {
        "fast": "⚡ سريعة",
        "precise": "🎯 دقيقة",
        "spin": "🌀 Spin",
        "smash": "💥 Smash",
        "block": "🛡️ صد",
    }.get(
        shot,
        shot
    )

    state.rally_number += 1

    # ==================================================
    # ضربة فاشلة
    # ==================================================

    if not success:

        player.failed_shots += 1

        player.combo = 0

        _give_point_to_opponent(
            state,
            player
        )

        state.last_result = (
            f"❌ <b>{player.name}</b> "
            f"أخطأ في {state.last_shot} "
            f"{state.last_direction}!\n"
            "🏓 نقطة للفريق الخصم."
        )

        state.current_index += 1

        _recover_stamina(
            state
        )

        winner = _winner_team(
            state
        )

        if winner:

            await _finish_match(
                state,
                context,
                winner
            )

            return

        current = _current_player(
            state
        )

        state.waiting_for = (
            current.user_id
            if current
            else None
        )

        state.ball_position = "center"

        await _send_match(
            state,
            context,
            _match_caption(state),
            _shot_keyboard()
        )

        if state.waiting_for:

            state.turn_task = asyncio.create_task(
                _turn_timeout(
                    state,
                    context,
                    state.waiting_for
                )
            )

        return

    # ==================================================
    # ضربة ناجحة
    # ==================================================

    player.successful_shots += 1

    player.combo += 1

    player.best_combo = max(
        player.best_combo,
        player.combo
    )

    state.best_combo = max(
        state.best_combo,
        player.combo
    )

    if shot == "smash":

        state.best_shot = "💥 Smash"

    elif not state.best_shot:

        state.best_shot = state.last_shot

    # ==================================================
    # تحريك الكرة
    # ==================================================

    state.ball_position = direction

    # ==================================================
    # عرض الرد
    # ==================================================

    state.last_result = (
        f"🏓 <b>رد ناجح!</b>\n"
        f"🔴 <b>{player.name}</b>\n"
        f"{state.last_shot} "
        f"{state.last_direction}\n\n"
        "⏳ الكرة مستمرة في اللعب..."
    )

    # الدور ينتقل
    state.current_index += 1

    current = _current_player(
        state
    )

    state.waiting_for = (
        current.user_id
        if current
        else None
    )

    _recover_stamina(
        state
    )

    await _send_match(
        state,
        context,
        _match_caption(state),
        _shot_keyboard()
    )

    if state.waiting_for:

        state.turn_task = asyncio.create_task(
            _turn_timeout(
                state,
                context,
                state.waiting_for
            )
        )


# ==================================================
# إنهاء المباراة
# ==================================================

async def _finish_match(
    state: TableTennisState,
    context: ContextTypes.DEFAULT_TYPE,
    winner_team: str
):

    if state.finished:

        return

    state.finished = True
    state.started = False

    await _cancel_turn_task(
        state
    )

    winners = [
        p for p in state.players
        if p.team == winner_team
    ]

    losers = [
        p for p in state.players
        if p.team != winner_team
    ]

    # ==================================================
    # النقاط
    # ==================================================

    for player in winners:

        await _give_points(
            player.user_id,
            WIN_POINTS
        )

    winner_names = " — ".join(
        p.name
        for p in winners
    )

    loser_names = " — ".join(
        p.name
        for p in losers
    )

    winner_label = (
        "🔴 الفريق الأحمر"
        if winner_team == "red"
        else "🔵 الفريق الأزرق"
    )

    state.last_result = (
        "🏆 <b>انتهت المباراة!</b>\n\n"
        f"🥇 {winner_label}\n"
        f"{winner_names}\n\n"
        f"💰 مكافأة الفوز: "
        f"<b>+{WIN_POINTS} نقطة</b> لكل فائز"
    )

    await _send_match(
        state,
        context,
        _match_caption(state),
        None
    )

    # ==================================================
    # رسالة النتيجة
    # ==================================================

    await context.bot.send_message(

        chat_id=state.chat_id,

        text=(

            "🏆 <b>انتهت مباراة طاولة التنس!</b>\n\n"

            f"🥇 <b>الفائز:</b>\n"
            f"{winner_names}\n\n"

            f"🏆 النتيجة:\n"
            f"🔴 {state.score_red}"
            f" — "
            f"{state.score_blue} 🔵\n\n"

            f"💰 <b>+{WIN_POINTS} نقطة</b>"
            " لكل لاعب من الفريق الفائز.\n\n"

            f"💥 أفضل ضربة: "
            f"{state.best_shot or '—'}\n"

            f"🔥 أعلى Combo: "
            f"×{state.best_combo}"
        ),

        parse_mode="HTML"
    )

    # ==================================================
    # إزالة اللعبة
    # ==================================================

    TABLE_TENNIS_GAMES.pop(
        state.chat_id,
        None
    )


# ==================================================
# الإنهاء اليدوي
# ==================================================

async def end_table_tennis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not _ensure_group(update):

        return

    chat_id = update.effective_chat.id

    state = TABLE_TENNIS_GAMES.get(
        chat_id
    )

    if not state:

        return

    user = update.effective_user

    if not user:
        return

    if not _is_controller(
        state,
        user.id
    ):

        await update.message.reply_text(
            "❌ فقط الهوست أو المطور يستطيع إنهاء اللعبة."
        )

        return

    await _cancel_turn_task(
        state
    )

    state.finished = True

    state.started = False

    TABLE_TENNIS_GAMES.pop(
        chat_id,
        None
    )

    await update.message.reply_text(
        "🛑 تم إنهاء لعبة طاولة التنس."
    )
