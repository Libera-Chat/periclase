from typing import List, Tuple
from .common import Table


class TriggerTable(Table):
    async def list(self) -> List[Tuple[int, str]]:
        query = """
            SELECT id, pattern
            FROM trigger
        """

        async with self.pool.acquire() as conn:
            return await conn.fetch(query)

    async def add(self, pattern: str, source: str, oper: str) -> int:
        query = """
            INSERT INTO trigger (pattern, source, oper, ts)
            VALUES ($1, $2, $3, NOW()::TIMESTAMP)
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, pattern, source, oper)

    async def remove(self, id: int) -> None:
        query = """
            DELETE FROM trigger
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.fetchrow(query, id)
