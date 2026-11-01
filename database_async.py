
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


logger = logging.getLogger("database")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "5"))

DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "10"))
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "8"))

DB_SLOW_QUERY_SECONDS = float(
    os.getenv("DB_SLOW_QUERY_SECONDS", "0.5")
)

DB_APPLICATION_NAME = os.getenv(
    "DB_APPLICATION_NAME",
    "nawaf-telegram-bot"
)

_pool: Optional[AsyncConnectionPool] = None
_pool_lock = asyncio.Lock()


def _validate_settings():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL غير موجود في Environment Variables")

    if DB_POOL_MIN < 0:
        raise ValueError("DB_POOL_MIN يجب أن يكون صفرًا أو أكبر")

    if DB_POOL_MAX < 1:
        raise ValueError("DB_POOL_MAX يجب أن يكون أكبر من صفر")

    if DB_POOL_MIN > DB_POOL_MAX:
        raise ValueError("DB_POOL_MIN لا يمكن أن يكون أكبر من DB_POOL_MAX")


async def init_db():
    """
    تشغيل مجمع اتصالات قاعدة البيانات.
    يستدعى مرة واحدة عند بدء البوت.
    """

    global _pool

    if _pool is not None:
        return

    async with _pool_lock:

        if _pool is not None:
            return

        _validate_settings()

        pool = AsyncConnectionPool(
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
                "application_name": DB_APPLICATION_NAME,
                "row_factory": dict_row,
                "prepare_threshold": None,
            },
        )

        try:
            await pool.open(
                wait=True,
                timeout=DB_POOL_TIMEOUT,
            )

            async with pool.connection() as conn:
                await conn.execute("SELECT 1")

            _pool = pool

            logger.info(
                "Database pool connected | min=%s max=%s",
                DB_POOL_MIN,
                DB_POOL_MAX,
            )

        except Exception:
            await pool.close()
            raise


async def close_db():
    """
    إغلاق جميع اتصالات قاعدة البيانات.
    يستدعى عند إيقاف البوت.
    """

    global _pool

    async with _pool_lock:

        pool = _pool
        _pool = None

        if pool is not None:
            await pool.close()
            logger.info("Database pool closed")


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError(
            "قاعدة البيانات غير مهيأة. استدعِ init_db() أولًا."
        )

    return _pool


@asynccontextmanager
async def connection():
    """
    الحصول على اتصال غير متزامن.

    يحفظ التغييرات تلقائيًا عند النجاح،
    ويتراجع عنها عند حدوث استثناء.
    """

    pool = get_pool()

    async with pool.connection() as conn:
        yield conn


@asynccontextmanager
async def transaction():
    """
    معاملة قاعدة بيانات مستقلة.
    """

    async with connection() as conn:
        async with conn.transaction():
            yield conn


async def execute(
    query: str,
    params: Optional[tuple] = None,
) -> int:
    """
    تنفيذ INSERT / UPDATE / DELETE.
    يرجع عدد الصفوف المتأثرة.
    """

    started = time.perf_counter()

    async with connection() as conn:
        cursor = await conn.execute(query, params or ())
        rowcount = cursor.rowcount

    _log_slow_query(query, started)

    return rowcount


async def fetch_one(
    query: str,
    params: Optional[tuple] = None,
) -> Optional[dict]:
    """
    جلب صف واحد على شكل dict.
    """

    started = time.perf_counter()

    async with connection() as conn:
        cursor = await conn.execute(query, params or ())
        result = await cursor.fetchone()

    _log_slow_query(query, started)

    return result


async def fetch_all(
    query: str,
    params: Optional[tuple] = None,
) -> list:
    """
    جلب جميع الصفوف على شكل قائمة من dict.
    """

    started = time.perf_counter()

    async with connection() as conn:
        cursor = await conn.execute(query, params or ())
        result = await cursor.fetchall()

    _log_slow_query(query, started)

    return result


async def fetch_value(
    query: str,
    params: Optional[tuple] = None,
    default: Any = None,
) -> Any:
    """
    جلب أول قيمة من أول صف.
    """

    started = time.perf_counter()

    async with connection() as conn:
        cursor = await conn.execute(query, params or ())
        row = await cursor.fetchone()

    _log_slow_query(query, started)

    if row is None:
        return default

    return next(iter(row.values()), default)


async def execute_many(
    query: str,
    params_list: list,
) -> int:
    """
    تنفيذ استعلام على مجموعة بيانات.
    """

    if not params_list:
        return 0

    started = time.perf_counter()

    async with connection() as conn:
        cursor = await conn.cursor()
        await cursor.executemany(query, params_list)
        rowcount = cursor.rowcount
        await cursor.close()

    _log_slow_query(query, started)

    return rowcount


async def health_check() -> bool:
    """
    اختبار الاتصال بقاعدة البيانات.
    """

    try:
        result = await fetch_value("SELECT 1", default=0)
        return result == 1

    except Exception:
        logger.exception("Database health check failed")
        return False


def pool_stats() -> dict:
    """
    إحصائيات مجمع الاتصالات.
    """

    pool = get_pool()
    stats = pool.get_stats()

    return {
        "pool_min": DB_POOL_MIN,
        "pool_max": DB_POOL_MAX,
        "pool_size": stats.get("pool_size", 0),
        "pool_available": stats.get("pool_available", 0),
        "requests_waiting": stats.get("requests_waiting", 0),
        "requests_queued": stats.get("requests_queued", 0),
        "requests_wait_ms": stats.get("requests_wait_ms", 0),
        "connections_num": stats.get("connections_num", 0),
        "connections_errors": stats.get("connections_errors", 0),
    }


def _log_slow_query(query: str, started: float):
    elapsed = time.perf_counter() - started

    if elapsed >= DB_SLOW_QUERY_SECONDS:
        compact_query = " ".join(query.split())

        logger.warning(
            "Slow database query | %.3fs | %s",
            elapsed,
            compact_query[:300],
        )
