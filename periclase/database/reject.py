from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple
from .common import Table


@dataclass
class Reject:
    pattern: str
    source: str
    oper: str
    reason: str
    ts: datetime


class RejectTable(Table):
    async def list(self) -> List[Tuple[int, Reject]]:
        query = """
            SELECT id, pattern, source, oper, reason, ts
            FROM reject
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [(id, Reject(*row)) for id, *row in rows]

    async def get(self, reject_id: int) -> Reject:
        query = """
            SELECT pattern, source, oper, reason, ts
            FROM reject
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, reject_id)
        return Reject(*row)

    async def add(self, pattern: str, source: str, oper: str, reason: str):
        query = """
            INSERT INTO reject (pattern, source, oper, reason, ts)
            VALUES ($1, $2, $3, $4, NOW()::TIMESTAMP)
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, pattern, source, oper, reason)

    async def remove(self, reject_id: int) -> None:
        query = """
            DELETE FROM reject
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, reject_id)
