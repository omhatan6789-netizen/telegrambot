
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


logger = logging.getLogger("database.async")


# =========================================================
# إعدادات الاتصال
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL غير موجود في Environment Variables"
    )

DB_POOL_MIN = max(
    1,
    int(os.getenv("DB_POOL_MIN", "1"))
)

DB_POOL_MAX = max(
    DB_POOL_MIN,
    int(os.getenv("DB_POOL_MAX", "5"))
)

DB_POOL_TIMEOUT = max(
    3,
    float(os.getenv("DB_POOL_TIMEOUT", "10"))
)

DB_CONNECT_TIMEOUT = max(
    3,
    int(os.getenv("DB_CONNECT_TIMEOUT", "8"))
)

DB_SLOW_QUERY_SECONDS = max(
    0.1,
    float(os.getenv("DB_SLOW_QUERY_SECONDS", "0.5"))
)


# =========================================================
# مجموعة الاتصالات
# =========================================================

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError(
            "قاعدة البيانات غير مهيأة. "
            "شغّل init_db() أولاً."
        )

    return _pool


async def init_db() -> None:
    """
    تهيئة مجموعة الاتصالات مرة واحدة عند تشغيل البوت.
    """

    global _pool

    async with _pool_lock:

        if _pool is not None:
            return

        new_pool = AsyncConnectionPool(
            conninfo=DATABASE_URL,

            min_size=DB_POOL_MIN,
            max_size=DB_POOL_MAX,

            timeout=DB_POOL_TIMEOUT,
            max_waiting=20,

            max_lifetime=1800,
            max_idle=300,

            reconnect_timeout=30,
            num_workers=2,

            open=False,

            kwargs={
                "connect_timeout": DB_CONNECT_TIMEOUT,
                "application_name": "nawaf-telegram-bot",
                "prepare_threshold": None,
            },
        )

        try:
            await new_pool.open(
                wait=True,
                timeout=DB_POOL_TIMEOUT,
            )

            async with new_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()

            _pool = new_pool

            logger.info(
                "تم تشغيل Async PostgreSQL Pool "
                "(min=%s, max=%s)",
                DB_POOL_MIN,
                DB_POOL_MAX,
            )

        except Exception:
            await new_pool.close()
            raise


# =========================================================
# إغلاق الاتصالات
# =========================================================

async def close_db() -> None:
    global _pool

    async with _pool_lock:

        if _pool is None:
            return

        current_pool = _pool
        _pool = None

        await current_pool.close()

        logger.info(
            "تم إغلاق مجموعة اتصالات قاعدة البيانات"
        )


# =========================================================
# الاتصال
# =========================================================

@asynccontextmanager
async def connection():
    """
    استخدام:
        async with connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(...)
    """

    pool = get_pool()

    async with pool.connection() as conn:
        yield conn


# =========================================================
# تنفيذ استعلام
# =========================================================

async def execute(query: str, params=None) -> int:
    started = time.perf_counter()

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rowcount = cur.rowcount

    _log_slow_query(query, started)

    return rowcount


# =========================================================
# جلب سجل واحد
# =========================================================

async def fetch_one(query: str, params=None):
    started = time.perf_counter()

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            result = await cur.fetchone()

    _log_slow_query(query, started)

    return result


# =========================================================
# جلب جميع السجلات
# =========================================================

async def fetch_all(query: str, params=None):
    started = time.perf_counter()

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            result = await cur.fetchall()

    _log_slow_query(query, started)

    return result


# =========================================================
# تنفيذ جماعي
# =========================================================

async def execute_many(query: str, params_seq) -> None:
    started = time.perf_counter()

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                query,
                params_seq,
            )

    _log_slow_query(query, started)


# =========================================================
# فحص صحة الاتصال
# =========================================================

async def health_check() -> dict:
    started = time.perf_counter()

    try:
        result = await fetch_one("SELECT 1")

        return {
            "ok": result is not None,
            "latency_ms": round(
                (time.perf_counter() - started) * 1000,
                2,
            ),
        }

    except Exception as exc:
        logger.exception(
            "فشل فحص قاعدة البيانات"
        )

        return {
            "ok": False,
            "error": str(exc),
        }


# =========================================================
# إحصائيات مجموعة الاتصالات
# =========================================================

def pool_stats() -> dict:
    pool = get_pool()

    return {
        "pool_min": DB_POOL_MIN,
        "pool_max": DB_POOL_MAX,
        "pool_size": pool.get_stats().get(
            "pool_size",
            0,
        ),
        "pool_available": pool.get_stats().get(
            "pool_available",
            0,
        ),
        "requests_waiting": pool.get_stats().get(
            "requests_waiting",
            0,
        ),
    }


# =========================================================
# تسجيل الاستعلامات البطيئة
# =========================================================

def _log_slow_query(query: str, started: float) -> None:
    elapsed = time.perf_counter() - started

    if elapsed < DB_SLOW_QUERY_SECONDS:
        return

    preview = " ".join(
        str(query).split()
    )[:180]

    logger.warning(
        "استعلام PostgreSQL بطيء: %.3fs | %s",
        elapsed,
        preview,
    )
