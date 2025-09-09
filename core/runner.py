from __future__ import annotations

from isa import decode

from .control_unit import ControlUnit
from .io import IOController, IOEvent


def run_machine(
    code_bin_path: str,
    input_schedule: list[IOEvent],
    data_words: int,
    tick_limit: int,
    trace: bool = False,
    trace_file: str | None = None,
) -> dict[int, list[int]]:
    with open(code_bin_path, "rb") as f:
        blob = f.read()
    code = decode(blob)
    io = IOController(schedule=input_schedule)
    cpu = ControlUnit(code, data_words=data_words, io=io, tick_limit=tick_limit)
    trace_out = None
    if trace:
        trace_out = open(trace_file, "w", encoding="utf-8") if trace_file else None
    try:
        while cpu.tick < cpu.tick_limit and not cpu._halted:
            if trace:
                line = f"t={cpu.tick} pc={cpu.pc} phase={cpu._phase} T={cpu.dp.t} S={cpu.dp.z} AR={cpu.dp.ar} zero={int(cpu.dp.zero)} sign={int(cpu.dp.sign)} in_isr={int(cpu.in_isr)}\n"
                if trace_out:
                    trace_out.write(line)
                else:
                    print(line, end="")
            cpu.step_tick()
    finally:
        if trace_out:
            trace_out.close()
    return io.out_dump()
