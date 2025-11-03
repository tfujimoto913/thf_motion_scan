import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from thresholds_editor.safeguards import (
    ConfirmationError,
    EnvironmentError,
    ensure_dev_environment,
    require_apply_confirmation,
    should_block_apply,
)


def test_ensure_dev_environment_blocks_non_dev():
    with pytest.raises(EnvironmentError):
        ensure_dev_environment("prod")


def test_require_apply_confirmation():
    with pytest.raises(ConfirmationError):
        require_apply_confirmation("apply")
    require_apply_confirmation("APPLY")


def test_should_block_apply_limit():
    assert should_block_apply(0.4) is True
    assert should_block_apply(0.2) is False
    assert should_block_apply(0.4, admin_override=True) is False
