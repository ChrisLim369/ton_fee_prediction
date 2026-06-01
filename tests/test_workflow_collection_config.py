import re
from pathlib import Path

from schema import PROJECT_ROOT

HOURLY_WORKFLOW = PROJECT_ROOT / ".github/workflows/hourly_forecast_update.yml"
RETRAIN_WORKFLOW = PROJECT_ROOT / ".github/workflows/daily_model_retrain.yml"


def read_workflow(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def max_pages_cap(content: str) -> int:
    match = re.search(r"--max-pages-cap\s+(\d+)", content)
    assert match is not None
    return int(match.group(1))


def test_both_workflows_uncapped() -> None:
    for workflow in (HOURLY_WORKFLOW, RETRAIN_WORKFLOW):
        content = read_workflow(workflow)
        assert max_pages_cap(content) >= 50
        assert "--max-pages-per-window 50" in content
        assert "--sleep 0.15" in content


def test_r2_backup_step_is_safe() -> None:
    content = read_workflow(HOURLY_WORKFLOW)

    assert "name: Back up raw transaction snapshot to R2" in content
    assert "continue-on-error: true" in content
    assert "r2.cloudflarestorage.com" in content
    assert "raw/snapshots/" in content
    assert 'if [ -z "$R2_ACCOUNT_ID" ]' in content
    assert "R2_ACCOUNT_ID:" in content
    assert "R2_BUCKET:" in content
    assert "AWS_ACCESS_KEY_ID:" in content
    assert "AWS_SECRET_ACCESS_KEY:" in content


def test_no_r2_step_in_retrain() -> None:
    content = read_workflow(RETRAIN_WORKFLOW)

    assert "name: Back up raw transaction snapshot to R2" not in content
    assert "r2.cloudflarestorage.com" not in content
