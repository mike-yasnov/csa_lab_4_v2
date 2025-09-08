from __future__ import annotations

from typing import Optional

from isa import DEFAULT_NUM_VECTORS, Instr, Opcode

from .datapath import DataPath
from .io import IOController


class CPU:
    def __init__(
        self,
        instr_mem: list[Instr],
        data_words: int,
        io: IOController,
        num_vectors: int = DEFAULT_NUM_VECTORS,
        tick_limit: int = 100000,
    ):
        self.imem = instr_mem
        self.dp = DataPath(data_words, io)
        self.rs: list[int] = []  # return stack
        self.pc = 0
        self.ir: Optional[Instr] = None
        self.tick = 0
        self.tick_limit = tick_limit

        self.num_vectors = num_vectors
        self.io = io

        # Enable interrupts by default; ISR handlers can DI/EI
        self.int_enabled = True
        self.in_isr = False

        # фазы/шаги
        self._phase = "FETCH_IR"  # FETCH_IR -> LATCH_PC -> EXEC
        self._step = 0
        self._halted = False
        self.last_pc: int = 0
        self.last_ir: Optional[Instr] = None
        self._tmp_addr: int = 0
        self._tmp_val: int = 0
        self._tmp_alu: int = 0

    def tick_inc(self):
        self.tick += 1

    def maybe_raise_irq(self):
        if not self.int_enabled or self.in_isr:
            return False
        irq = self.io.irq_pending()
        if irq is None:
            return False
        self.rs.append(self.pc)
        self.pc = irq
        self.in_isr = True
        self.io.ack_irq()
        return True

    def step_tick(self):
        if self._halted:
            return

        self.dp.tick_begin()
        self.io.on_tick(self.tick)
        if self._phase == "FETCH_IR" and self.maybe_raise_irq():
            self.tick_inc()
            return

        if self._phase == "FETCH_IR":
            self.last_pc = self.pc
            self.ir = self.imem[self.pc]
            self.last_ir = self.ir
            self._phase = "LATCH_PC"
            self.tick_inc()
            return

        if self._phase == "LATCH_PC":
            self.pc += 1
            self._phase = "EXEC"
            self._step = 0
            self.tick_inc()
            return

        op, arg = self.ir.opcode, self.ir.arg

        if op == Opcode.NOP and self._step == 0:
            self._finish_instruction()
            return

        if op == Opcode.PUSHI and self._step == 0:
            self.dp.latch_t_push("lit", arg)
            self._finish_instruction()
            return

        if op == Opcode.DUP and self._step == 0:
            self.dp.data_push(self.dp.t)
            self._finish_instruction()
            return
        if op == Opcode.DROP and self._step == 0:
            self.dp.data_pop()
            self._finish_instruction()
            return
        if op == Opcode.SWAP and self._step == 0:
            a = self.dp.data_pop()
            b = self.dp.data_pop()
            self.dp.data_push(a)
            self.dp.data_push(b)
            self._finish_instruction()
            return

        if op in (Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.LE):
            if self._step == 0:
                self.dp.alu_compute(op)
                self._tmp_alu = self.dp._last_alu
                self._step = 1
                self.tick_inc()
                return
            if self._step == 1:
                self.dp.data_pop()
                self._step = 2
                self.tick_inc()
                return
            if self._step == 2:
                self.dp.data_pop()
                self.dp.latch_t_push("alu", self._tmp_alu)
                self._finish_instruction()
                return

        if op == Opcode.LOAD:
            if self._step == 0:
                self.dp.latch_ar_from_t()
                self._step = 1
                self.tick_inc()
                return
            if self._step == 1:
                self.dp.dm_read()
                self._step = 2
                self.tick_inc()
                return
            if self._step == 2:
                self.dp.data_pop()
                self.dp.latch_t_push("mem")
                self._finish_instruction()
                return

        if op == Opcode.STORE:
            if self._step == 0:
                self._tmp_addr = self.dp.data_pop()
                self.dp.latch_ar_from_lit(self._tmp_addr)
                self._step = 1
                self.tick_inc()
                return
            if self._step == 1:
                self._tmp_val = self.dp.data_pop()
                self._step = 2
                self.tick_inc()
                return
            if self._step == 2:
                self.dp.dm_write(self._tmp_val)
                self._finish_instruction()
                return

        if op == Opcode.JMP and self._step == 0:
            self.pc = arg
            self._finish_instruction()
            return

        if op == Opcode.JZ and self._step == 0:
            if self.dp.zero:
                self.pc = arg
            self.dp.data_pop()
            self._finish_instruction()
            return

        if op == Opcode.CALL and self._step == 0:
            self.rs.append(self.pc)
            self.pc = arg
            self._finish_instruction()
            return
        if op == Opcode.RET and self._step == 0:
            self.pc = self.rs.pop() if self.rs else self.pc
            self._finish_instruction()
            return
        if op == Opcode.IRET and self._step == 0:
            self.pc = self.rs.pop() if self.rs else self.pc
            self.in_isr = False
            self._finish_instruction()
            return

        if op == Opcode.EI and self._step == 0:
            self.int_enabled = True
            self._finish_instruction()
            return
        if op == Opcode.DI and self._step == 0:
            self.int_enabled = False
            self._finish_instruction()
            return

        if op == Opcode.IN:
            if self._step == 0:
                self.dp.latch_io_read(arg)
                self._step = 1
                self.tick_inc()
                return
            if self._step == 1:
                self.dp.latch_t_push("io")
                self._finish_instruction()
                return

        if op == Opcode.OUT:
            if self._step == 0:
                v = self.dp.data_pop()
                self.dp.latch_io_write_prepare(v)
                self._step = 1
                self.tick_inc()
                return
            if self._step == 1:
                self.dp.io_write_commit(arg)
                self._finish_instruction()
                return

        if op == Opcode.HALT and self._step == 0:
            self._halted = True
            self.tick_inc()
            return

        raise AssertionError(f"unknown or unhandled opcode: {op} step {self._step}")

    def _finish_instruction(self):
        self._phase = "FETCH_IR"
        self._step = 0
        self.tick_inc()
