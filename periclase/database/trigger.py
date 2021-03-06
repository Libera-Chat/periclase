from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import List, Tuple
from .common import Table


class TriggerAction(IntEnum):
    DISABLED = 1
    IGNORE = 2
    QUIETSCAN = 3
    SCAN = 4


@dataclass
class Trigger:
    pattern: str
    source: str
    oper: str
    action: TriggerAction
    ts: datetime


class TriggerTable(Table):
    async def list(self) -> List[Tuple[int, Trigger]]:
        query = """
            SELECT id, pattern, source, oper, action, ts
            FROM trigger
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)

        out: List[Tuple[int, Trigger]] = []
        for id, pattern, source, oper, action, ts in rows:
            out.append((id, Trigger(pattern, source, oper, TriggerAction(action), ts)))
        return out

    async def get(self, trigger_id) -> Trigger:
        query = """
            SELECT pattern, source, oper, action, ts
            FROM trigger
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, trigger_id)

        pattern, source, oper, action, ts = row
        return Trigger(pattern, source, oper, TriggerAction(action), ts)

    async def add(
        self, pattern: str, source: str, oper: str, action: TriggerAction
    ) -> int:
        query = """
            INSERT INTO trigger (pattern, source, oper, action, ts)
            VALUES ($1, $2, $3, $4, NOW()::TIMESTAMP)
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, pattern, source, oper, action)

    async def set(self, trigger_id: int, action: TriggerAction) -> None:
        query = """
            UPDATE trigger
            SET action = $2
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, trigger_id, action)

    async def remove(self, trigger_id: int) -> None:
        query = """
            DELETE FROM trigger
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.fetchrow(query, trigger_id)
