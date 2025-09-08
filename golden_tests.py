from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional


# Ensure local package imports work when running directly
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from translator.parser import parse_source  # type: ignore
from translator.codegen import Codegen  # type: ignore
from isa import encode, to_hex  # type: ignore
from core.runner import run_machine  # type: ignore
from machine_cli import parse_schedule  # type: ignore
import difflib


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def compile_alg(src_path: Path) -> Dict[str, object]:
    src = read_text(src_path)
    prog = parse_source(src)
    cg = Codegen()
    code = cg.gen(prog)
    blob = encode(code)
    hexdump = to_hex(code)
    return {"code": code, "blob": blob, "hex": hexdump}


def format_outputs(out: Dict[int, List[int]]) -> str:
    lines: List[str] = []
    if out.get(1):
        s = bytes([v & 0xFF for v in out[1]]).decode("latin1", errors="replace")
        lines.append(f"CH| {s}")
    if out.get(2):
        d_vals = " ".join(str(int(v) if v < 2**31 else v - 2**32) for v in out[2])
        lines.append(f"D|  {d_vals}")
    if out.get(3):
        words = out[3]
        if len(words) % 2 != 0:
            lines.append("L| (warn: odd words)")
        else:
            vals = []
            for i in range(0, len(words), 2):
                lo = words[i] & 0xFFFF_FFFF
                hi = words[i + 1] & 0xFFFF_FFFF
                val = (hi << 32) | lo
                vals.append(str(val))
            lines.append(f"L|  {' '.join(vals)}")
    return "\n".join(lines) + ("\n" if lines else "")


def generate_golden(
    name: str,
    src_path: Path,
    out_dir: Path,
    schedule_path: Optional[Path],
    ticks: int,
    data_words: int = 1024,
):
    test_dir = out_dir / name
    test_dir.mkdir(parents=True, exist_ok=True)

    # Copy inputs
    write_text(test_dir / "program.alg", read_text(src_path))
    if schedule_path and schedule_path.exists():
        write_text(test_dir / "schedule.txt", read_text(schedule_path))

    # Compile
    comp = compile_alg(src_path)
    blob: bytes = comp["blob"]  # type: ignore
    hexdump: str = comp["hex"]  # type: ignore
    write_bytes(test_dir / "program.bin", blob)
    write_text(test_dir / "program.hex", hexdump)

    # Run with optional schedule and trace
    schedule = parse_schedule(str(schedule_path)) if schedule_path else []
    trace_file = str(test_dir / "trace.txt")
    out = run_machine(str(test_dir / "program.bin"), schedule, data_words, ticks, trace=True, trace_file=trace_file)

    # Outputs
    write_text(test_dir / "out.txt", format_outputs(out))

    # Meta
    meta = {
        "name": name,
        "src": str(src_path),
        "ticks": ticks,
        "data_words": data_words,
        "schedule": str(schedule_path) if schedule_path else None,
    }
    write_text(test_dir / "meta.json", json.dumps(meta, indent=2, ensure_ascii=False))


def discover_tests(project_root: Path) -> List[Dict[str, object]]:
    ex = project_root / "examples"
    return [
        {"name": "hello_world", "src": ex / "hello_world.alg", "sched": None, "ticks": 2000},
        {"name": "cat", "src": ex / "cat.alg", "sched": ex / "cat.input", "ticks": 200},
        {"name": "hello_user_name", "src": ex / "hello_user_name.alg", "sched": ex / "hello_user_name.input", "ticks": 8000},
        {"name": "prob2", "src": ex / "prob2.alg", "sched": ex / "prob2.input", "ticks": 4000},
        {"name": "double_precision", "src": ex / "double_precision.alg", "sched": ex / "double_precision.input", "ticks": 5000},
        {"name": "sort", "src": ex / "sort.alg", "sched": ex / "sort.input", "ticks": 120000},
        {"name": "cat_trap", "src": ex / "cat_trap.alg", "sched": ex / "cat.input", "ticks": 200},
    ]


def main():
    ap = argparse.ArgumentParser(description="Generate golden test artifacts")
    ap.add_argument("--out-dir", default="golden", help="output directory for golden tests")
    ap.add_argument("--only", action="append", help="run only specified test(s) by name", default=None)
    ap.add_argument("--ticks", type=int, help="override ticks for all tests")
    ap.add_argument("--verify", action="store_true", help="run tests against existing golden artifacts and compare")
    ap.add_argument("--check-hex", action="store_true", help="also compare hex listing with golden")
    ap.add_argument("--check-trace", action="store_true", help="also compare trace with golden (strict)")
    ap.add_argument("--fail-fast", action="store_true", help="stop at first mismatch with non-zero exit code")
    args = ap.parse_args()

    out_dir = (REPO_ROOT / args.out_dir).resolve()
    tests = discover_tests(REPO_ROOT)
    if args.only:
        names = set(args.only)
        tests = [t for t in tests if t["name"] in names]

    def verify_one(name: str, src: Path, sched: Optional[Path], ticks: int) -> bool:
        gdir = out_dir / name
        ok = True
        # compile fresh
        comp = compile_alg(src)
        fresh_hex: str = comp["hex"]  # type: ignore
        fresh_blob: bytes = comp["blob"]  # type: ignore
        # use golden schedule if exists
        gsched = gdir / "schedule.txt"
        use_sched = gsched if gsched.exists() else (sched if sched and sched.exists() else None)
        schedule = parse_schedule(str(use_sched)) if use_sched else []
        # run fresh
        trace_tmp = gdir / "trace.tmp.txt"
        out = run_machine(str(gdir / "program.bin"), schedule, 1024, ticks, trace=args.check_trace, trace_file=str(trace_tmp) if args.check_trace else None)
        fresh_out = format_outputs(out)
        # compare outputs
        expected_out = (gdir / "out.txt").read_text(encoding="utf-8") if (gdir / "out.txt").exists() else ""
        if fresh_out != expected_out:
            print(f"[mismatch][{name}] out.txt differs")
            for line in difflib.unified_diff(expected_out.splitlines(), fresh_out.splitlines(), fromfile="golden/out.txt", tofile="fresh/out.txt", lineterm=""):
                print(line)
            ok = False
        # compare hex optionally
        if args.check_hex:
            expected_hex = (gdir / "program.hex").read_text(encoding="utf-8") if (gdir / "program.hex").exists() else ""
            if fresh_hex != expected_hex:
                print(f"[mismatch][{name}] program.hex differs")
                for line in difflib.unified_diff(expected_hex.splitlines(), fresh_hex.splitlines(), fromfile="golden/program.hex", tofile="fresh/program.hex", lineterm=""):
                    print(line)
                ok = False
        # compare trace optionally
        if args.check_trace and (gdir / "trace.txt").exists():
            expected_trace = (gdir / "trace.txt").read_text(encoding="utf-8")
            fresh_trace = trace_tmp.read_text(encoding="utf-8") if trace_tmp.exists() else ""
            if fresh_trace != expected_trace:
                print(f"[mismatch][{name}] trace.txt differs")
                ok = False
        # cleanup temp
        if trace_tmp.exists():
            try:
                trace_tmp.unlink()
            except OSError:
                pass
        return ok

    any_failed = False
    for t in tests:
        name = t["name"]  # type: ignore
        src = Path(t["src"])  # type: ignore
        sched = Path(t["sched"]) if t["sched"] else None  # type: ignore
        ticks = int(args.ticks) if args.ticks is not None else int(t["ticks"])  # type: ignore
        if args.verify:
            print(f"[verify] {name}")
            ok = verify_one(name, src, sched, ticks)
            if not ok:
                any_failed = True
                if args.fail_fast:
                    sys.exit(1)
        else:
            print(f"[golden] Generating {name} → {out_dir / name}")
            generate_golden(name, src, out_dir, sched, ticks)

    if args.verify:
        if any_failed:
            sys.exit(1)
        print("[verify] all tests OK")


if __name__ == "__main__":
    main()


