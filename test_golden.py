"""Golden тесты транслятора и машины.

Тесты используют существующую структуру golden/ с meta.json файлами.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


def get_golden_tests():
    """Собирает все golden тесты из директории golden/."""
    golden_dir = Path("golden")
    tests = []

    for test_dir in golden_dir.iterdir():
        if test_dir.is_dir():
            meta_file = test_dir / "meta.json"
            if meta_file.exists():
                tests.append(test_dir.name)

    return tests


@pytest.mark.parametrize("test_name", get_golden_tests())
def test_golden(test_name):
    """Запускает golden тест для указанной программы."""
    test_dir = Path("golden") / test_name
    meta_file = test_dir / "meta.json"

    # Читаем метаданные
    with open(meta_file) as f:
        meta = json.load(f)

    # Файлы теста
    program_file = test_dir / "program.alg"
    schedule_file = test_dir / "schedule.txt"
    trace_file = test_dir / "trace.txt"
    hex_file = test_dir / "program.hex"
    bin_file = test_dir / "program.bin"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Компилируем программу
        tmp_bin = Path(tmpdir) / "program.bin"
        tmp_hex = Path(tmpdir) / "program.hex"

        result = subprocess.run(
            ["python3", "-m", "translator", str(program_file), str(tmp_bin), "--hex", str(tmp_hex)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Проверяем hex файл
        if hex_file.exists():
            with open(hex_file) as f:
                expected_hex = f.read()
            with open(tmp_hex) as f:
                actual_hex = f.read()
            assert actual_hex == expected_hex, f"Hex output mismatch for {test_name}"

        # Проверяем бинарный файл
        if bin_file.exists():
            with open(bin_file, "rb") as f:
                expected_bin = f.read()
            with open(tmp_bin, "rb") as f:
                actual_bin = f.read()
            assert actual_bin == expected_bin, f"Binary output mismatch for {test_name}"

        # Запускаем программу если есть trace
        if trace_file.exists() and schedule_file.exists():
            # Создаем временный файл для трейса
            tmp_trace = Path(tmpdir) / "trace.txt"

            # Формируем команду
            cmd = [
                "python3",
                "machine_cli.py",
                str(tmp_bin),
                "--trace",
                "--trace-file",
                str(tmp_trace),
                "--ticks",
                str(meta.get("ticks", 10000)),
                "--data-words",
                str(meta.get("data_words", 1024)),
            ]

            if schedule_file.exists():
                cmd.extend(["--schedule", str(schedule_file)])

            result = subprocess.run(cmd, capture_output=True, text=True)

            assert result.returncode == 0, f"Machine execution failed: {result.stderr}"

            # Читаем и сравниваем трейсы
            with open(trace_file) as f:
                expected_trace = f.read().strip()
            with open(tmp_trace) as f:
                actual_trace = f.read().strip()

            # Сравниваем построчно для лучшей диагностики
            expected_lines = expected_trace.split("\n")
            actual_lines = actual_trace.split("\n")

            for i, (expected, actual) in enumerate(zip(expected_lines, actual_lines)):
                assert expected == actual, f"Trace mismatch at line {i+1}:\nExpected: {expected}\nActual: {actual}"

            assert len(actual_lines) == len(
                expected_lines
            ), f"Trace length mismatch: expected {len(expected_lines)}, got {len(actual_lines)}"


def test_update_golden():
    """Обновляет golden файлы (запускается с флагом --update-goldens)."""
    import sys

    if "--update-goldens" not in sys.argv:
        pytest.skip("Not updating golden files")

    golden_dir = Path("golden")

    for test_dir in golden_dir.iterdir():
        if not test_dir.is_dir():
            continue

        meta_file = test_dir / "meta.json"
        if not meta_file.exists():
            continue

        print(f"Updating golden test: {test_dir.name}")

        with open(meta_file) as f:
            meta = json.load(f)

        program_file = test_dir / "program.alg"
        if not program_file.exists():
            continue

        # Компилируем
        bin_file = test_dir / "program.bin"
        hex_file = test_dir / "program.hex"

        result = subprocess.run(
            ["python3", "-m", "translator", str(program_file), str(bin_file), "--hex", str(hex_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  Failed to compile: {result.stderr}")
            continue

        # Запускаем если есть schedule
        schedule_file = test_dir / "schedule.txt"
        trace_file = test_dir / "trace.txt"

        if schedule_file.exists():
            cmd = [
                "python3",
                "machine_cli.py",
                str(bin_file),
                "--trace",
                "--trace-file",
                str(trace_file),
                "--ticks",
                str(meta.get("ticks", 10000)),
                "--data-words",
                str(meta.get("data_words", 1024)),
                "--schedule",
                str(schedule_file),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"  Failed to run: {result.stderr}")
            else:
                print(f"  Updated: {trace_file}")
