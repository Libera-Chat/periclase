import re
from typing import Pattern, Tuple


def _find_unescaped(s: str, c: int) -> int:
    i = 1
    while i < len(s):
        c2 = ord(s[i])
        i += 1
        if c2 == ord("\\"):
            i += 1
        elif c2 == c:
            return i
    else:
        return -1


def lex_pattern(pattern: str) -> Tuple[int, str, str, str]:
    pattern_delim_ = pattern[0]
    if pattern_delim_.isalnum():
        raise ValueError("pattern delimiter cannot be alphanumeric")
    pattern_delim = ord(pattern_delim_)

    regex_end = _find_unescaped(pattern, pattern_delim)
    if regex_end == -1:
        raise ValueError("unterminated regex")

    regex, pattern_flags = pattern[1 : regex_end - 1], pattern[regex_end:]
    pattern_flags, _, remaining = pattern_flags.partition(" ")
    return (pattern_delim, regex, pattern_flags, remaining)


def compile_pattern(pattern: str) -> Pattern:
    pattern_delim, regex, pattern_flags, _2 = lex_pattern(pattern)

    if pattern_delim in {ord("'"), ord('"')}:
        regex = re.escape(regex)

    regex_flags = 0
    for pattern_flag in pattern_flags:
        if pattern_flag == "i":
            regex_flags |= re.I
        elif pattern_flag == "^":
            regex = f"^{regex}"
        elif pattern_flag == "$":
            regex = f"{regex}$"
        else:
            raise ValueError(f"unknown pattern flag '{pattern_flag}'")

    return re.compile(regex, regex_flags)
