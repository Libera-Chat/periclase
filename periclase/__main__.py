import asyncio
from argparse import ArgumentParser

from ircrobots import ConnectionParams, SASLUserPass

from . import Bot
from .database import Database
from .config import Config, load as config_load


async def main(config: Config):
    database = await Database.connect(
        config.db_user, config.db_pass, config.db_host, config.db_name
    )

    bot = Bot(config, database)

    sasl_user, sasl_pass = config.sasl

    params = ConnectionParams.from_hoststring(config.nickname, config.server)
    params.username = config.username
    params.realname = config.realname
    params.password = config.password
    params.sasl = SASLUserPass(sasl_user, sasl_pass)
    params.autojoin = [config.log, config.audit]

    await bot.add_server("beryllia", params)
    await bot.run()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()

    config = config_load(args.config)
    asyncio.run(main(config))
