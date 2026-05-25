import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 30


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=TIMEOUT,
        check=False,
    )


def assert_success(args: list[str]) -> None:
    result = run_command(args)
    assert result.returncode == 0, result.stderr


def test_all_python_files_compile() -> None:
    python_files = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob("*.py"))
    assert python_files
    assert_success([sys.executable, "-m", "py_compile", *python_files])


def test_cli_help_commands() -> None:
    commands = [
        [sys.executable, "scripts/collect_transactions.py", "--help"],
        [sys.executable, "scripts/build_hourly_features.py", "--help"],
        [sys.executable, "src/update_data.py", "--help"],
        [sys.executable, "src/refresh_forecast_outputs.py", "--help"],
        [sys.executable, "src/train_model.py", "--help"],
        [sys.executable, "src/generate_forecast.py", "--help"],
    ]

    for command in commands:
        assert_success(command)


def test_telegram_bot_validate() -> None:
    assert_success([sys.executable, "src/telegram_bot.py", "--validate"])
