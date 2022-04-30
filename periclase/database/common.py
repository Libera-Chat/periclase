from dataclasses import dataclass
from asyncpg import Pool


@dataclass
class Table(object):
    pool: Pool
