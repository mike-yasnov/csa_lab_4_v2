from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class IOEvent:
    tick: int
    port: int
    value: int


class IOController:
    """Контроллер портов с расписанием событий (trap)."""

    def __init__(self, schedule: list[IOEvent] | None = None):
        self._in_queues: dict[int, list[int]] = {}
        self._out_queues: dict[int, list[int]] = {}
        self._schedule: dict[int, list[IOEvent]] = {}
        if schedule:
            for ev in schedule:
                self._schedule.setdefault(ev.tick, []).append(ev)

        self._pending_irq: int | None = None

    def on_tick(self, t: int):
        for ev in self._schedule.get(t, []):
            self._in_queues.setdefault(ev.port, []).append(ev.value)
            if self._pending_irq is None:
                self._pending_irq = ev.port

    def irq_pending(self) -> int | None:
        return self._pending_irq

    def ack_irq(self):
        self._pending_irq = None

    def read_port(self, port: int) -> int:
        q = self._in_queues.get(port, [])
        if not q:
            return 0
        return q.pop(0)

    def write_port(self, port: int, value: int):
        self._out_queues.setdefault(port, []).append(value)

    def out_dump(self) -> dict[int, list[int]]:
        return {p: list(buf) for p, buf in self._out_queues.items()}
