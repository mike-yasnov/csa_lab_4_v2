from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int


KEYWORDS = {"func", "int", "long", "string", "char", "while", "true", "if", "else", "break", "print", "printInt"}


def tokenize(src: str) -> Iterator[Token]:
    i = 0
    line = 1
    col = 1

    def emit(kind: str, value: str):
        nonlocal line, col
        tok = Token(kind, value, line, col)
        return tok

    while i < len(src):
        ch = src[i]
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if ch == "/" and i + 1 < len(src) and src[i + 1] == "/":
            # comment till EOL
            while i < len(src) and src[i] != "\n":
                i += 1
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < len(src) and (src[j].isalnum() or src[j] == "_"):
                j += 1
            val = src[i:j]
            kind = "KW" if val in KEYWORDS else "ID"
            yield emit(kind, val)
            col += j - i
            i = j
            continue
        if ch.isdigit():
            j = i + 1
            while j < len(src) and src[j].isdigit():
                j += 1
            yield emit("INT", src[i:j])
            col += j - i
            i = j
            continue
        if ch == '"':
            j = i + 1
            buf = []
            while j < len(src) and src[j] != '"':
                buf.append(src[j])
                j += 1
            j += 1
            yield emit("STR", "".join(buf))
            col += j - i
            i = j
            continue
        # two-char operators
        if i + 1 < len(src):
            two = src[i : i + 2]
            if two in {"<=", ">=", "==", "!="}:
                yield emit(two, two)
                i += 2
                col += 2
                continue
        # single char tokens
        if ch in "{}();,=+-*/<>!":
            yield emit(ch, ch)
            i += 1
            col += 1
            continue
        if ch in "[]":
            yield emit(ch, ch)
            i += 1
            col += 1
            continue
        raise SyntaxError(f"Unexpected char {ch!r} at {line}:{col}")
