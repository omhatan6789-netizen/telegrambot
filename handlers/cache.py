import asyncio
from datetime import datetime

from database import connect


_user_cache = {}
_cache_lock = None


def _get_cache_lock():
    """
    إنشاء Lock واحد للكاش عند الحاجة.
    """
    global _cache_lock

    if _cache_lock is None:
        _cache_lock = asyncio.Lock()

    return _cache_lock


def default_joined_date():
    return datetime.now().strftime("%Y/%m/%d")


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


def has_user_cache(user_id):
    return user_id in _user_cache


def get_cached_user(user_id):
    return _user_cache.get(user_id)


def set_cached_user(user_id, data):
    _user_cache[user_id] = data
    return data


def update_cached_user(
    user_id,
    **values
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data.update(values)

    return data


def increment_cached_messages(
    user_id,
    amount=1,
    username=None,
    first_name=None
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(
            user_id,
            username,
            first_name or ""
        )
        _user_cache[user_id] = data

    data["messages"] = (
        data.get("messages", 0)
        + amount
    )

    if username is not None:
        data["username"] = username

    if first_name is not None:
        data["first_name"] = first_name

    return data


def set_cached_points(
    user_id,
    points
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["points"] = points or 0

    return data


def increment_cached_points(
    user_id,
    amount
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["points"] = (
        data.get("points", 0)
        + amount
    )

    return data


def set_cached_rank(
    user_id,
    rank
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["rank"] = rank or "عضو"

    return data


def set_cached_messages(
    user_id,
    messages
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(user_id)
        _user_cache[user_id] = data

    data["messages"] = messages or 0

    return data


def update_cached_profile(
    user_id,
    username=None,
    first_name=None
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(
            user_id,
            username,
            first_name or ""
        )
        _user_cache[user_id] = data

    if username is not None:
        data["username"] = username

    if first_name is not None:
        data["first_name"] = first_name

    return data


def load_user_from_db(user_id):
    conn = connect()
    cur = None

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

        if not row:
            return None

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

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass

        conn.close()


def get_user_data_sync(user_id):
    cached = _user_cache.get(user_id)

    if cached is not None:
        return cached

    return load_user_from_db(user_id)


async def get_user_data(user_id):
    cached = _user_cache.get(user_id)

    if cached is not None:
        return cached

    return await asyncio.to_thread(
        load_user_from_db,
        user_id
    )


def ensure_cached_user(
    user_id,
    username=None,
    first_name=""
):
    cached = _user_cache.get(user_id)

    if cached is not None:

        if username is not None:
            cached["username"] = username

        if first_name is not None:
            cached["first_name"] = first_name

        return cached

    data = load_user_from_db(user_id)

    if data is not None:

        if username is not None:
            data["username"] = username

        if first_name is not None:
            data["first_name"] = first_name

        return data

    return set_cached_user(
        user_id,
        create_default_user_data(
            user_id,
            username,
            first_name
        )
    )


def ensure_user_loaded_sync(
    user_id,
    username=None,
    first_name=""
):
    cached = _user_cache.get(user_id)

    if cached is not None:

        if username is not None:
            cached["username"] = username

        if first_name is not None:
            cached["first_name"] = first_name

        return cached

    data = load_user_from_db(user_id)

    if data is not None:

        if username is not None:
            data["username"] = username

        if first_name is not None:
            data["first_name"] = first_name

        return data

    return ensure_cached_user(
        user_id,
        username,
        first_name
    )


async def ensure_user_loaded(
    user_id,
    username=None,
    first_name=""
):
    cached = _user_cache.get(user_id)

    if cached is not None:

        if username is not None:
            cached["username"] = username

        if first_name is not None:
            cached["first_name"] = first_name

        return cached

    data = await asyncio.to_thread(
        load_user_from_db,
        user_id
    )

    if data is not None:

        if username is not None:
            data["username"] = username

        if first_name is not None:
            data["first_name"] = first_name

        return data

    return ensure_cached_user(
        user_id,
        username,
        first_name
    )


def clear_cached_user(user_id):
    _user_cache.pop(
        user_id,
        None
    )


def clear_all_user_cache():
    _user_cache.clear()


def get_cache_size():
    return len(_user_cache)


def get_user_cache_lock():
    return _get_cache_lock()


def update_cached_user_data(
    user_id,
    messages=None,
    rank=None,
    points=None,
    username=None,
    first_name=None,
    joined_date=None
):
    data = _user_cache.get(user_id)

    if data is None:
        data = load_user_from_db(user_id)

    if data is None:
        data = create_default_user_data(
            user_id,
            username,
            first_name or ""
        )
        _user_cache[user_id] = data

    if messages is not None:
        data["messages"] = messages

    if rank is not None:
        data["rank"] = rank

    if points is not None:
        data["points"] = points

    if username is not None:
        data["username"] = username

    if first_name is not None:
        data["first_name"] = first_name

    if joined_date is not None:
        data["joined_date"] = joined_date

    return data
