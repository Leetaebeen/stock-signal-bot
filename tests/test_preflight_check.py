from pathlib import Path

from app.tools.preflight_check import _configured_symbols, _mask, _check_state_path


def test_mask_hides_sensitive_values():
    assert _mask(None) == "missing"
    assert _mask("1234") == "****"
    assert _mask("abcdef") == "ab***ef"


def test_configured_symbols_dedupes_env_and_file(tmp_path: Path):
    symbol_file = tmp_path / "symbols.txt"
    symbol_file.write_text("NVDA\nHOOD\n", encoding="utf-8")

    assert _configured_symbols("nvda,tsla", str(symbol_file)) == ["NVDA", "TSLA", "HOOD"]


def test_check_state_path_creates_parent(tmp_path: Path):
    state_path = tmp_path / "nested" / "positions.json"

    result = _check_state_path(str(state_path))

    assert result.status == "OK"
    assert state_path.parent.exists()
