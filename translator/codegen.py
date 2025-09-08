from __future__ import annotations

try:
    from ..isa import DEFAULT_NUM_VECTORS, Instr, Opcode
except ImportError:
    from isa import DEFAULT_NUM_VECTORS, Instr, Opcode
from .parser import (
    Assign,
    BinOp,
    Break,
    Call,
    Expr,
    Func,
    If,
    IntLit,
    PrintChar,
    PrintInt,
    PrintStr,
    Program,
    Stmt,
    Var,
    VarDecl,
    While,
)


class Codegen:
    def __init__(self):
        self.code: list[Instr] = []
        self.labels: dict[str, int] = {}
        self.vars: dict[str, int] = {}  # переменные в статической памяти (адрес)
        self.data_next = 0
        self.break_stack: list[list[int]] = []
        self.var_types: dict[str, str] = {}
        self.array_bases: dict[str, int] = {}
        self.string_bases: dict[str, int] = {}

    def _ensure_cstr_literal(self, text: str) -> int:
        """Ensure c-string literal is placed in data memory and a pointer cell exists.
        Returns address of the variable cell that stores pointer to the literal buffer.
        """
        if text in self.string_bases:
            return self.string_bases[text]
        # allocate buffer for chars + NUL terminator
        base = self.alloc_buffer(len(text) + 1)
        # initialize buffer contents at runtime (store bytes)
        for i, ch in enumerate(text):
            self.emit(Opcode.PUSHI, ord(ch))
            self.emit(Opcode.PUSHI, base + i)
            self.emit(Opcode.STORE)
        # NUL terminator
        self.emit(Opcode.PUSHI, 0)
        self.emit(Opcode.PUSHI, base + len(text))
        self.emit(Opcode.STORE)
        # create a pointer cell and store base pointer into it
        var_name = f"__strlit_{len(self.string_bases)}"
        var_addr = self.alloc_var(var_name)
        self.emit(Opcode.PUSHI, base)
        self.emit(Opcode.PUSHI, var_addr)
        self.emit(Opcode.STORE)
        self.string_bases[text] = var_addr
        return var_addr

    def emit(self, opcode: Opcode, arg: int = 0):
        self.code.append(Instr(opcode, arg))

    def alloc_var(self, name: str) -> int:
        if name in self.vars:
            return self.vars[name]
        addr = self.data_next
        self.vars[name] = addr
        # если тип уже известен и это long/string — выделим больше
        vtype = self.var_types.get(name)
        if vtype == "long":
            self.data_next += 2
        else:
            self.data_next += 1
        return addr

    def alloc_buffer(self, words: int) -> int:
        base = self.data_next
        self.data_next += words
        return base

    def ensure_array_initialized(self, name: str, capacity: int = 128):
        if name in self.array_bases:
            return
        base = self.alloc_buffer(capacity)
        self.array_bases[name] = base
        var_addr = self.alloc_var(name)
        # a <- &buffer
        self.emit(Opcode.PUSHI, base)
        self.emit(Opcode.PUSHI, var_addr)
        self.emit(Opcode.STORE)

    def _emit_print_cstr(self, addr: int):
        # ptr <- addr
        ptr = self.alloc_var("__ptr__")
        # load pointer from var cell
        self.emit(Opcode.PUSHI, addr)
        self.emit(Opcode.LOAD)
        self.emit(Opcode.PUSHI, ptr)
        self.emit(Opcode.STORE)
        start = len(self.code)
        # ch <- *ptr
        self.emit(Opcode.PUSHI, ptr)
        self.emit(Opcode.LOAD)
        self.emit(Opcode.LOAD)
        # if ch == 0 -> end
        self.emit(Opcode.DUP)
        jz = len(self.code)
        self.emit(Opcode.JZ, 0)
        # print ch
        self.emit(Opcode.OUT, 1)
        # ptr++
        self.emit(Opcode.PUSHI, ptr)
        self.emit(Opcode.LOAD)
        self.emit(Opcode.PUSHI, 1)
        self.emit(Opcode.ADD)
        self.emit(Opcode.PUSHI, ptr)
        self.emit(Opcode.STORE)
        # loop
        self.emit(Opcode.JMP, start)
        end = len(self.code)
        self.code[jz].arg = end

    def gen_expr(self, e: Expr):
        if isinstance(e, IntLit):
            self.emit(Opcode.PUSHI, e.value & 0x00FF_FFFF)
            return
        if isinstance(e, Var):
            addr = self.alloc_var(e.name)
            self.emit(Opcode.PUSHI, addr)
            self.emit(Opcode.LOAD)
            return
        if isinstance(e, Call):
            # поддерживаем только readInt()
            if e.name == "readInt":
                # читаем последовательность цифр через порт CH и строим число
                # минимальный runtime на месте: acc = 0; читать, пока не \n
                # var tmp, ch
                tmp = self.alloc_var("__tmp__")
                ch = self.alloc_var("__ch__")
                # tmp = 0
                self.emit(Opcode.PUSHI, 0)
                self.emit(Opcode.PUSHI, tmp)
                self.emit(Opcode.STORE)
                # loop:
                loop = len(self.code)
                # ch = IN CH
                self.emit(Opcode.IN, 1)
                self.emit(Opcode.PUSHI, ch)
                self.emit(Opcode.STORE)
                # if ch == '\n' -> end
                self.emit(Opcode.PUSHI, ch)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.PUSHI, ord("\n"))
                self.emit(Opcode.SUB)
                jz = len(self.code)
                self.emit(Opcode.JZ, 0)
                # tmp = tmp*10 + (ch - '0')
                self.emit(Opcode.PUSHI, tmp)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.PUSHI, 10)
                self.emit(Opcode.MUL)
                self.emit(Opcode.PUSHI, ch)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.PUSHI, ord("0"))
                self.emit(Opcode.SUB)
                self.emit(Opcode.ADD)
                self.emit(Opcode.PUSHI, tmp)
                self.emit(Opcode.STORE)
                self.emit(Opcode.JMP, loop)
                end = len(self.code)
                self.code[jz].arg = end
                # push tmp
                self.emit(Opcode.PUSHI, tmp)
                self.emit(Opcode.LOAD)
                return
            if e.name == "readChar":
                # просто IN CH
                self.emit(Opcode.IN, 1)
                return
            if e.name == "get" and len(e.args) == 2 and isinstance(e.args[0], Var):
                # Ensure backing array exists and variable holds pointer to it
                self.ensure_array_initialized(e.args[0].name)
                base_addr = self.alloc_var(e.args[0].name)
                # addr = (*base_addr) + idx; then load *addr
                self.emit(Opcode.PUSHI, base_addr)
                self.emit(Opcode.LOAD)
                self.gen_expr(e.args[1])
                self.emit(Opcode.ADD)
                self.emit(Opcode.LOAD)
                return
            raise NotImplementedError(f"call not supported: {e.name}")
        if isinstance(e, BinOp):
            if e.op == "*":
                self.gen_expr(e.a)
                self.gen_expr(e.b)
                self.emit(Opcode.MUL)
                return
            if e.op == "+":
                self.gen_expr(e.a)
                self.gen_expr(e.b)
                self.emit(Opcode.ADD)
                return
            if e.op == "-":
                self.gen_expr(e.a)
                self.gen_expr(e.b)
                self.emit(Opcode.SUB)
                return
            if e.op == "<=":
                self.gen_expr(e.a)
                self.gen_expr(e.b)
                self.emit(Opcode.LE)
                return
            if e.op == "==":
                # a == b -> push 1 if equal else 0
                self.gen_expr(e.a)
                self.gen_expr(e.b)
                self.emit(Opcode.SUB)
                l_true = len(self.code)
                self.emit(Opcode.JZ, 0)  # if a-b == 0 -> true
                # false path
                self.emit(Opcode.PUSHI, 0)
                l_end = len(self.code)
                self.emit(Opcode.JMP, 0)
                # true path
                self.code[l_true].arg = len(self.code)
                self.emit(Opcode.PUSHI, 1)
                # end
                self.code[l_end].arg = len(self.code)
                return
        raise NotImplementedError(f"expr not supported: {e}")

    def gen_stmt(self, s: Stmt):
        if isinstance(s, Break):
            if not self.break_stack:
                raise NotImplementedError("break outside of loop")
            pos = len(self.code)
            self.emit(Opcode.JMP, 0)
            self.break_stack[-1].append(pos)
            return
        if isinstance(s, VarDecl):
            self.alloc_var(s.name)
            self.var_types[s.name] = s.vtype
            if s.vtype == "string":
                base = self.alloc_buffer(64)
                var_addr = self.alloc_var(s.name)
                self.emit(Opcode.PUSHI, base)
                self.emit(Opcode.PUSHI, var_addr)
                self.emit(Opcode.STORE)
            return
        if isinstance(s, Assign):
            # Спец.случай: строка = readString()
            if isinstance(s.expr, Call) and s.expr.name == "readString":
                base = self.alloc_var(s.name)
                ptr = self.alloc_var("__ptr__")
                # ptr <- *base (string variable stores pointer to buffer)
                self.emit(Opcode.PUSHI, base)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.PUSHI, ptr)
                self.emit(Opcode.STORE)
                rs = len(self.code)
                # ch <- IN CH
                self.emit(Opcode.IN, 1)
                # if ch == '\n' -> end
                self.emit(Opcode.DUP)
                self.emit(Opcode.PUSHI, ord("\n"))
                self.emit(Opcode.SUB)
                jz_end = len(self.code)
                self.emit(Opcode.JZ, 0)
                # *ptr = ch
                self.emit(Opcode.PUSHI, ptr)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.STORE)
                # ptr++
                self.emit(Opcode.PUSHI, ptr)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.PUSHI, 1)
                self.emit(Opcode.ADD)
                self.emit(Opcode.PUSHI, ptr)
                self.emit(Opcode.STORE)
                # loop
                self.emit(Opcode.JMP, rs)
                end = len(self.code)
                self.code[jz_end].arg = end
                # write terminator 0
                self.emit(Opcode.PUSHI, 0)
                self.emit(Opcode.PUSHI, ptr)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.STORE)
                return
            # long присваивание: a = b + c; a = readLong();
            if self.var_types.get(s.name) == "long":
                base = self.alloc_var(s.name)
                base_hi = base + 1
                # a = readLong()
                if isinstance(s.expr, Call) and s.expr.name == "readLong":
                    # IN L: читаем lo и hi по очереди
                    self.emit(Opcode.IN, 3)  # lo
                    self.emit(Opcode.PUSHI, base)
                    self.emit(Opcode.STORE)
                    self.emit(Opcode.IN, 3)  # hi
                    self.emit(Opcode.PUSHI, base_hi)
                    self.emit(Opcode.STORE)
                    return
                # a = b + c (long)
                if isinstance(s.expr, BinOp) and s.expr.op == "+":

                    def gen_load_long(var: Var):
                        addr = self.alloc_var(var.name)
                        # lo
                        self.emit(Opcode.PUSHI, addr)
                        self.emit(Opcode.LOAD)
                        # hi на стек сверху
                        self.emit(Opcode.PUSHI, addr + 1)
                        self.emit(Opcode.LOAD)

                    assert isinstance(s.expr.a, Var) and isinstance(s.expr.b, Var)
                    gen_load_long(s.expr.a)  # a_lo, a_hi
                    gen_load_long(s.expr.b)  # b_lo, b_hi (в вершине b_hi)
                    # сложение lo: возьмём a_lo и b_lo
                    # стек: a_lo, a_hi, b_lo, b_hi
                    # перестроим порядок для lo: ... a_lo, b_lo на вершине через SWAP/переукладку
                    # упростим: сохраним в темпах и перезагрузим
                    tmp_lo = self.alloc_var("__tmp_lo__")
                    tmp_hi = self.alloc_var("__tmp_hi__")
                    # pop b_hi -> tmp_hi
                    self.emit(Opcode.PUSHI, tmp_hi)
                    self.emit(Opcode.SWAP)  # не хватает SWAP с адресом
                    # Из-за ограничений стековой модели, используем прямые LOAD для чтения из памяти повторно:
                    # lo_sum = (a_lo + b_lo)
                    self.emit(Opcode.PUSHI, self.alloc_var(s.expr.a.name))
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.PUSHI, self.alloc_var(s.expr.b.name))
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.ADD)
                    # tmp_lo = lo_sum
                    self.emit(Opcode.PUSHI, tmp_lo)
                    self.emit(Opcode.STORE)
                    # carry = lo_sum < a_lo
                    # compute a_lo - 1
                    self.emit(Opcode.PUSHI, self.alloc_var(s.expr.a.name))
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.PUSHI, 1)
                    self.emit(Opcode.SUB)  # a_lo-1
                    # push lo_sum
                    self.emit(Opcode.PUSHI, tmp_lo)
                    self.emit(Opcode.LOAD)
                    # test lo_sum <= a_lo-1
                    self.emit(Opcode.LE)
                    # now T is 1 if carry else 0
                    # hi_sum = a_hi + b_hi
                    self.emit(Opcode.PUSHI, self.alloc_var(s.expr.a.name) + 1)
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.PUSHI, self.alloc_var(s.expr.b.name) + 1)
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.ADD)
                    self.emit(Opcode.PUSHI, tmp_hi)
                    self.emit(Opcode.STORE)
                    # if carry then tmp_hi = tmp_hi + 1
                    jz = len(self.code)
                    self.emit(Opcode.JZ, 0)
                    self.emit(Opcode.PUSHI, tmp_hi)
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.PUSHI, 1)
                    self.emit(Opcode.ADD)
                    self.emit(Opcode.PUSHI, tmp_hi)
                    self.emit(Opcode.STORE)
                    endc = len(self.code)
                    self.emit(Opcode.JMP, 0)
                    self.code[jz].arg = len(self.code)
                    self.code[endc].arg = len(self.code)
                    # store to a
                    self.emit(Opcode.PUSHI, tmp_lo)
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.PUSHI, base)
                    self.emit(Opcode.STORE)
                    self.emit(Opcode.PUSHI, tmp_hi)
                    self.emit(Opcode.LOAD)
                    self.emit(Opcode.PUSHI, base_hi)
                    self.emit(Opcode.STORE)
                    return
                # fallback: присваивание из 32-бит (lo), hi=0
                self.gen_expr(s.expr)
                self.emit(Opcode.PUSHI, base)
                self.emit(Opcode.STORE)
                self.emit(Opcode.PUSHI, 0)
                self.emit(Opcode.PUSHI, base_hi)
                self.emit(Opcode.STORE)
                return
            # обычное присваивание (int/char)
            self.gen_expr(s.expr)
            addr = self.alloc_var(s.name)
            self.emit(Opcode.PUSHI, addr)
            self.emit(Opcode.STORE)
            return
        if isinstance(s, While):
            start = len(self.code)
            self.gen_expr(s.cond)
            jz_pos = len(self.code)
            self.emit(Opcode.JZ, 0)  # заполнится позже
            # новый уровень break-адресов
            self.break_stack.append([])
            for st in s.body:
                if isinstance(st, Break):
                    br_pos = len(self.code)
                    self.emit(Opcode.JMP, 0)  # заполнится после тела цикла
                    self.break_stack[-1].append(br_pos)
                else:
                    self.gen_stmt(st)
            self.emit(Opcode.JMP, start)
            end = len(self.code)
            self.code[jz_pos].arg = end
            # проставим все break'и на конец цикла
            for pos in self.break_stack.pop():
                self.code[pos].arg = end
            return
        if isinstance(s, If):
            self.gen_expr(s.cond)
            jz_pos = len(self.code)
            self.emit(Opcode.JZ, 0)
            for st in s.then_body:
                self.gen_stmt(st)
            if s.else_body is not None:
                jmp_end = len(self.code)
                self.emit(Opcode.JMP, 0)
                self.code[jz_pos].arg = len(self.code)
                for st in s.else_body:
                    self.gen_stmt(st)
                self.code[jmp_end].arg = len(self.code)
            else:
                self.code[jz_pos].arg = len(self.code)
            return
        if isinstance(s, Call):
            # interrupts control
            if s.name == "ei" and len(s.args) == 0:
                self.emit(Opcode.EI)
                return
            if s.name == "di" and len(s.args) == 0:
                self.emit(Opcode.DI)
                return
            if s.name == "printChar" and len(s.args) == 1:
                self.gen_expr(s.args[0])
                self.emit(Opcode.OUT, 1)
                return
            if s.name == "readChar" and len(s.args) == 0:
                self.emit(Opcode.IN, 1)
                return
            if s.name == "printLong" and len(s.args) == 1 and isinstance(s.args[0], Var):
                base = self.alloc_var(s.args[0].name)
                # out lo, then hi to Port L
                self.emit(Opcode.PUSHI, base)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.OUT, 3)
                self.emit(Opcode.PUSHI, base + 1)
                self.emit(Opcode.LOAD)
                self.emit(Opcode.OUT, 3)
                return
            if s.name == "set" and len(s.args) == 3 and isinstance(s.args[0], Var):
                # Ensure backing array exists and variable holds pointer
                self.ensure_array_initialized(s.args[0].name)
                base_addr = self.alloc_var(s.args[0].name)
                # push value first (STORE expects value on top after popping addr)
                self.gen_expr(s.args[2])
                # compute addr = (*base_addr) + idx
                self.emit(Opcode.PUSHI, base_addr)
                self.emit(Opcode.LOAD)
                self.gen_expr(s.args[1])
                self.emit(Opcode.ADD)
                # store value at addr
                self.emit(Opcode.STORE)
                return
            raise NotImplementedError(f"call statement not supported: {s.name}")
        if isinstance(s, PrintInt):
            # runtime: печать целого через порт D (числовой), затем перевод строки в CH
            self.gen_expr(s.expr)
            self.emit(Opcode.OUT, 2)  # Port.D = 2
            self.emit(Opcode.PUSHI, ord("\n"))
            self.emit(Opcode.OUT, 1)  # Port.CH = 1
            return
        if isinstance(s, PrintStr):
            # Помещаем строковый литерал в data memory (cstr) и печатаем через _emit_print_cstr
            var_addr = self._ensure_cstr_literal(s.text)
            self._emit_print_cstr(var_addr)
            return
        if isinstance(s, PrintChar):
            # Если аргумент — строковая переменная: печатаем cstr, иначе символ
            if isinstance(s.expr, Var) and self.var_types.get(s.expr.name) == "string":
                addr = self.alloc_var(s.expr.name)
                self._emit_print_cstr(addr)
            else:
                self.gen_expr(s.expr)
                self.emit(Opcode.OUT, 1)
            return
        raise NotImplementedError(f"stmt not supported: {s}")

    def _is_irq_func(self, name: str) -> int | None:
        if name.startswith("irq") and name[3:].isdigit():
            n = int(name[3:])
            return n
        return None

    def gen_func(self, f: Func):
        # записываем адрес начала функции
        self.labels[f.name] = len(self.code)
        for st in f.body:
            self.gen_stmt(st)
        # завершение функции в зависимости от типа
        irq_n = self._is_irq_func(f.name)
        if f.name == "main":
            self.emit(Opcode.HALT)
        elif irq_n is not None:
            self.emit(Opcode.IRET)
        else:
            self.emit(Opcode.RET)

    def gen(self, prog: Program) -> list[Instr]:
        # таблица векторов прерываний (DEFAULT_NUM_VECTORS слов в начале)
        # по умолчанию — все на NOP; IRQ0,1,2... содержат адресы обработчиков
        # пока обработчики не генерируем, поэтому заполним jump на main.
        vectors = [Instr(Opcode.JMP, 0) for _ in range(DEFAULT_NUM_VECTORS)]

        # базовый адрес кода после таблицы векторов
        start_main = len(vectors)

        # сгенерировать код всех функций (main, irq*, прочие)
        for f in prog.functions:
            self.gen_func(f)

        # релокация адресов переходов внутри кода: смещение на start_main
        for ins in self.code:
            if ins.opcode in (Opcode.JMP, Opcode.JZ, Opcode.CALL):
                ins.arg += start_main

        # вектор 0 — вход: перейти на main
        if "main" in self.labels:
            vectors[0].arg = start_main + self.labels["main"]
        # векторы прерываний irqN -> адрес функции irqN, если есть
        for i in range(1, DEFAULT_NUM_VECTORS):
            fname = f"irq{i}"
            if fname in self.labels:
                vectors[i] = Instr(Opcode.JMP, start_main + self.labels[fname])
        return vectors + self.code
