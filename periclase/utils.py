import re
from typing import Pattern


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


def compile_pattern(pattern: str) -> Pattern:
    pattern_delim = pattern[0]
    if pattern_delim.isalnum():
        raise ValueError("pattern delimiter cannot be alphanumeric")

    regex_end = _find_unescaped(pattern, ord(pattern_delim))
    if regex_end == -1:
        raise ValueError("unterminated regex")

    regex, pattern_flags = pattern[1 : regex_end - 1], pattern[regex_end:]

    regex_flags = 0
    for pattern_flag in pattern_flags:
        if pattern_flag == "i":
            regex_flags |= re.I
        else:
            raise ValueError(f"unknown pattern flag '{pattern_flag}'")

    return re.compile(regex, regex_flags)
