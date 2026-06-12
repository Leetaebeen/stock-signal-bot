from app.universe.nasdaq_trader import _dedupe_symbols, ListedSymbol, parse_nasdaq_listed, parse_other_listed


def test_parse_nasdaq_listed_excludes_etf_units_and_tests():
    text = "\n".join(
        [
            "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares",
            "AAPL|Apple Inc. - Common Stock|Q|N|N|40|N|N",
            "AAPU|Direxion Daily AAPL Bull 2X ETF|G|N|N|100|Y|N",
            "AACB|Artius II Acquisition Inc. - Class A Ordinary Shares|G|N|D|100|N|N",
            "ABCDU|ABCD Corp - Unit|G|N|N|100|N|N",
            "TEST|Test Co - Common Stock|Q|Y|N|100|N|N",
            "File Creation Time: 0612202600:00|||||||",
        ]
    )

    symbols = parse_nasdaq_listed(text)

    assert [item.symbol for item in symbols] == ["AAPL"]
    assert symbols[0].exchange == "NASDAQ"


def test_parse_other_listed_maps_exchange_and_excludes_etf():
    text = "\n".join(
        [
            "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol",
            "IBM|International Business Machines Corporation Common Stock|N|IBM|N|100|N|IBM",
            "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY",
            "ABC.W|ABC Corp Warrant|A|ABC.W|N|100|N|ABC.W",
        ]
    )

    symbols = parse_other_listed(text)

    assert [item.symbol for item in symbols] == ["IBM"]
    assert symbols[0].exchange == "NYSE"


def test_priority_symbols_are_sorted_first():
    symbols = _dedupe_symbols(
        [
            ListedSymbol("ZZZ", "Zzz Corp", "NASDAQ"),
            ListedSymbol("NVDA", "NVIDIA", "NASDAQ"),
            ListedSymbol("AAPL", "Apple", "NASDAQ"),
        ]
    )

    assert [item.symbol for item in symbols] == ["NVDA", "AAPL", "ZZZ"]
