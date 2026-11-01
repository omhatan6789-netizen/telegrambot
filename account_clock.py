
import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pyrogram.errors import FloodWait

from music_call import get_music_client


ACCOUNT_ID = 6496915877
TIMEZONE = ZoneInfo("Asia/Riyadh")

_clock_task = None

# التعرف على الساعة القديمة سواء كانت بأرقام عادية أو صغيرة
CLOCK_PATTERN = re.compile(
    r"\s+⌁\s+"
    r"(?:[0-9]{1,2}:[0-9]{2}\s+(?:AM|PM)"
    r"|[⁰¹²³⁴⁵⁶⁷⁸⁹]{1,2}:[⁰¹²³⁴⁵⁶⁷⁸⁹]{2}\s+[ᴬᴾᴹ]+)"
    r"$"
)


def small_clock(text):
    numbers = str.maketrans(
        "0123456789",
        "⁰¹²³⁴⁵⁶⁷⁸⁹"
    )

    return (
        text.translate(numbers).replace(":", "ː")
        .replace("AM", "ᴬᴹ")
        .replace("PM", "ᴾᴹ")
    )


def get_base_name(name):
    """إزالة الساعة القديمة من الاسم مع الحفاظ على الاسم الأساسي."""
    return CLOCK_PATTERN.sub("", name).strip()


async def _clock_loop():
    client = get_music_client()

    if client is None:
        print("[CLOCK] Music account is not connected.")
        return

    me = await client.get_me()

    if me.id != ACCOUNT_ID:
        print(
            f"[CLOCK] Account ID mismatch: "
            f"expected {ACCOUNT_ID}, got {me.id}. Clock disabled."
        )
        return

    print("[CLOCK] Account verified. Clock started.")

    # تنظيف الساعات القديمة أو المكررة عند بداية التشغيل
    base_name = get_base_name(me.first_name)

    if base_name != me.first_name:
        await client.update_profile(first_name=base_name)
        print(f"[CLOCK] Old clock cleaned: {base_name}")

    while True:
        try:
            # قراءة الاسم الحالي حتى نلتقط أي تغيير يدوي
            me = await client.get_me()

            base_name = get_base_name(me.first_name)

            now = datetime.now(TIMEZONE)
            clock = small_clock(now.strftime("%I:%M %p"))

            new_name = f"{base_name} ⌁ {clock}"

            if me.first_name != new_name:
                await client.update_profile(
                    first_name=new_name
                )

                print(f"[CLOCK] Name updated: {new_name}")

            # الانتظار حتى بداية الدقيقة التالية
            now = datetime.now(TIMEZONE)

            seconds = (
                60 - now.second - now.microsecond / 1_000_000
            )

            await asyncio.sleep(max(1, seconds))

        except FloodWait as exc:
            print(f"[CLOCK] FloodWait: waiting {exc.value}s")
            await asyncio.sleep(exc.value)

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(f"[CLOCK] Update error: {exc}")
            await asyncio.sleep(60)


async def start_account_clock():
    global _clock_task

    if _clock_task and not _clock_task.done():
        return

    _clock_task = asyncio.create_task(_clock_loop())


async def shutdown_account_clock():
    global _clock_task

    if _clock_task:
        _clock_task.cancel()

        try:
            await _clock_task
        except asyncio.CancelledError:
            pass

        _clock_task = None

    print("[CLOCK] Account clock stopped.")
