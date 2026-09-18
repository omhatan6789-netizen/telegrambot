import asyncio
from datetime import datetime

from database import connect


# =========================================================
# الكاش المركزي للمستخدمين
# =========================================================

_user_cache = {}


# =========================================================
# قفل تحميل المستخدمين
# =========================================================

_cache_lock = None


def _get_cache_lock():
    global _cache_lock

    if _cache_lock is None:
        _cache_lock = asyncio.Lock()

    return _cache_lock


# =========================================================
# التاريخ الافتراضي
# =========================================================

def default_joined_date():
    return datetime.now().strftime("%Y/%m/%d")


# =========================================================
# إنشاء بيانات افتراضية
# =========================================================

def create_default_user_data(
    user_id,
    username=None,
    first_name=""
):
    return {
        "user_id": user_id,
        "messages": 0,
        "rank": "عضو",
        "joined_date": default_joined_date(),
        "username": username,
        "first_name": first_name or "",
        "points": 0,
    }


# =========================================================
# هل المستخدم موجود في الكاش؟
# =========================================================

def has_user_cache(user_id):
    return user_id in _user_cache


# =========================================================
# جلب بيانات من الكاش فقط
# =========================================================

def get_cached_user(user_id):
    return _user_cache.get(user_id)


# =========================================================
# حفظ بيانات المستخدم في الكاش
# =========================================================

def set_cached_user(user_id, data):
    _user_cache[user_id] = data
    return data


# =========================================================
# تحديث جزء من بيانات المستخدم
# =========================================================

def update_cached_user(user_id, **values):

    data = _user_cache.get(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data.update(values)

    return data


# =========================================================
# تحديث الرسائل في الكاش
# =========================================================

def increment_cached_messages(
    user_id,
    amount=1,
    username=None,
    first_name=None
):

    data = _user_cache.get(user_id)

    if data is None:
        data = create_default_user_data(
            user_id,
            username,
            first_name or ""
        )
        _user_cache[user_id] = data

    data["messages"] = (
        data.get("messages", 0) + amount
    )

    if username is not None:
        data["username"] = username

    if first_name is not None:
        data["first_name"] = first_name

    return data


# =========================================================
# تحديث النقاط في الكاش
# =========================================================

def set_cached_points(
    user_id,
    points
):

    data = _user_cache.get(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["points"] = points

    return data


def increment_cached_points(
    user_id,
    amount
):

    data = _user_cache.get(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["points"] = (
        data.get("points", 0) + amount
    )

    return data


# =========================================================
# تحديث الرتبة في الكاش
# =========================================================

def set_cached_rank(
    user_id,
    rank
):

    data = _user_cache.get(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["rank"] = rank

    return data


# =========================================================
# تحميل المستخدم من قاعدة البيانات
# =========================================================

def load_user_from_db(user_id):

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                u.user_id,
                u.messages,
                u.rank,
                u.joined_date,
                u.username,
                u.first_name,
                COALESCE(p.points, 0)
            FROM users u
            LEFT JOIN points p
                ON p.user_id = u.user_id
            WHERE u.user_id = ?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        if row:

            data = {
                "user_id": row[0],
                "messages": row[1] or 0,
                "rank": row[2] or "عضو",
                "joined_date": (
                    row[3]
                    or "غير معروف"
                ),
                "username": row[4],
                "first_name": row[5] or "",
                "points": row[6] or 0,
            }

            _user_cache[user_id] = data

            return data

        return None

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# جلب بيانات المستخدم
# =========================================================

def get_user_data_sync(user_id):

    cached = _user_cache.get(user_id)

    if cached is not None:
        return cached

    return load_user_from_db(user_id)


# =========================================================
# جلب بيانات المستخدم بشكل Async
#
# قاعدة البيانات تعمل خارج event loop
# =========================================================

async def get_user_data(user_id):

    cached = _user_cache.get(user_id)

    if cached is not None:
        return cached

    return await asyncio.to_thread(
        load_user_from_db,
        user_id
    )


# =========================================================
# إنشاء مستخدم في الكاش
# =========================================================

def ensure_cached_user(
    user_id,
    username=None,
    first_name=""
):

    cached = _user_cache.get(user_id)

    if cached is not None:
        return cached

    return set_cached_user(
        user_id,
        create_default_user_data(
            user_id,
            username,
            first_name
        )
    )


# =========================================================
# حذف كاش مستخدم
# =========================================================

def clear_cached_user(user_id):
    _user_cache.pop(user_id, None)


# =========================================================
# مسح الكاش بالكامل
# =========================================================

def clear_all_user_cache():
    _user_cache.clear()
