from __future__ import annotations

import argparse

try:
    from .core.io import IOEvent
    from .core.runner import run_machine
except ImportError:
    from core.io import IOEvent
    from core.runner import run_machine


def parse_schedule(path: str):
    events = []

    def decode_char_token(tok: str) -> int:
        # escaped: \n, \t, \r, \0, \xHH
        if tok == "\\n":
            return 10
        if tok == "\\t":
            return 9
        if tok == "\\r":
            return 13
        if tok == "\\0":
            return 0
        if tok.startswith("\\x") and len(tok) == 4:
            return int(tok[2:], 16)
        # quoted 'A' or "A"
        if (tok.startswith("'") and tok.endswith("'") and len(tok) >= 3) or (
            tok.startswith('"') and tok.endswith('"') and len(tok) >= 3
        ):
            return ord(tok[1])
        # hex like 0x41
        if tok.startswith("0x") or tok.startswith("0X"):
            return int(tok, 16)
        # single literal char (A, B, 5 etc.)
        if len(tok) >= 1:
            return ord(tok[0])
        raise ValueError("bad token")

    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) != 3:
                raise ValueError("bad schedule line")
            tick = int(parts[0])
            port = int(parts[1])
            val_tok = parts[2]
            # CH (1) может принимать символьные токены; для D/L придерживаемся чисел
            if port == 1:
                value = decode_char_token(val_tok)
            else:
                value = int(val_tok, 0) if (val_tok.startswith("0x") or val_tok.startswith("0X")) else int(val_tok)
            events.append(IOEvent(tick=tick, port=port, value=value))
    return events


def main():
    ap = argparse.ArgumentParser(description="Run stack|harv machine")
    ap.add_argument("program", help="binary code path")
    ap.add_argument("--schedule", help="text schedule file (tick port value)")
    ap.add_argument("--data-words", type=int, default=1024)
    ap.add_argument("--ticks", type=int, default=100000)
    ap.add_argument("--trace", action="store_true", help="dump per-tick trace")
    ap.add_argument("--trace-file", help="write trace to file (default: stdout)")
    args = ap.parse_args()

    sched = parse_schedule(args.schedule) if args.schedule else []
    out = run_machine(args.program, sched, args.data_words, args.ticks, trace=args.trace, trace_file=args.trace_file)
    # печать портов (CH -> строка, D -> числа через пробел)
    if out.get(1):
        s = bytes([v & 0xFF for v in out[1]]).decode("latin1", errors="replace")
        print(f"CH| {s}")
    if out.get(2):
        print("D| ", " ".join(str(int(v) if v < 2**31 else v - 2**32) for v in out[2]))
    if out.get(3):
        words = out[3]
        if len(words) % 2 != 0:
            print("L| (warn: odd words)")
        else:
            vals = []
            for i in range(0, len(words), 2):
                lo = words[i] & 0xFFFF_FFFF
                hi = words[i + 1] & 0xFFFF_FFFF
                val = (hi << 32) | lo
                vals.append(str(val))
            print("L| ", " ".join(vals))


if __name__ == "__main__":
    main()
