from pathlib import Path


DEFAULT_US_SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "TSLA",
    "AMD",
    "AVGO",
    "GOOGL",
    "GOOG",
    "SMCI",
    "PLTR",
    "MSTR",
    "COIN",
    "MARA",
    "RIOT",
    "IONQ",
    "SOUN",
    "RGTI",
    "QBTS",
    "HOOD",
    "SOFI",
    "UPST",
    "BBAI",
    "AI",
    "SERV",
    "ACHR",
    "JOBY",
    "RKLB",
    "ASTS",
    "LUNR",
    "HIMS",
    "CRWV",
    "MU",
    "TSM",
    "ARM",
    "MRVL",
    "DELL",
    "ORCL",
    "CRWD",
]


def load_us_symbols(path: str | None = None) -> list[str]:
    if not path:
        return DEFAULT_US_SYMBOLS.copy()

    symbol_path = Path(path)
    if not symbol_path.exists():
        return DEFAULT_US_SYMBOLS.copy()

    symbols: list[str] = []
    seen: set[str] = set()
    for line in symbol_path.read_text(encoding="utf-8").splitlines():
        symbol = line.split("#", 1)[0].strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols or DEFAULT_US_SYMBOLS.copy()
