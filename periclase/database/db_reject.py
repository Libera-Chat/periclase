from typing import List, Tuple
from .common import Table


class RejectTable(Table):
    async def list(self) -> List[Tuple[int, str, str]]:
        query = """
            SELECT id, pattern, reason
            FROM reject
        """

        async with self.pool.acquire() as conn:
            return await conn.fetch(query)

    async def add(self, pattern: str, source: str, oper: str, reason: str):
        query = """
            INSERT INTO reject (pattern, source, oper, reason, enabled, ts)
            VALUES ($1, $2, $3, $4, true, NOW()::TIMESTAMP)
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, pattern, source, oper, reason)

    async def disable(self, reject_id: int) -> None:
        query = """
            UPDATE reject
            SET enabled = false
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, reject_id)
