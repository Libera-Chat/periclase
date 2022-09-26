from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import List, Tuple
from .common import Table


class Action(IntEnum):
    BAN = 1
    WARN = 2


@dataclass
class Reject:
    pattern: str
    source: str
    oper: str
    action: Action
    reason: str
    ts: datetime


class RejectTable(Table):
    async def list(self) -> List[Tuple[int, Reject]]:
        query = """
            SELECT id, pattern, source, oper, action, reason, ts
            FROM reject
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [(id, Reject(*row)) for id, *row in rows]

    async def get(self, reject_id: int) -> Reject:
        query = """
            SELECT pattern, source, oper, action, reason, ts
            FROM reject
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, reject_id)

        return Reject(*row)

    async def add(
        self, pattern: str, source: str, oper: str, action: Action, reason: str
    ) -> int:
        query = """
            INSERT INTO reject (pattern, source, oper, action, reason, ts)
            VALUES ($1, $2, $3, $4, $5, NOW()::TIMESTAMP)
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                query, pattern, source, oper, action.value, reason
            )

    async def remove(self, reject_id: int) -> None:
        query = """
            DELETE FROM reject
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, reject_id)
