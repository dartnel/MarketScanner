import logging
import time
from binance_client import get_klines, COMPLETED_KLINES_COUNT
from calculations import calculate_price_change
from config import MIN_1H_PRICE_CHANGE

logger = logging.getLogger(__name__)

def check_price_momentum(symbol, klines):
    """
    Check whether the symbol increased by at least
    MIN_1H_PRICE_CHANGE during the last hour.
    """

    if len(klines) < 12:
        logger.warning("%s: Not enough completed klines", symbol)
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

        logger.debug("Checking %s...", symbol)

        klines = get_klines(symbol)

        if klines is None:
            continue
        if len(klines) < COMPLETED_KLINES_COUNT:
            logger.warning("%s: Not enough completed klines", symbol)
            continue

        result = check_price_momentum(
            symbol,
            klines,
        )

        if result is not None:
            logger.info("%s: %.2f%%", symbol, result["price_change"])

            if result["condition_passed"]:
                passed_symbols.append(result)

        # Small delay before the next Binance API request
        if index < len(top_symbols) - 1:
            time.sleep(0.15)

    return passed_symbols