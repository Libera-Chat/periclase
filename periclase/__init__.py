import traceback
from collections import OrderedDict
from dataclasses import dataclass
from random import randint
from re import compile as re_compile
from typing import Awaitable, Callable, Dict, List, Optional, Pattern, Sequence, Tuple

from irctokens import build, Hostmask, Line
from ircrobots import Bot as BaseBot
from ircrobots import Server as BaseServer

from ircstates.numerics import (
    RPL_WELCOME,
    RPL_YOUREOPER,
    RPL_RSACHALLENGE2,
    RPL_ENDOFRSACHALLENGE2,
)
from ircrobots.ircv3 import Capability
from ircrobots.matching import ANY, Response, SELF
from ircchallenge import Challenge

from .config import Config
from .database import Database
from .database.reject import Action, Reject
from .database.trigger import Trigger, TriggerAction
from .utils import compile_pattern, lex_pattern

CAP_OPER = Capability(None, "solanum.chat/oper")
CAP_REALHOST = Capability(None, "solanum.chat/realhost")

URL = "https://github.com/Libera-Chat/periclase"
OUR_CTCP = {"VERSION": f"periclase CTCP VERSION scanner ({URL})", "SOURCE": URL}

RE_VERSION = re_compile(r"^\x01VERSION (?P<version>.*?)\x01?$")
RE_NUHR = re_compile(r"^(?P<nick>[^!]+)![^@]+@\S+ .+$")


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

        self._triggers: OrderedDict[int, Tuple[Pattern, Trigger]] = OrderedDict()
        self._rejects: OrderedDict[int, Tuple[Pattern, Reject]] = OrderedDict()

    def set_throttle(self, rate: int, time: float):
        # turn off throttling
        pass

    async def handshake(self):
        # 8 digit random number
        alt_rand = str(randint(0, (10 ** 8) - 1)).zfill(8)
        self.params.alt_nicknames = [f"p{alt_rand}"]
        await super().handshake()

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

    def _sort_triggers(self) -> None:
        # sort by action; DISABLED, IGNORE, QUIETSCAN, SCAN
        self._triggers = OrderedDict(
            sorted(self._triggers.items(), key=lambda a: a[1][1].action)
        )

    async def _check_triggers(self, nuhr: str) -> Optional[Tuple[int, TriggerAction]]:
        for trigger_id, (trigger_pattern, trigger) in self._triggers.items():
            if trigger.action == TriggerAction.DISABLED or not trigger_pattern.search(
                nuhr
            ):
                continue
            return (trigger_id, trigger.action)
        return None

    async def _check_rejects(self, version: str) -> Optional[int]:
        for reject_id, (reject_pattern, _) in self._rejects.items():
            if reject_pattern.search(version):
                return reject_id
        else:
            return None

    async def line_read(self, line: Line):
        if line.command == RPL_WELCOME:
            triggers = await self._database.trigger.list()
            for trigger_id, trigger in triggers:
                self._triggers[trigger_id] = (
                    compile_pattern(trigger.pattern),
                    trigger,
                )
            self._sort_triggers()

            rejects = await self._database.reject.list()
            for reject_id, reject in rejects:
                self._rejects[reject_id] = (compile_pattern(reject.pattern), reject)

            oper_name, oper_file, oper_pass = self._config.oper
            await self._oper_up(oper_name, oper_file, oper_pass)

        elif line.command == RPL_YOUREOPER:
            # F far cliconn
            # c near cliconn
            await self.send(build("MODE", [self.nickname, "-s+s", "+Fc"]))

        elif p_cliconn := self._config.cliconn.search(line.format()):
            nickname = p_cliconn.group("nick")
            userhost = p_cliconn.group("userhost")
            realname = p_cliconn.group("real")
            nuhr = f"{nickname}!{userhost} {realname}"

            matched_trigger = await self._check_triggers(nuhr)
            if matched_trigger is not None:
                trigger_id, trigger_action = matched_trigger
                await self._log(f"TRIGGER:{trigger_action.name}: {trigger_id} {nuhr}")
                if trigger_action == TriggerAction.SCAN:
                    await self.send(build("NOTICE", [nickname, self._config.notify]))
                if trigger_action in {TriggerAction.SCAN, TriggerAction.QUIETSCAN}:
                    await self.send(build("PRIVMSG", [nickname, "\x01VERSION\x01"]))

        elif (
            line.command == "NOTICE"
            and line.source is not None
            and self.is_me(line.params[0])
            and (p_version := RE_VERSION.search(line.params[1])) is not None
            and line.tags is not None
            and not (ip := line.tags.get("solanum.chat/ip", "")) == ""
        ):
            # CTCP VERSION response
            version = p_version.group("version")

            matched_reject = await self._check_rejects(version)
            if matched_reject is not None:
                # GET THEY ASS
                _, reject = self._rejects[matched_reject]
                await self._log(
                    f"BAD: {matched_reject} {line.hostmask.nickname} {version}"
                )
                if reject.action == Action.BAN:
                    await self.send(build("KLINE", ["10", f"*@{ip}", reject.reason]))
                else:
                    await self.send(
                        build("NOTICE", [line.hostmask.nickname, reject.reason])
                    )
            else:
                await self._log(f"FINE: {line.hostmask.nickname} {version}")

        elif (
            line.command == "PRIVMSG"
            and line.source is not None
            and self.is_me(line.params[0])
            and line.params[1].startswith("\x01")
            and line.params[1].endswith("\x01")
        ):
            # CTCP request
            ctcp_type = line.params[1][1:-1].upper()
            if ctcp_type in OUR_CTCP:
                ctcp_response = OUR_CTCP[ctcp_type]
                await self.send(
                    build(
                        "NOTICE",
                        [
                            line.hostmask.nickname,
                            f"\x01{ctcp_type} {ctcp_response}\x01",
                        ],
                    )
                )

        elif (
            line.command == "PRIVMSG"
            and line.source is not None
            and not self.is_me(line.hostmask.nickname)
            and self.is_me(line.params[0])
        ):
            # private message
            await self._audit(f"[PV] <{line.source}> {line.params[1]}")
            cmd, _, args = line.params[1].partition(" ")
            await self.cmd(
                line.hostmask, line.hostmask.nickname, cmd.lower(), args, line.tags
            )

        elif (
            line.command == "PRIVMSG"
            and line.source is not None
            and not self.is_me(line.hostmask.nickname)
            and self.is_channel(line.params[0])
        ):
            # channel message
            first, _, rest = line.params[1].partition(" ")
            if first in {f"{self.nickname}{c}" for c in [":", ",", ""]} and rest:
                # highlight
                cmd, _, args = rest.partition(" ")
                await self.cmd(
                    line.hostmask, line.params[0], cmd.lower(), args, line.tags
                )

    async def cmd(
        self,
        who: Hostmask,
        target: str,
        command: str,
        args: str,
        tags: Optional[Dict[str, str]],
    ):

        if not tags or not (oper := tags.get("solanum.chat/oper", "")):
            return

        caller = Caller(who.nickname, str(who), oper)
        attrib = f"cmd_{command}"
        if not hasattr(self, attrib):
            return

        try:
            outs = await getattr(self, attrib)(caller, args)
        except ValueError as e:
            outs = [f"error: {str(e)}"]

        for out in outs:
            await self.send(build("NOTICE", [target, out]))

    async def cmd_scan(self, caller: Caller, sargs: str):
        nuhr = RE_NUHR.search(sargs)
        if nuhr is None:
            return ["please provide `nickname!username@hostname realname`"]

        matched_trigger = await self._check_triggers(sargs)
        if matched_trigger is None:
            return ["no trigger matched"]

        trigger_id, trigger_action = matched_trigger
        await self._log(f"TRIGGER:{trigger_action.name}: {trigger_id} {sargs}")
        await self.send(build("PRIVMSG", [nuhr.group("nick"), "\x01VERSION\x01"]))
        return []

    async def _cmd_reject_add(self, caller: Caller, sargs: str) -> Sequence[str]:
        if sargs.strip() == "":
            return ["please provide a reject pattern and reason"]

        # this may through ValueError, but up-stack will handle it nicely
        p_delim, pattern, p_flags, reason = lex_pattern(sargs)

        if reason.strip() == "":
            return ["please provide a reject reason"]

        # TODO: kinda strange that we totally re-create the pattern
        pattern = f"{chr(p_delim)}{pattern}{chr(p_delim)}{p_flags}"
        reject_id = await self._database.reject.add(
            pattern, caller.source, caller.oper, Action.BAN, reason
        )
        self._rejects[reject_id] = (
            compile_pattern(pattern),
            await self._database.reject.get(reject_id),
        )

        return [f"added reject {reject_id}"]

    async def _cmd_reject_get(self, caller: Caller, sargs: str) -> Sequence[str]:
        if sargs.strip() == "":
            return ["please provide a reject id"]
        elif not sargs.isdigit():
            return [f"'{sargs}' is not a valid reject id"]

        reject_id = int(sargs)
        if not reject_id in self._rejects:
            return ["unknown reject id"]

        _, reject = self._rejects[reject_id]
        return [
            reject.pattern,
            f"reason: {reject.reason}",
            f" since: {reject.ts.isoformat()}",
            f" adder: {reject.oper} ({reject.source})",
        ]

    async def _cmd_reject_remove(self, caller: Caller, sargs: str) -> Sequence[str]:
        if sargs.strip() == "":
            return ["please provide a reject id"]
        elif not sargs.isdigit():
            return [f"'{sargs}' is not a valid reject id"]

        reject_id = int(sargs)
        if not reject_id in self._rejects:
            return ["unknown reject id"]

        _, reject = self._rejects.pop(reject_id)
        await self._database.reject.remove(reject_id)
        return [f"removed reject {reject_id} ({reject.pattern})"]

    async def _cmd_reject_list(self, caller: Caller, sargs: str) -> Sequence[str]:
        if not self._rejects:
            return ["no rejects"]

        output: List[str] = []

        col_max = max(len(str(reject_id)) for reject_id in self._rejects.keys())
        for reject_id, (_, reject) in self._rejects.items():
            reject_id_s = str(reject_id).rjust(col_max)
            output.append(f"{reject_id_s}: {reject.pattern}")

        output.append(f"({len(output)} total)")
        return output

    async def cmd_reject(self, caller: Caller, sargs: str) -> Sequence[str]:
        subcmds: Dict[str, Callable[[Caller, str], Awaitable[Sequence[str]]]] = {
            "ADD": self._cmd_reject_add,
            "GET": self._cmd_reject_get,
            "REMOVE": self._cmd_reject_remove,
            "LIST": self._cmd_reject_list,
        }
        subcmd_keys = ", ".join(subcmds.keys())

        subcmd, _, sargs = sargs.partition(" ")
        if subcmd == "":
            return [f"please provide a subcommand ({subcmd_keys})"]

        subcmd = subcmd.upper()
        if not subcmd in subcmds:
            return [f"unknown subcommand '{subcmd}', expectected {subcmd_keys}"]

        subcmd_func = subcmds[subcmd]
        return await subcmd_func(caller, sargs)

    async def _cmd_trigger_add(self, caller: Caller, sargs: str) -> Sequence[str]:
        if (sargs := sargs.strip()) == "":
            return ["please provide a trigger pattern"]

        # this may through ValueError, but up-stack will handle it nicely
        p_delim, pattern, p_flags, action_name = lex_pattern(sargs)

        action_name, *_ = action_name.upper().split(" ", 1)
        action_names = sorted([a.name for a in TriggerAction])
        if not action_name in action_names:
            action_names_s = ", ".join(action_names)
            return [f"unknown action '{action_name}', expected {action_names_s}"]

        action = TriggerAction[action_name]

        # TODO: kinda strange that we totally re-create the pattern
        pattern = f"{chr(p_delim)}{pattern}{chr(p_delim)}{p_flags}"
        trigger_id = await self._database.trigger.add(
            pattern, caller.source, caller.oper, action
        )
        self._triggers[trigger_id] = (
            compile_pattern(pattern),
            await self._database.trigger.get(trigger_id),
        )
        self._sort_triggers()

        return [f"added trigger {trigger_id}"]

    async def _cmd_trigger_set(self, caller: Caller, sargs: str) -> Sequence[str]:
        trigger_id_s, _, action_name = sargs.partition(" ")
        if not trigger_id_s:
            return ["please provide a trigger id"]
        elif not trigger_id_s.isdigit():
            return [f"'{sargs}' is not a valid trigger id"]

        trigger_id = int(trigger_id_s)
        if not trigger_id in self._triggers:
            return ["unknown trigger id"]

        if (action_name := action_name.strip().upper()) == "":
            return ["please provide a trigger action"]

        action_names = sorted([a.name for a in TriggerAction])
        if not action_name in action_names:
            action_names_s = ", ".join(action_names)
            return [f"unknown action '{action_name}', expected {action_names_s}"]

        action = TriggerAction[action_name]
        _, trigger = self._triggers[trigger_id]
        if trigger.action == action:
            return [f"trigger {trigger_id} is already {action_name}"]

        await self._database.trigger.set(trigger_id, action)

        trigger.action = action
        self._sort_triggers()

        return [f"set triger {trigger_id} to {action_name}"]

    async def _cmd_trigger_get(self, caller: Caller, sargs: str) -> Sequence[str]:
        if sargs.strip() == "":
            return ["please provide a trigger id"]
        elif not sargs.isdigit():
            return [f"'{sargs}' is not a valid trigger id"]

        trigger_id = int(sargs)
        if not trigger_id in self._triggers:
            return ["unknown trigger id"]

        _, trigger = self._triggers[trigger_id]
        return [
            trigger.pattern,
            f"action: {trigger.action.name}",
            f" since: {trigger.ts.isoformat()}",
            f" adder: {trigger.oper} ({trigger.source})",
        ]

    async def _cmd_trigger_remove(self, caller: Caller, sargs: str) -> Sequence[str]:
        if (sargs := sargs.strip()) == "":
            return ["please provide a trigger id"]
        elif not sargs.isdigit():
            return [f"'{sargs}' is not a valid trigger id"]

        trigger_id = int(sargs)
        if not trigger_id in self._triggers:
            return ["unknown trigger id"]

        _, trigger = self._triggers.pop(trigger_id)
        await self._database.trigger.remove(trigger_id)
        return [f"removed trigger {trigger_id} ({trigger.pattern})"]

    # TODO: this is a lot of code duplication. what can we do about that?
    async def _cmd_trigger_list(self, caller: Caller, sargs: str) -> Sequence[str]:
        if not self._triggers:
            return ["no triggers"]

        output: List[str] = []

        col_max = max(len(str(trigger_id)) for trigger_id in self._triggers.keys())
        last_action: Optional[TriggerAction] = None
        for trigger_id, (_, trigger) in self._triggers.items():
            if last_action is None or not trigger.action == last_action:
                last_action = trigger.action
                output.append(f"{trigger.action.name}:")

            trigger_id_s = str(trigger_id).rjust(col_max)
            output.append(f"  {trigger_id_s}: {trigger.pattern}")

        output.append(f"({len(self._triggers)} total)")
        return output

    # TODO: this is a lot of code duplication. what can we do about that?
    async def cmd_trigger(self, caller: Caller, sargs: str) -> Sequence[str]:
        subcmds: Dict[str, Callable[[Caller, str], Awaitable[Sequence[str]]]] = {
            "ADD": self._cmd_trigger_add,
            "SET": self._cmd_trigger_set,
            "GET": self._cmd_trigger_get,
            "REMOVE": self._cmd_trigger_remove,
            "LIST": self._cmd_trigger_list,
        }
        subcmd_keys = ", ".join(subcmds.keys())

        subcmd, _, sargs = sargs.partition(" ")
        if subcmd == "":
            return [f"please provide a subcommand ({subcmd_keys})"]

        subcmd = subcmd.upper()
        if not subcmd in subcmds:
            return [f"unknown subcommand '{subcmd}', expectected {subcmd_keys}"]

        subcmd_func = subcmds[subcmd]
        return await subcmd_func(caller, sargs)


class Bot(BaseBot):
    def __init__(self, config: Config, database: Database):
        super().__init__()
        self._config = config
        self._database = database

    def create_server(self, name: str):
        return Server(self, name, self._config, self._database)
