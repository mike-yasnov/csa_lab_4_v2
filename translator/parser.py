from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .lexer import Token, tokenize


# AST для подмножества prob2.alg
@dataclass
class Program:
    functions: list[Func]


@dataclass
class Func:
    name: str
    body: list[Stmt]


class Stmt:  # маркер
    pass


@dataclass
class VarDecl(Stmt):
    vtype: str
    name: str


@dataclass
class Assign(Stmt):
    name: str
    expr: Expr


@dataclass
class While(Stmt):
    cond: Expr
    body: list[Stmt]


@dataclass
class PrintInt(Stmt):
    expr: Expr


@dataclass
class PrintStr(Stmt):
    text: str


@dataclass
class PrintChar(Stmt):
    expr: Expr


@dataclass
class Break(Stmt):
    pass


@dataclass
class If(Stmt):
    cond: Expr
    then_body: list[Stmt]
    else_body: list[Stmt] | None = None


@dataclass
class Expr:  # маркер
    pass


@dataclass
class IntLit(Expr):
    value: int


@dataclass
class Var(Expr):
    name: str


@dataclass
class BinOp(Expr):
    op: str
    a: Expr
    b: Expr


@dataclass
class Call(Expr):
    name: str
    args: list[Expr]


class Parser:
    def __init__(self, tokens: Iterator[Token]):
        self.tokens = list(tokens)
        self.i = 0

    def cur(self) -> Token:
        return self.tokens[self.i]

    def eat(self, kind: str | None = None, value: str | None = None) -> Token:
        t = self.cur()
        if kind and t.kind != kind:
            raise SyntaxError("bad token kind")
        if value and t.value != value:
            raise SyntaxError("bad token value")
        self.i += 1
        return t

    def match(self, value: str) -> bool:
        return self.cur().value == value

    def parse(self) -> Program:
        funcs: list[Func] = []
        while self.i < len(self.tokens):
            funcs.append(self.parse_func())
        return Program(funcs)

    def parse_func(self) -> Func:
        self.eat("KW", "func")
        name = self.eat("ID").value
        self.eat("(")
        self.eat(")")
        self.eat("{")
        body: list[Stmt] = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        self.eat("}")
        return Func(name, body)

    def parse_stmt(self) -> Stmt:
        t = self.cur()
        if t.kind == "KW" and t.value in {"int", "long", "string", "char"}:
            vtype = self.eat("KW").value
            name = self.eat("ID").value
            self.eat(";")
            return VarDecl(vtype, name)
        if t.kind == "KW" and t.value == "break":
            self.eat("KW", "break")
            self.eat(";")
            return Break()
        if t.kind == "KW" and t.value == "if":
            self.eat("KW", "if")
            self.eat("(")
            cond = self.parse_expr()
            self.eat(")")
            self.eat("{")
            body: list[Stmt] = []
            while not self.match("}"):
                body.append(self.parse_stmt())
            self.eat("}")
            else_body: list[Stmt] | None = None
            if self.i < len(self.tokens) and self.cur().value == "else":
                self.eat("KW", "else")
                self.eat("{")
                else_body = []
                while not self.match("}"):
                    else_body.append(self.parse_stmt())
                self.eat("}")
            return If(cond, body, else_body)
        if t.kind == "KW" and t.value == "while":
            self.eat("KW", "while")
            self.eat("(")
            cond = self.parse_expr()
            self.eat(")")
            self.eat("{")
            body: list[Stmt] = []
            while not self.match("}"):
                body.append(self.parse_stmt())
            self.eat("}")
            return While(cond, body)
        if t.kind == "KW" and t.value == "printInt":
            self.eat("KW", "printInt")
            self.eat("(")
            e = self.parse_expr()
            self.eat(")")
            self.eat(";")
            return PrintInt(e)
        if t.kind == "KW" and t.value == "print":
            # print("...") или print(<expr>) как char
            self.eat("KW", "print")
            self.eat("(")
            if self.cur().kind == "STR":
                s = self.eat("STR").value
                self.eat(")")
                self.eat(";")
                return PrintStr(s)
            e = self.parse_expr()
            self.eat(")")
            self.eat(";")
            return PrintChar(e)
        if t.kind == "ID":
            name = self.eat("ID").value
            # вызов-процедура или присваивание
            if self.cur().value == "(":
                self.eat("(")
                args: list[Expr] = []
                if self.cur().value != ")":
                    args.append(self.parse_expr())
                    while self.cur().value == ",":
                        self.eat(",")
                        args.append(self.parse_expr())
                self.eat(")")
                self.eat(";")
                return Call(name, args)
            self.eat("=")
            e = self.parse_expr()
            self.eat(";")
            return Assign(name, e)
        raise SyntaxError(f"unexpected token {t}")

    def parse_expr(self) -> Expr:
        # только +, -, *, <=, приоритет: *, затем +-, затем <= (левая ассоциативность)
        def parse_term() -> Expr:
            t = self.cur()
            if t.kind == "INT":
                self.eat("INT")
                return IntLit(int(t.value))
            if t.kind == "KW" and t.value == "true":
                self.eat("KW", "true")
                return IntLit(1)
            if t.kind == "ID":
                name = self.eat("ID").value
                if name == "EOF":
                    return IntLit(0)
                # возможен вызов функции
                if self.i < len(self.tokens) and self.cur().value == "(":
                    self.eat("(")
                    args: list[Expr] = []
                    if self.cur().value != ")":
                        args.append(self.parse_expr())
                        while self.cur().value == ",":
                            self.eat(",")
                            args.append(self.parse_expr())
                    self.eat(")")
                    return Call(name, args)
                return Var(name)
            if t.kind == "STR":
                self.eat("STR")
                # строковый литерал допустим только в print(); но вернём как Var-эмулированный тип
                # Генерация будет обрабатывать отдельно.
                return IntLit(0)  # placeholder, фактическое значение на этапе codegen
            raise SyntaxError("term expected")

        def parse_mul() -> Expr:
            e = parse_term()
            while self.i < len(self.tokens) and self.cur().value == "*":
                self.eat("*")
                e = BinOp("*", e, parse_term())
            return e

        def parse_add() -> Expr:
            e = parse_mul()
            while self.i < len(self.tokens) and self.cur().value in {"+", "-"}:
                op = self.eat(self.cur().value).value
                e = BinOp(op, e, parse_mul())
            return e

        e = parse_add()
        # сравнительные: ==, <= (без цепочек)
        if self.i < len(self.tokens) and self.cur().value in {"<=", "=="}:
            op = self.eat(self.cur().value).value
            e = BinOp(op, e, parse_add())
        return e


def parse_source(src: str) -> Program:
    return Parser(tokenize(src)).parse()
