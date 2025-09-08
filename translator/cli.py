from __future__ import annotations

import argparse

try:
    from ..isa import encode, to_hex
    from .parser import parse_source
    from .codegen import Codegen
except ImportError:
    # запуск как пакет из каталога lab_implementation (translator — пакет верхнего уровня)
    from isa import encode, to_hex
    from translator.parser import parse_source
    from translator.codegen import Codegen


def main():
    ap = argparse.ArgumentParser(description="ALG -> binary translator (stack|harv)")
    ap.add_argument("source", help="input .alg file")
    ap.add_argument("target", help="output .bin file")
    ap.add_argument("--hex", dest="hexdump", help="write hex listing to file")
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as f:
        src = f.read()
    prog = parse_source(src)
    cg = Codegen()
    code = cg.gen(prog)

    blob = encode(code)
    with open(args.target, "wb") as f:
        f.write(blob)
    if args.hexdump:
        with open(args.hexdump, "w", encoding="utf-8") as f:
            f.write(to_hex(code))


if __name__ == "__main__":
    main()


