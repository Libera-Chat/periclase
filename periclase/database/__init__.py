import asyncpg
from typing import Optional

from .db_trigger import TriggerTable, TriggerAction
from .db_reject import RejectTable


class Database(object):
    def __init__(self, pool: asyncpg.Pool):
        self.trigger = TriggerTable(pool)
        self.reject = RejectTable(pool)

    @classmethod
    async def connect(
        self,
        username: str,
        password: Optional[str],
        hostname: Optional[str],
        db_name: str,
    ):

        pool = await asyncpg.create_pool(
            user=username, password=password, host=hostname, database=db_name
        )
        return Database(pool)
