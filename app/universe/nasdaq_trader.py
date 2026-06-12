from dataclasses import dataclass

import httpx


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
PRIORITY_SYMBOLS = {
    symbol: idx
    for idx, symbol in enumerate(
        [
            "NVDA",
            "AMD",
            "AVGO",
            "TSM",
            "ARM",
            "MU",
            "MRVL",
            "SMCI",
            "PLTR",
            "MSTR",
            "COIN",
            "MARA",
            "RIOT",
            "HOOD",
            "SOFI",
            "UPST",
            "IONQ",
            "SOUN",
            "RGTI",
            "QBTS",
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
            "TSLA",
            "META",
            "AAPL",
            "MSFT",
            "AMZN",
            "GOOGL",
            "GOOG",
        ]
    )
}


@dataclass(frozen=True)
class ListedSymbol:
    symbol: str
    name: str
    exchange: str


def download_us_symbol_universe(http_client: httpx.Client | None = None) -> list[ListedSymbol]:
    client = http_client or httpx.Client(timeout=20)
    listed: list[ListedSymbol] = []
    listed.extend(parse_nasdaq_listed(_get_text(client, NASDAQ_LISTED_URL)))
    listed.extend(parse_other_listed(_get_text(client, OTHER_LISTED_URL)))
    return _dedupe_symbols(listed)


def parse_nasdaq_listed(text: str) -> list[ListedSymbol]:
    symbols: list[ListedSymbol] = []
    for row in _parse_pipe_rows(text):
        symbol = row.get("Symbol", "").strip().upper()
        name = row.get("Security Name", "").strip()
        if not _is_common_stock_symbol(symbol, name, row.get("ETF"), row.get("Test Issue")):
            continue
        symbols.append(ListedSymbol(symbol=symbol, name=name, exchange="NASDAQ"))
    return symbols


def parse_other_listed(text: str) -> list[ListedSymbol]:
    symbols: list[ListedSymbol] = []
    for row in _parse_pipe_rows(text):
        symbol = row.get("ACT Symbol", "").strip().upper()
        name = row.get("Security Name", "").strip()
        exchange = _exchange_name(row.get("Exchange", ""))
        if not _is_common_stock_symbol(symbol, name, row.get("ETF"), row.get("Test Issue")):
            continue
        symbols.append(ListedSymbol(symbol=symbol, name=name, exchange=exchange))
    return symbols


def format_symbol_file(symbols: list[ListedSymbol]) -> str:
    lines = [
        "# Generated from Nasdaq Trader symbol directories.",
        "# symbol # exchange - name",
    ]
    for item in symbols:
        lines.append(f"{item.symbol} # {item.exchange} - {item.name}")
    return "\n".join(lines) + "\n"


def _get_text(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def _parse_pipe_rows(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header = lines[0].split("|")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        values = line.split("|")
        if len(values) != len(header):
            continue
        rows.append(dict(zip(header, values)))
    return rows


def _is_common_stock_symbol(symbol: str, name: str, etf: str | None, test_issue: str | None) -> bool:
    if not symbol or "$" in symbol:
        return False
    if etf == "Y" or test_issue == "Y":
        return False
    upper_name = name.upper()
    blocked_keywords = (
        " ACQUISITION",
        " BLANK CHECK",
        " SPAC",
        " SHELL COMPANY",
        " ETF",
        " ETN",
        " FUND",
        " WARRANT",
        " WARRANTS",
        " RIGHT",
        " RIGHTS",
        " UNIT",
        " UNITS",
        " PREFERRED",
        " PREFERENCE",
        " NOTE",
        " BOND",
        " DEBENTURE",
    )
    return not any(keyword in f" {upper_name} " for keyword in blocked_keywords)


def _exchange_name(value: str) -> str:
    value = value.strip().upper()
    if value == "N":
        return "NYSE"
    if value == "A":
        return "AMEX"
    if value == "P":
        return "NYSEARCA"
    if value == "Z":
        return "BATS"
    return value or "UNKNOWN"


def _dedupe_symbols(symbols: list[ListedSymbol]) -> list[ListedSymbol]:
    seen: set[str] = set()
    unique: list[ListedSymbol] = []
    for item in sorted(symbols, key=lambda row: (PRIORITY_SYMBOLS.get(row.symbol, 999_999), row.symbol)):
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        unique.append(item)
    return unique
