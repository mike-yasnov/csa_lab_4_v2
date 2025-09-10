from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Opcode(IntEnum):
    # Stack/memory
    NOP = 0x00
    PUSHI = 0x01  # push immediate (signed 24-bit)
    LOAD = 0x02  # pop addr -> push mem[addr]
    STORE = 0x03  # pop value; pop addr -> mem[addr] = value
    DUP = 0x04
    DROP = 0x05
    SWAP = 0x06

    # ALU
    ADD = 0x10
    SUB = 0x11
    MUL = 0x12
    DIV = 0x13

    # Compare -> boolean (1/0)
    LE = 0x41  # pop b; pop a; push(1 if a <= b else 0)

    # Control flow
    JMP = 0x20
    JZ = 0x21  # pop cond; if cond == 0 then jump arg else PC++
    CALL = 0x22
    RET = 0x23
    IRET = 0x24
    EI = 0x25
    DI = 0x26

    # IO (port-mapped)
    IN = 0x30  # arg = port id; push value from port buffer
    OUT = 0x31  # arg = port id; pop value -> port buffer

    HALT = 0xFF


MNEMONICS = {
    Opcode.NOP: "nop",
    Opcode.PUSHI: "pushi",
    Opcode.LOAD: "load",
    Opcode.STORE: "store",
    Opcode.DUP: "dup",
    Opcode.DROP: "drop",
    Opcode.SWAP: "swap",
    Opcode.ADD: "add",
    Opcode.SUB: "sub",
    Opcode.MUL: "mul",
    Opcode.DIV: "div",
    Opcode.LE: "le",
    Opcode.JMP: "jmp",
    Opcode.JZ: "jz",
    Opcode.CALL: "call",
    Opcode.RET: "ret",
    Opcode.IRET: "iret",
    Opcode.EI: "ei",
    Opcode.DI: "di",
    Opcode.IN: "in",
    Opcode.OUT: "out",
    Opcode.HALT: "halt",
}


@dataclass
class Instr:
    opcode: Opcode
    arg: int = 0


def encode(instrs: list[Instr]) -> bytes:
    out = bytearray()
    for ins in instrs:
        word = ((int(ins.opcode) & 0xFF) << 24) | (ins.arg & 0x00FF_FFFF)
        out.extend((word & 0xFF, (word >> 8) & 0xFF, (word >> 16) & 0xFF, (word >> 24) & 0xFF))
    return bytes(out)


def decode(blob: bytes) -> list[Instr]:
    code: list[Instr] = []
    for i in range(0, len(blob), 4):
        if i + 3 >= len(blob):
            break
        word = blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16) | (blob[i + 3] << 24)
        opcode = Opcode((word >> 24) & 0xFF)
        arg = word & 0x00FF_FFFF
        # восстановим знак для PUSHI (24-битный знаковый)
        if opcode == Opcode.PUSHI and arg & 0x0080_0000:
            arg = arg - (1 << 24)
        code.append(Instr(opcode, arg))
    return code


def to_hex(code: list[Instr]) -> str:
    lines: list[str] = []
    for addr, ins in enumerate(code):
        word = ((int(ins.opcode) & 0xFF) << 24) | (ins.arg & 0x00FF_FFFF)
        mnem = MNEMONICS[ins.opcode]
        if ins.opcode in (Opcode.JMP, Opcode.JZ, Opcode.CALL, Opcode.IN, Opcode.OUT, Opcode.PUSHI):
            mnem = f"{mnem} {ins.arg}"
        lines.append(f"{addr} - {word:08X} - {mnem}")
    return "\n".join(lines)


# Порты ввода-вывода (port-mapped)
class Port(IntEnum):
    CH = 1  # символьный поток
    D = 2  # поток целых (32-бит)
    L = 3  # поток long (64-бит представляется в порту как два слова)


# Размер таблицы векторов прерываний (первые слова памяти инструкций)
DEFAULT_NUM_VECTORS = 8
