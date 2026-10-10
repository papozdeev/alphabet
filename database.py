import aiosqlite
from datetime import datetime
from config import DB_PATH, DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, ADMIN_IDS, ADMIN_USERNAMES

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_by INTEGER,
                reviewed_by_name TEXT,
                reviewed_at TEXT
            )
        ''')
        await db.commit()

        # Дефолтные настройки
        async with db.execute("SELECT value FROM settings WHERE key = 'group_name'") as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO settings (key, value) VALUES ('group_name', ?)", (DEFAULT_GROUP_NAME,))

        if DEFAULT_GROUP_ID is not None:
            async with db.execute("SELECT value FROM settings WHERE key = 'group_id'") as cursor:
                row = await cursor.fetchone()
                if not row:
                    await db.execute("INSERT INTO settings (key, value) VALUES ('group_id', ?)", (str(DEFAULT_GROUP_ID),))

        await db.commit()

async def get_setting(key: str, default: str = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (key, str(value)))
        await db.commit()

def is_superadmin(user_id: int, username: str | None) -> bool:
    if user_id in ADMIN_IDS:
        return True
    if username and username.lstrip('@').lower() in ADMIN_USERNAMES:
        return True
    return False

async def is_reviewer(user_id: int) -> bool:
    reviewer_id_str = await get_setting("reviewer_id")
    if reviewer_id_str and reviewer_id_str.isdigit() and int(reviewer_id_str) == user_id:
        return True
    return False

async def can_review(user_id: int, username: str | None) -> bool:
    return is_superadmin(user_id, username) or await is_reviewer(user_id)

async def record_superadmin_id_if_matching(user_id: int, username: str | None):
    if is_superadmin(user_id, username):
        await set_setting("superadmin_id", str(user_id))

async def create_application(user_id: int, username: str | None, full_name: str, reason: str | None) -> int:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO applications (user_id, username, full_name, reason, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        ''', (user_id, username, full_name, reason, now_str))
        await db.commit()
        return cursor.lastrowid

async def get_application(app_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)) as cursor:
            return await cursor.fetchone()

async def get_all_pending_applications():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM applications WHERE status = 'pending' ORDER BY id DESC") as cursor:
            return await cursor.fetchall()

async def get_pending_application_by_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM applications WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_application_status(app_id: int, status: str, reviewed_by: int, reviewed_by_name: str):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE applications
            SET status = ?, reviewed_by = ?, reviewed_by_name = ?, reviewed_at = ?
            WHERE id = ?
        ''', (status, reviewed_by, reviewed_by_name, now_str, app_id))
        await db.commit()

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM applications
        ''') as cursor:
            row = await cursor.fetchone()
            return {
                "total": row[0] or 0,
                "pending": row[1] or 0,
                "approved": row[2] or 0,
                "rejected": row[3] or 0
            }
