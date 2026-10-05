"""自己紹介本文を持たず、サーバー・チャンネル・ユーザーIDだけを保存する。"""
import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        self.path = path

    async def initialize(self):
        await asyncio.to_thread(self._initialize)

    def _initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS introductions (
                guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, channel_id, user_id))''')

    async def mark(self, guild_id: int, channel_id: int, user_id: int):
        await asyncio.to_thread(self._mark, guild_id, channel_id, user_id)

    def _mark(self, *ids):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('INSERT OR IGNORE INTO introductions '
                       '(guild_id, channel_id, user_id) VALUES (?, ?, ?)', ids)

    async def has(self, guild_id: int, channel_id: int, user_id: int) -> bool:
        return await asyncio.to_thread(self._has, guild_id, channel_id, user_id)

    def _has(self, *ids):
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            return db.execute('SELECT 1 FROM introductions WHERE '
                              'guild_id=? AND channel_id=? AND user_id=?', ids).fetchone() is not None
