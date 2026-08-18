import time
from binance_client import get_klines
from calculations import calculate_price_change
from config import MIN_1H_PRICE_CHANGE


def check_price_momentum(symbol, klines):
    """
    Check whether the symbol increased by at least
    MIN_1H_PRICE_CHANGE during the last hour.
    """

    if len(klines) < 12:
        print(f"{symbol}: Not enough completed klines")
        return None

    starting_price = float(klines[0][1])
    ending_price = float(klines[-1][4])

    price_change = calculate_price_change(
        starting_price,
        ending_price,
    )

    condition_passed = (
        price_change >= MIN_1H_PRICE_CHANGE
    )

    return {
        "symbol": symbol,
        "starting_price": starting_price,
        "ending_price": ending_price,
        "price_change": price_change,
        "condition_passed": condition_passed,
    }


def scan_symbols(top_symbols):
    passed_symbols = []

    for index, ticker in enumerate(top_symbols):
        symbol = ticker.get("symbol")

        if not symbol:
            continue

        print(f"Checking {symbol}...")

        klines = get_klines(symbol)

        if klines is None:
            return None

        if len(klines) < COMPLETED_KLINES_COUNT:
            print(f"{symbol}: Not enough completed klines")
            return None

        result = check_price_momentum(
            symbol,
            klines,
        )

        if result is not None:
            print(
                f"{symbol}: "
                f"{result['price_change']:.2f}%"
            )

            if result["condition_passed"]:
                passed_symbols.append(result)

        # Small delay before the next Binance API request
        if index < len(top_symbols) - 1:
            time.sleep(0.15)

    return passed_symbols