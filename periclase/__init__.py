import asyncio, ipaddress, time, traceback
from dataclasses import dataclass
from re import compile as re_compile
from typing import Dict, Optional, Pattern, Tuple

from irctokens import build, Hostmask, Line
from ircrobots import Bot as BaseBot
from ircrobots import Server as BaseServer

from ircstates.numerics import *
from ircrobots.ircv3 import Capability
from ircrobots.matching import ANY, Folded, Response, SELF
from ircchallenge import Challenge

from .config import Config
from .database import Database

CAP_OPER = Capability(None, "solanum.chat/oper")
CAP_REALHOST = Capability(None, "solanum.chat/realhost")

RE_CLICONN = re_compile(
    r"^:[^!]+ NOTICE \* :\*{3} Notice -- Client connecting: (?P<nick>\S+) \((?P<userhost>[^)]+)\) \S+ \S+ \S+ \[(?P<real>.*)\]$"
)
RE_VERSION = re_compile(r"^\x01VERSION (?P<version>.*?)\x01?$")


@dataclass
class Caller:
    nick: str
    source: str
    oper: str


class Server(BaseServer):
    def __init__(self, bot: BaseBot, name: str, config: Config, database: Database):
        super().__init__(bot, name)
        self._config = config
        self._database = database

        self.desired_caps.add(CAP_OPER)
        self.desired_caps.add(CAP_REALHOST)

        self._triggers: Dict[int, Pattern] = {}
        self._rejects: Dict[int, Tuple[Pattern, str]] = {}

    def set_throttle(self, rate: int, time: float):
        # turn off throttling
        pass

    def line_preread(self, line: Line):
        print(f"< {line.format()}")

    def line_presend(self, line: Line):
        print(f"> {line.format()}")

    async def _log(self, text: str):
        await self.send(build("PRIVMSG", [self._config.log, text]))

    async def _audit(self, text: str):
        await self.send(build("NOTICE", [self._config.audit, text]))

    async def _oper_up(self, oper_name: str, oper_file: str, oper_pass: str):

        try:
            challenge = Challenge(keyfile=oper_file, password=oper_pass)
        except Exception:
            traceback.print_exc()
        else:
            await self.send(build("CHALLENGE", [oper_name]))
            challenge_text = Response(RPL_RSACHALLENGE2, [SELF, ANY])
            challenge_stop = Response(RPL_ENDOFRSACHALLENGE2, [SELF])
            #:lithium.libera.chat 740 sandcat :foobarbazmeow
            #:lithium.libera.chat 741 sandcat :End of CHALLENGE

            while True:
                challenge_line = await self.wait_for({challenge_text, challenge_stop})
                if challenge_line.command == RPL_RSACHALLENGE2:
                    challenge.push(challenge_line.params[1])
                else:
                    retort = challenge.finalise()
                    await self.send(build("CHALLENGE", [f"+{retort}"]))
                    break

    async def _check_trigger(self, nuhr: str) -> Optional[int]:
        for trigger_id, pattern in self._triggers.items():
            if pattern.search(nuhr):
                return trigger_id
        else:
            return None

    async def _check_reject(self, version: str) -> Optional[int]:
        for reject_id, (pattern, _) in self._rejects.items():
            if pattern.search(version):
                return reject_id
        else:
            return None

    async def line_read(self, line: Line):
        now = time.monotonic()

        if line.command == RPL_WELCOME:
            triggers = await self._database.trigger.list()
            for trigger_id, trigger_pattern in triggers:
                self._triggers[trigger_id] = re_compile(trigger_pattern)

            rejects = await self._database.reject.list()
            for reject_id, reject_pattern, reject_reason in rejects:
                self._rejects[reject_id] = (re_compile(reject_pattern), reject_reason)

            await self.send(build("MODE", [self.nickname, "+g"]))
            oper_name, oper_file, oper_pass = self._config.oper
            await self._oper_up(oper_name, oper_file, oper_pass)

        elif line.command == RPL_YOUREOPER:
            # F far cliconn
            # c near cliconn
            await self.send(build("MODE", [self.nickname, "-s+s", "+Fc"]))

        elif p_cliconn := RE_CLICONN.search(line.format()):
            nickname = p_cliconn.group("nick")
            userhost = p_cliconn.group("userhost")
            realname = p_cliconn.group("real")
            nuhr = f"{nickname}!{userhost} {realname}"

            matched_trigger = await self._check_trigger(nuhr)
            if matched_trigger is not None:
                await self._log(f"TRIGGER:{matched_trigger}: want to CTCP {nuhr}")
                await self.send(build("PRIVMSG", [nickname, "\x01VERSION\x01"]))

        elif (
            line.command == "NOTICE"
            and line.source is not None
            and self.is_me(line.params[0])
            and (p_version := RE_VERSION.search(line.params[1])) is not None
            and line.tags is not None
            and not (ip := line.tags.get("solanum.chat/ip", "")) == ""
        ):
            version = p_version.group("version")

            matched_reject = await self._check_reject(version)
            if matched_reject is not None:
                # GET THEY ASS
                _, reason = self._rejects[matched_reject]
                await self._log(f"BAD: {line.source} for CTCP reject {matched_reject}")
                await self.send(build("KLINE", ["10", f"*@{ip}", reason]))

        elif (
            line.command == "PRIVMSG"
            and line.source is not None
            and not self.is_me(line.hostmask.nickname)
        ):

            me = self.nickname
            who = line.hostmask

            first, _, rest = line.params[1].partition(" ")
            if self.is_me(line.params[0]):
                # private message
                await self._audit(f"[PV] <{line.source}> {line.params[1]}")
                await self.cmd(who, first.lower(), rest, line.tags)

    async def cmd(
        self,
        who: Hostmask,
        command: str,
        args: str,
        tags: Optional[Dict[str, str]],
    ):

        if tags and (oper := tags.get("solanum.chat/oper", "")):
            caller = Caller(who.nickname, str(who), oper)
            attrib = f"cmd_{command}"
            if hasattr(self, attrib):
                outs = await getattr(self, attrib)(caller, args)
                for out in outs:
                    await self.send(build("NOTICE", [who.nickname, out]))


class Bot(BaseBot):
    def __init__(self, config: Config, database: Database):
        super().__init__()
        self._config = config
        self._database = database

    def create_server(self, name: str):
        return Server(self, name, self._config, self._database)
