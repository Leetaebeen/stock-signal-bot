from pathlib import Path

from app.config import get_settings
from app.universe.nasdaq_trader import download_us_symbol_universe, format_symbol_file


def main() -> None:
    settings = get_settings()
    output_path = Path(settings.us_symbols_path or "data/us_symbols.txt")
    symbols = download_us_symbol_universe()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_symbol_file(symbols), encoding="utf-8")
    cursor_path = Path(settings.toss_scan_cursor_path)
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text("0", encoding="utf-8")
    print(f"saved={output_path}")
    print(f"symbols={len(symbols)}")
    print(f"cursor_reset={cursor_path}")


if __name__ == "__main__":
    main()
