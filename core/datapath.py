from __future__ import annotations

from isa import Opcode

from .io import IOController


class DataPath:
    """Тракт данных: стек, AR, однопортовая память, ALU и IO-регистр."""

    def __init__(self, data_words: int, io: IOController):
        self.mem = [0] * max(1, data_words)
        self.io = io

        self.stack: list[int] = []
        self.t: int = 0
        self.s: int = 0
        self.ar: int = 0
        self.io_reg: int = 0
        self.zero: bool = True
        self.sign: bool = False
        self._last_mem_read: int = 0
        self._last_mem_write: int = 0
        self._last_alu: int = 0
        self._mem_access: str | None = None  # 'r' или 'w' на такт

    def tick_begin(self):
        self._mem_access = None

    def _refresh_tz(self):
        self.t = self.stack[-1] & 0xFFFF_FFFF if self.stack else 0
        self.s = self.stack[-2] & 0xFFFF_FFFF if len(self.stack) >= 2 else 0
        self.zero = (self.t & 0xFFFF_FFFF) == 0
        self.sign = (self.t & 0x8000_0000) != 0

    # Стек
    def data_push(self, value: int):
        self.stack.append(value & 0xFFFF_FFFF)
        self._refresh_tz()

    def data_pop(self) -> int:
        v = self.stack.pop() if self.stack else 0
        self._refresh_tz()
        return v

    def latch_t_push(self, source: str, value: int | None = None):
        if source == "lit":
            assert value is not None
            self.data_push(value)
        elif source == "mem":
            self.data_push(self._last_mem_read)
        elif source == "alu":
            self.data_push(self._last_alu)
        elif source == "io":
            self.data_push(self.io_reg)
        else:
            raise AssertionError("unknown latch_t_push source")

    def latch_t_pop(self):
        self._refresh_tz()

    # AR
    def latch_ar_from_t(self):
        self.ar = self.t & 0xFFFF_FFFF

    def latch_ar_from_lit(self, addr: int):
        self.ar = addr & 0xFFFF_FFFF

    # Однопортовая память
    def dm_read(self):
        assert self._mem_access is None, "dm conflict"
        idx = self.ar
        if idx >= len(self.mem):
            self.mem.extend([0] * (idx - len(self.mem) + 1))
        self._last_mem_read = self.mem[idx] & 0xFFFF_FFFF
        self._mem_access = "r"

    def dm_write(self, value: int):
        assert self._mem_access is None, "dm conflict"
        idx = self.ar
        if idx >= len(self.mem):
            self.mem.extend([0] * (idx - len(self.mem) + 1))
        self._last_mem_write = value & 0xFFFF_FFFF
        self.mem[idx] = self._last_mem_write
        self._mem_access = "w"

    # IO
    def latch_io_read(self, port: int):
        self.io_reg = self.io.read_port(port) & 0xFFFF_FFFF

    def latch_io_write_prepare(self, value: int):
        self.io_reg = value & 0xFFFF_FFFF

    def io_write_commit(self, port: int):
        self.io.write_port(port, self.io_reg)

    # ALU
    def alu_compute(self, op: Opcode):
        a = self.s & 0xFFFF_FFFF
        b = self.t & 0xFFFF_FFFF
        if op == Opcode.ADD:
            r = (a + b) & 0xFFFF_FFFF
        elif op == Opcode.SUB:
            r = (a - b) & 0xFFFF_FFFF
        elif op == Opcode.MUL:
            r = (a * b) & 0xFFFF_FFFF
        elif op == Opcode.DIV:
            r = (a // b) & 0xFFFF_FFFF if b != 0 else 0
        elif op == Opcode.LE:
            r = 1 if a <= b else 0
        else:
            raise AssertionError("unsupported alu op")
        self._last_alu = r
        self.zero = (r & 0xFFFF_FFFF) == 0
        self.sign = (r & 0x8000_0000) != 0
