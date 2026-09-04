```python
# ============================================================
# 🍻 طاولة الكذب
# لعبة مستقلة عن games/liar.py
# ============================================================

import asyncio
import random

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from config import OWNER_ID

from games.big_game_lock import (
    get_big_game,
    lock_big_game,
    unlock_big_game,
)

from handlers.points import add_points


# ============================================================
# إعدادات اللعبة
# ============================================================

LIARS_TABLE_KEY = "liars_table"
LIARS_TABLE_NAME = "طاولة الكذب 🍻"

MIN_PLAYERS = 3

CARDS_PER_PLAYER = 5

TURN_TIME = 30

START_DELAY = 15

TRIGGER_TIME = 30

WIN_POINTS = 60

# فرص سحب الزناد لكل لاعب
TRIGGER_ATTEMPTS = 2


# ============================================================
# الألعاب النشطة
# ============================================================

active_liars_tables = {}


# ============================================================
# أسماء الكروت
# ============================================================

CARD_NAMES = {
    "K": "الملك 👑",
    "Q": "الملكة 👸",
    "A": "الآس 🅰️",
    "J": "الجوكر 🃏",
}


# ============================================================
# اسم اللاعب
# ============================================================

def get_player_name(user):
    if not user:
        return "لاعب"

    name = user.first_name or ""

    if user.last_name:
        name += f" {user.last_name}"

    return name.strip() or "لاعب"


def get_account_name(user):
    if not user:
        return "لاعب"

    if user.username:
        return f"@{user.username}"

    return get_player_name(user)


# ============================================================
# فحص أدمن القروب
# ============================================================

async def is_group_admin(update, context):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if user.id == OWNER_ID:
        return True

    try:
        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except Exception:
        return False


# ============================================================
# إنشاء أوراق
# ============================================================

def create_deck(player_count):

    # الأساس:
    # 6 ملك
    # 6 ملكة
    # 6 آس
    # 2 جوكر
    base_deck = (
        ["K"] * 6
        + ["Q"] * 6
        + ["A"] * 6
        + ["J"] * 2
    )

    required = player_count * CARDS_PER_PLAYER

    deck = []

    while len(deck) < required:
        deck.extend(base_deck)

    deck = deck[:required]

    random.shuffle(deck)

    return deck


# ============================================================
# توزيع الأوراق
# ============================================================

def deal_cards(game):

    players = game["players"]

    deck = create_deck(
        len(players)
    )

    game["hands"] = {}

    index = 0

    for player_id in players:

        game["hands"][player_id] = deck[
            index:index + CARDS_PER_PLAYER
        ]

        index += CARDS_PER_PLAYER


# ============================================================
# تحويل الكرت إلى نص
# ============================================================

def card_text(card):

    return CARD_NAMES.get(
        card,
        "كرت"
    )


# ============================================================
# كروت اللاعب كنص
# ============================================================

def hand_text(hand):

    if not hand:
        return "لا توجد كروت"

    return "، ".join(
        card_text(card)
        for card in hand
    )


# ============================================================
# حالة الفرص
# ============================================================

def attempts_text(attempts):

    if attempts >= 2:
        return "🟢🟢"

    if attempts == 1:
        return "🟢🔴"

    return "🔴🔴"


# ============================================================
# إنشاء زر التوجه للخاص
# ============================================================

async def build_private_url(
    context,
    chat_id
):

    me = await context.bot.get_me()

    username = me.username

    if not username:
        return None

    return (
        f"https://t.me/{username}"
        f"?start=liars_table_{chat_id}"
    )


# ============================================================
# رسالة دور اللاعب
# ============================================================

async def send_turn_message(
    context,
    chat_id
):

    game = active_liars_tables.get(chat_id)

    if not game:
        return

    if game["finished"]:
        return

    current_index = game["current_index"]

    if current_index >= len(game["players"]):
        current_index = 0
        game["current_index"] = 0

    player_id = game["players"][current_index]

    user = game["users"].get(player_id)

    if not user:
        return

    player_name = get_player_name(user)

    target = game["target"]

    previous = game.get("previous_play")

    text = (
        f"⬇️ دور: {player_name}\n\n"
        f"🃏 المطلوب: {card_text(target)}\n\n"
    )

    if previous:

        previous_user = game["users"].get(
            previous["player_id"]
        )

        previous_name = get_player_name(
            previous_user
        )

        text += (
            f"📦 السابق {previous_name} لعب "
            f"{len(previous['cards'])} كروت.\n\n"
        )

        text += (
            "اختر للعب: توجه للخاص، أو كذاب! "
            "لتكذيبه."
        )

    else:

        text += (
            "⚠️ اضغط توجه للخاص للعب."
        )

    keyboard = []

    private_url = await build_private_url(
        context,
        chat_id
    )

    if private_url:

        keyboard.append([
            InlineKeyboardButton(
                "توجه للخاص",
                url=private_url
            )
        ])

    if previous:

        keyboard.append([
            InlineKeyboardButton(
                "كذاب!",
                callback_data=(
                    f"lt:challenge:"
                    f"{chat_id}:"
                    f"{previous['player_id']}:"
                    f"{player_id}"
                )
            )
        ])

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    # مؤقت الدور
    old_task = game.get("turn_task")

    if old_task:
        old_task.cancel()

    game["turn_task"] = asyncio.create_task(
        turn_timeout(
            context,
            chat_id,
            player_id
        )
    )


# ============================================================
# انتهاء وقت الدور
# ============================================================

async def turn_timeout(
    context,
    chat_id,
    player_id
):

    try:
        await asyncio.sleep(TURN_TIME)

    except asyncio.CancelledError:
        return

    game = active_liars_tables.get(chat_id)

    if not game:
        return

    if game["finished"]:
        return

    if game["current_player"] != player_id:
        return

    # إذا انتهى الوقت ولم يلعب:
    # نختار من 1 إلى 3 كروت تلقائيًا
    hand = game["hands"].get(
        player_id,
        []
    )

    if not hand:
        return

    amount = min(
        len(hand),
        random.randint(1, 3)
    )

    cards = hand[:amount]

    await play_cards(
        context,
        chat_id,
        player_id,
        cards
    )


# ============================================================
# بدء اللعبة
# ============================================================

async def start_liars_table(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    chat_id = chat.id

    # إذا فيه طاولة بالفعل
    if chat_id in active_liars_tables:

        await update.message.reply_text(
            "⚠️ طاولة الكذب مفتوحة بالفعل!\n\n"
            "اكتب دخول للانضمام."
        )

        return

    # قفل الألعاب الكبيرة
    locked = lock_big_game(
        chat_id,
        LIARS_TABLE_KEY,
        LIARS_TABLE_NAME
    )

    if not locked:

        current = get_big_game(chat_id)

        name = (
            current["name"]
            if current
            else "لعبة أخرى"
        )

        await update.message.reply_text(
            f"⚠️ لا يمكن بدء طاولة الكذب الآن.\n\n"
            f"🎮 توجد لعبة كبيرة شغالة بالفعل: {name}"
        )

        return

    user = update.effective_user

    active_liars_tables[chat_id] = {

        "players": [
            user.id
        ],

        "users": {
            user.id: user
        },

        "host": user.id,

        "started": False,

        "finished": False,

        "hands": {},

        "target": None,

        "current_index": 0,

        "current_player": None,

        "previous_play": None,

        "selected_cards": {},

        "used_challenge": False,

        "trigger_player": None,

        "trigger_attempts": {},

        "turn_task": None,

        "trigger_task": None,

        "start_task": None,

        "resolving": False,
    }

    await update.message.reply_text(
        "🎲 تسجيل طاولة الكذب مفتوح! 🍻\n\n"
        "• اكتب دخول للانضمام.\n"
        "• الأدمن يكتب .ابدا للبدء.\n"
        "• الفرص: 2 🟢🟢."
    )


# ============================================================
# دخول اللاعب
# ============================================================

async def join_liars_table(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    game = active_liars_tables.get(chat_id)

    if not game:
        return

    if game["started"]:
        return

    user = update.effective_user

    if not user:
        return

    if user.id in game["players"]:

        await update.message.reply_text(
            f"⚠️ {get_player_name(user)} "
            "أنت داخل اللعبة بالفعل."
        )

        return

    game["players"].append(
        user.id
    )

    game["users"][user.id] = user

    await update.message.reply_text(
        f"✅ انضم {get_player_name(user)} 🍻\n"
        f"👥 العدد: {len(game['players'])}"
    )


# ============================================================
# خروج من اللوبي
# ============================================================

async def leave_liars_table(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    game = active_liars_tables.get(chat_id)

    if not game:
        return

    if game["started"]:
        return

    user = update.effective_user

    if not user:
        return

    if user.id not in game["players"]:
        return

    game["players"].remove(
        user.id
    )

    game["users"].pop(
        user.id,
        None
    )

    if not game["players"]:

        active_liars_tables.pop(
            chat_id,
            None
        )

        unlock_big_game(
            chat_id,
            LIARS_TABLE_KEY
        )

        await update.message.reply_text(
            "❌ تم إلغاء طاولة الكذب."
        )

        return

    await update.message.reply_text(
        f"🚪 خرج {get_player_name(user)}.\n"
        f"👥 العدد: {len(game['players'])}"
    )


# ============================================================
# بدء اللعبة بواسطة الأدمن
# ============================================================

async def begin_liars_table(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    game = active_liars_tables.get(chat_id)

    if not game:
        return

    if not await is_group_admin(
        update,
        context
    ):
        return

    if game["started"]:

        await update.message.reply_text(
            "⚠️ اللعبة بدأت بالفعل."
        )

        return

    if len(game["players"]) < MIN_PLAYERS:

        await update.message.reply_text(
            f"❌ لازم يكون عدد اللاعبين "
            f"{MIN_PLAYERS} لاعبين على الأقل."
        )

        return

    game["started"] = True

    game["current_index"] = 0

    deal_cards(game)

    game["target"] = random.choice(
        ["K", "Q", "A"]
    )

    game["previous_play"] = None

    game["selected_cards"] = {}

    game["current_player"] = None

    game["resolving"] = False

    await update.message.reply_text(
        "🎮 تبدأ اللعبة الآن!\n\n"
        "سيتم توزيع الأوراق وبدء الجولة الأولى."
    )

    # إرسال الكروت للخاص
    failed = []

    for player_id in game["players"]:

        try:

            await send_private_hand(
                context,
                chat_id,
                player_id,
                delay_message=True
            )

        except Exception:

            failed.append(
                player_id
            )

    if failed:

        names = []

        for player_id in failed:

            user = game["users"].get(
                player_id
            )

            names.append(
                get_player_name(user)
            )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ تعذر إرسال الكروت في الخاص إلى:\n"
                + "\n".join(
                    f"• {name}"
                    for name in names
                )
                + "\n\n"
                "تأكدوا أنكم فتحتوا الخاص مع البوت."
            )
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "📬 تم توزيع الكروت في الخاص "
            "على جميع اللاعبين!\n\n"
            f"⏳ يبدأ اللعب بالدور بعد "
            f"{START_DELAY} ثانية..."
        )
    )

    # إلغاء أي مؤقت قديم
    old_task = game.get("start_task")

    if old_task:
        old_task.cancel()

    game["start_task"] = asyncio.create_task(
        start_first_turn(
            context,
            chat_id
        )
    )


# ============================================================
# بداية أول دور
# ============================================================

async def start_first_turn(
    context,
    chat_id
):

    try:
        await asyncio.sleep(
            START_DELAY
        )

    except asyncio.CancelledError:
        return

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    game["current_index"] = 0

    await start_turn(
        context,
        chat_id
    )


# ============================================================
# بدء الدور
# ============================================================

async def start_turn(
    context,
    chat_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    if not game["players"]:
        return

    # تجاوز أي لاعب خرج
    while (
        game["players"]
        and game["current_index"]
        >= len(game["players"])
    ):
        game["current_index"] = 0

    if not game["players"]:
        return

    player_id = game["players"][
        game["current_index"]
    ]

    game["current_player"] = player_id

    game["selected_cards"][player_id] = []

    await send_turn_message(
        context,
        chat_id
    )


# ============================================================
# إرسال اليد في الخاص
# ============================================================

async def send_private_hand(
    context,
    chat_id,
    player_id,
    delay_message=False
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    hand = game["hands"].get(
        player_id,
        []
    )

    target = game["target"]

    text = (
        "🃏 كروتك في هذه الجولة:\n\n"
    )

    for index, card in enumerate(
        hand,
        start=1
    ):

        text += (
            f"{index}. {card_text(card)}\n"
        )

    text += (
        f"\n🎯 الكرت المطلوب: "
        f"{card_text(target)}\n\n"
    )

    if delay_message:

        text += (
            f"⏳ اللعب سيبدأ بعد "
            f"{START_DELAY} ثانية... استعد!"
        )

    else:

        text += (
            "\n🎯 اختر الكروت التي تريد لعبها."
        )

    keyboard = build_card_keyboard(
        chat_id,
        player_id
    )

    await context.bot.send_message(
        chat_id=player_id,
        text=text,
        reply_markup=keyboard
    )


# ============================================================
# كيبورد الكروت
# ============================================================

def build_card_keyboard(
    chat_id,
    player_id
):

    game = active_liars_tables.get(
        chat_id
    )

    selected = []

    if game:
        selected = game[
            "selected_cards"
        ].get(
            player_id,
            []
        )

    hand = []

    if game:
        hand = game[
            "hands"
        ].get(
            player_id,
            []
        )

    keyboard = []

    for index, card in enumerate(
        hand
    ):

        mark = (
            "✅ "
            if index in selected
            else ""
        )

        keyboard.append([
            InlineKeyboardButton(
                f"{mark}{index + 1}. {card_text(card)}",
                callback_data=(
                    f"lt:card:"
                    f"{chat_id}:"
                    f"{player_id}:"
                    f"{index}"
                )
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "📨 إرسال الكروت!",
            callback_data=(
                f"lt:play:"
                f"{chat_id}:"
                f"{player_id}"
            )
        )
    ])

    return InlineKeyboardMarkup(
        keyboard
    )


# ============================================================
# لعب الكروت
# ============================================================

async def play_cards(
    context,
    chat_id,
    player_id,
    cards
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    if game["resolving"]:
        return

    if game["current_player"] != player_id:
        return

    if not cards:
        return

    if len(cards) > 3:
        return

    hand = game["hands"].get(
        player_id,
        []
    )

    # التأكد أن الكروت موجودة فعلًا
    for card in cards:

        if card not in hand:
            return

    game["resolving"] = True

    # إلغاء مؤقت الدور
    task = game.get("turn_task")

    if task:
        task.cancel()

    # حذف الكروت من اليد
    remaining = hand.copy()

    for card in cards:

        if card in remaining:
            remaining.remove(card)

    game["hands"][player_id] = remaining

    user = game["users"].get(
        player_id
    )

    player_name = get_player_name(
        user
    )

    target = game["target"]

    # حفظ اللعب السابق
    game["previous_play"] = {
        "player_id": player_id,
        "cards": cards.copy(),
        "target": target
    }

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"📢 لعب اللاعب {player_name} "
            f"عدد {len(cards)} كروت!\n\n"
            f"🃏 وادعى أنها تطابق: "
            f"{card_text(target)}"
        )
    )

    await asyncio.sleep(1)

    game["resolving"] = False

    # اللاعب التالي
    if player_id in game["players"]:

        current_position = game[
            "players"
        ].index(player_id)

        game["current_index"] = (
            current_position + 1
        ) % len(game["players"])

    await context.bot.send_message(
        chat_id=chat_id,
        text="🔄 ينتقل الدور الآن..."
    )

    await start_turn(
        context,
        chat_id
    )


# ============================================================
# التحقق من الصدق
# ============================================================

def is_truthful(
    cards,
    target
):

    if not cards:
        return False

    for card in cards:

        # الجوكر يطابق أي كرت
        if card == "J":
            continue

        if card != target:
            return False

    return True


# ============================================================
# التحدي
# ============================================================

async def challenge_player(
    context,
    chat_id,
    challenger_id,
    accused_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    if game["resolving"]:
        return

    previous = game.get(
        "previous_play"
    )

    if not previous:
        return

    if previous["player_id"] != accused_id:
        return

    if challenger_id != game["current_player"]:
        return

    game["resolving"] = True

    accused_user = game["users"].get(
        accused_id
    )

    challenger_user = game["users"].get(
        challenger_id
    )

    accused_name = get_account_name(
        accused_user
    )

    challenger_name = get_account_name(
        challenger_user
    )

    cards = previous["cards"]

    target = previous["target"]

    truthful = is_truthful(
        cards,
        target
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🚨 تحدي: {challenger_name} 🆚 "
            f"{accused_name}\n\n"
            f"🔍 كروت {accused_name} الحقيقية:\n"
            f"{hand_text(cards)}"
        )
    )

    await asyncio.sleep(2)

    if truthful:

        result_text = (
            f"✅ صادق!\n\n"
            f"{accused_name} كان صادقاً! 😇\n\n"
            f"❌ {challenger_name} خسر التحدي."
        )

        loser_id = challenger_id

    else:

        result_text = (
            f"❌ كاذب!\n\n"
            f"{accused_name} كان يكذب! 🤥\n\n"
            f"❌ {accused_name} خسر التحدي."
        )

        loser_id = accused_id

    await context.bot.send_message(
        chat_id=chat_id,
        text=result_text
    )

    game["resolving"] = False

    # اللاعب الخاسر يسحب الزناد
    await start_trigger(
        context,
        chat_id,
        loser_id
    )


# ============================================================
# بدء سحب الزناد
# ============================================================

async def start_trigger(
    context,
    chat_id,
    player_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    game["trigger_player"] = player_id

    # إذا لم يكن له سجل
    if player_id not in game[
        "trigger_attempts"
    ]:

        game["trigger_attempts"][
            player_id
        ] = TRIGGER_ATTEMPTS

    attempts = game[
        "trigger_attempts"
    ][player_id]

    user = game["users"].get(
        player_id
    )

    name = get_account_name(
        user
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🔫 دور {name} لسحب الزناد!\n\n"
            f"المحاولات المتبقية: "
            f"{attempts_text(attempts)}\n\n"
            f"⏳ لديك {TRIGGER_TIME} ثانية."
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "سحب الزناد 🔫",
                    callback_data=(
                        f"lt:trigger:"
                        f"{chat_id}:"
                        f"{player_id}"
                    )
                )
            ]
        ])
    )

    old_task = game.get(
        "trigger_task"
    )

    if old_task:
        old_task.cancel()

    game["trigger_task"] = asyncio.create_task(
        trigger_timeout(
            context,
            chat_id,
            player_id
        )
    )


# ============================================================
# انتهاء وقت الزناد
# ============================================================

async def trigger_timeout(
    context,
    chat_id,
    player_id
):

    try:
        await asyncio.sleep(
            TRIGGER_TIME
        )

    except asyncio.CancelledError:
        return

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    if game["trigger_player"] != player_id:
        return

    await pull_trigger(
        context,
        chat_id,
        player_id
    )


# ============================================================
# سحب الزناد
# ============================================================

async def pull_trigger(
    context,
    chat_id,
    player_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    if game["trigger_player"] != player_id:
        return

    if game["resolving"]:
        return

    attempts = game[
        "trigger_attempts"
    ].get(
        player_id,
        TRIGGER_ATTEMPTS
    )

    if attempts <= 0:
        return

    game["resolving"] = True

    # إلغاء المؤقت
    task = game.get(
        "trigger_task"
    )

    if task:
        task.cancel()

    # هذه المحاولة انحسبت
    attempts -= 1

    game["trigger_attempts"][
        player_id
    ] = attempts

    await context.bot.send_message(
        chat_id=chat_id,
        text="🔫 بانتظار النتيجة…"
    )

    await asyncio.sleep(2)

    # الرصاصة قاتلة
    bullet = random.choice(
        [True, False]
    )

    user = game["users"].get(
        player_id
    )

    name = get_account_name(
        user
    )

    # ========================================================
    # 💥 رصاصة
    # ========================================================

    if bullet:

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "طعععععععع! انطلقت الرصاصة!! 💥🔫\n\n"
                f"{name} خرج من اللعبة."
            )
        )

        await eliminate_player(
            context,
            chat_id,
            player_id
        )

        return

    # ========================================================
    # كليك
    # ========================================================

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "كليك.. 🔫\n\n"
            f"{name} نجا! 😮‍💨"
        )
    )

    game["resolving"] = False

    # إذا بقيت محاولة
    if attempts > 0:

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🟢 بقيت لك محاولة واحدة "
                f"{attempts_text(attempts)}."
            )
        )

    else:

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🛡️ انتهت محاولات سحب الزناد "
                "لهذا اللاعب، لكنه نجا."
            )
        )

    # الجولة الجديدة
    await new_round(
        context,
        chat_id
    )


# ============================================================
# إخراج لاعب
# ============================================================

async def eliminate_player(
    context,
    chat_id,
    player_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if player_id in game["players"]:

        game["players"].remove(
            player_id
        )

    game["hands"].pop(
        player_id,
        None
    )

    game["selected_cards"].pop(
        player_id,
        None
    )

    # هل بقي لاعب واحد؟
    if len(game["players"]) <= 1:

        await finish_liars_table(
            context,
            chat_id
        )

        return

    # التأكد من current_index
    if game["current_index"] >= len(
        game["players"]
    ):

        game["current_index"] = 0

    game["trigger_player"] = None

    game["previous_play"] = None

    game["resolving"] = False

    await new_round(
        context,
        chat_id
    )


# ============================================================
# جولة جديدة
# ============================================================

async def new_round(
    context,
    chat_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    if len(game["players"]) <= 1:

        await finish_liars_table(
            context,
            chat_id
        )

        return

    deal_cards(game)

    game["target"] = random.choice(
        ["K", "Q", "A"]
    )

    game["previous_play"] = None

    game["selected_cards"] = {}

    game["current_index"] = 0

    game["current_player"] = None

    game["trigger_player"] = None

    game["resolving"] = False

    # إرسال الكروت من جديد
    for player_id in game["players"]:

        try:

            await send_private_hand(
                context,
                chat_id,
                player_id,
                delay_message=False
            )

        except Exception:
            pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "📜 جولة جديدة 🍻\n\n"
            f"🃏 الكرت المطلوب: "
            f"{card_text(game['target'])}\n\n"
            "👥 اللاعبون:"
        )
    )

    # إضافة قائمة اللاعبين
    players_text = ""

    for player_id in game["players"]:

        user = game["users"].get(
            player_id
        )

        attempts = game[
            "trigger_attempts"
        ].get(
            player_id,
            TRIGGER_ATTEMPTS
        )

        players_text += (
            f"• {get_player_name(user)}: "
            f"{attempts_text(attempts)}\n"
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text=players_text
    )

    await asyncio.sleep(1)

    await start_turn(
        context,
        chat_id
    )


# ============================================================
# إنهاء اللعبة
# ============================================================

async def finish_liars_table(
    context,
    chat_id
):

    game = active_liars_tables.get(
        chat_id
    )

    if not game:
        return

    if game["finished"]:
        return

    game["finished"] = True

    # إلغاء المؤقتات
    for key in (
        "turn_task",
        "trigger_task",
        "start_task"
    ):

        task = game.get(key)

        if task:
            try:
                task.cancel()
            except Exception:
                pass

    players = game["players"]

    if players:

        winner_id = players[0]

        winner_user = game[
            "users"
        ].get(
            winner_id
        )

        winner_name = get_account_name(
            winner_user
        )

        # إضافة النقاط
        add_points(
            winner_id,
            WIN_POINTS
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🏆 انتهت اللعبة! "
                f"الفائز هو: {winner_name}! 🎉\n\n"
                f"• ✨ {get_player_name(winner_user)} "
                f"— حصل على {WIN_POINTS} نقطة! ✨"
            )
        )

    else:

        await context.bot.send_message(
            chat_id=chat_id,
            text="🏁 انتهت طاولة الكذب."
        )

    active_liars_tables.pop(
        chat_id,
        None
    )

    unlock_big_game(
        chat_id,
        LIARS_TABLE_KEY
    )


# ============================================================
# Callback الرئيسي
# ============================================================

async def liars_table_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    data = query.data or ""

    if not data.startswith("lt:"):
        return

    parts = data.split(":")

    if len(parts) < 3:
        await query.answer()
        return

    action = parts[1]

    # ========================================================
    # اختيار كرت
    # ========================================================

    if action == "card":

        if len(parts) != 5:
            await query.answer()
            return

        try:

            chat_id = int(parts[2])
            player_id = int(parts[3])
            card_index = int(parts[4])

        except ValueError:

            await query.answer()
            return

        game = active_liars_tables.get(
            chat_id
        )

        if not game:
            await query.answer(
                "انتهت اللعبة."
            )
            return

        if game["finished"]:
            await query.answer(
                "انتهت اللعبة."
            )
            return

        if query.from_user.id != player_id:
            await query.answer(
                "هذه ليست كروتك.",
                show_alert=True
            )
            return

        if game["current_player"] != player_id:
            await query.answer(
                "ليس دورك الآن.",
                show_alert=True
            )
            return

        hand = game["hands"].get(
            player_id,
            []
        )

        if (
            card_index < 0
            or card_index >= len(hand)
        ):

            await query.answer(
                "هذا الكرت غير موجود."
            )
            return

        selected = game[
            "selected_cards"
        ].setdefault(
            player_id,
            []
        )

        # إزالة الاختيار
        if card_index in selected:

            selected.remove(
                card_index
            )

            await query.answer(
                "تم إلغاء اختيار الكرت."
            )

        else:

            if len(selected) >= 3:

                await query.answer(
                    "تقدر تختار 3 كروت كحد أقصى.",
                    show_alert=True
                )
                return

            selected.append(
                card_index
            )

            await query.answer(
                "تم اختيار الكرت."
            )

        keyboard = build_card_keyboard(
            chat_id,
            player_id
        )

        try:

            await query.edit_message_reply_markup(
                reply_markup=keyboard
            )

        except Exception:
            pass

        return

    # ========================================================
    # إرسال الكروت
    # ========================================================

    if action == "play":

        if len(parts) != 4:
            await query.answer()
            return

        try:

            chat_id = int(parts[2])
            player_id = int(parts[3])

        except ValueError:

            await query.answer()
            return

        game = active_liars_tables.get(
            chat_id
        )

        if not game:
            await query.answer(
                "انتهت اللعبة."
            )
            return

        if query.from_user.id != player_id:
            await query.answer(
                "هذا ليس دورك.",
                show_alert=True
            )
            return

        if game["current_player"] != player_id:

            await query.answer(
                "ليس دورك الآن.",
                show_alert=True
            )
            return

        selected = game[
            "selected_cards"
        ].get(
            player_id,
            []
        )

        if not selected:

            await query.answer(
                "اختر كرتًا واحدًا على الأقل.",
                show_alert=True
            )
            return

        if len(selected) > 3:

            await query.answer(
                "الحد الأقصى 3 كروت.",
                show_alert=True
            )
            return

        hand = game["hands"].get(
            player_id,
            []
        )

        cards = [
            hand[index]
            for index in selected
            if 0 <= index < len(hand)
        ]

        await query.answer(
            "تم إرسال الكروت! 🃏"
        )

        try:
            await query.edit_message_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        await play_cards(
            context,
            chat_id,
            player_id,
            cards
        )

        return

    # ========================================================
    # تحدي
    # ========================================================

    if action == "challenge":

        if len(parts) != 5:

            await query.answer()
            return

        try:

            chat_id = int(parts[2])
            accused_id = int(parts[3])
            challenger_id = int(parts[4])

        except ValueError:

            await query.answer()
            return

        game = active_liars_tables.get(
            chat_id
        )

        if not game:
            await query.answer(
                "انتهت اللعبة."
            )
            return

        if query.from_user.id != challenger_id:

            await query.answer(
                "هذا التحدي ليس لك.",
                show_alert=True
            )
            return

        await query.answer(
            "🚨 تم التحدي!"
        )

        try:
            await query.edit_message_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        await challenge_player(
            context,
            chat_id,
            challenger_id,
            accused_id
        )

        return

    # ========================================================
    # الزناد
    # ========================================================

    if action == "trigger":

        if len(parts) != 4:

            await query.answer()
            return

        try:

            chat_id = int(parts[2])
            player_id = int(parts[3])

        except ValueError:

            await query.answer()
            return

        game = active_liars_tables.get(
            chat_id
        )

        if not game:
            await query.answer(
                "انتهت اللعبة."
            )
            return

        if query.from_user.id != player_id:

            await query.answer(
                "هذا الزناد ليس لك.",
                show_alert=True
            )
            return

        if game["trigger_player"] != player_id:

            await query.answer(
                "ليس دورك لسحب الزناد.",
                show_alert=True
            )
            return

        await query.answer(
            "🔫 تسحب الزناد..."
        )

        try:
            await query.edit_message_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        await pull_trigger(
            context,
            chat_id,
            player_id
        )

        return

    await query.answer()


# ============================================================
# /start الخاص باللعبة
# ============================================================

async def liars_table_private_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not context.args:
        return

    payload = context.args[0]

    if not payload.startswith(
        "liars_table_"
    ):
        return

    try:

        chat_id = int(
            payload.replace(
                "liars_table_",
                "",
                1
            )
        )

    except ValueError:
        return

    game = active_liars_tables.get(
        chat_id
    )

    if not game:

        await update.message.reply_text(
            "❌ لا توجد طاولة كذب شغالة."
        )

        raise ApplicationHandlerStop

    player_id = update.effective_user.id

    if player_id not in game["players"]:

        await update.message.reply_text(
            "❌ أنت لست لاعبًا في هذه الطاولة."
        )

        raise ApplicationHandlerStop

    # إذا لم تبدأ اللعبة
    if not game["started"]:

        await update.message.reply_text(
            "⏳ اللعبة لم تبدأ بعد."
        )

        raise ApplicationHandlerStop

    # إذا كان الدور للاعب
    if game["current_player"] == player_id:

        game["selected_cards"][
            player_id
        ] = []

        await send_private_hand(
            context,
            chat_id,
            player_id,
            delay_message=False
        )

    else:

        await update.message.reply_text(
            "⏳ ليس دورك الآن.\n\n"
            "انتظر حتى ينتقل الدور إليك."
        )

    # مهم جدًا:
    # يمنع /start العادي من العمل بعدها
    raise ApplicationHandlerStop

from games.liars_table import (
    active_liars_tables,
    join_liars_table
)

if chat_id in active_liars_tables:

    await join_liars_table(
        update,
        context
    )

    return
