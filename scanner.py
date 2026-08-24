import logging
import time
from binance_client import get_klines, get_hourly_klines
from calculations import calculate_price_change, calculate_volume_spike
from config import (
    MIN_1H_PRICE_CHANGE,
    VOLUME_BASELINE_HOURS,
    VOLUME_SPIKE_MULTIPLIER,
)

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


def check_volume_spike(symbol, klines, hourly_klines):
    """
    Check whether the trailing 1-hour volume (last 12 completed
    5m candles) is at least VOLUME_SPIKE_MULTIPLIER times the
    average of the prior VOLUME_BASELINE_HOURS completed hours.
    """
    if len(klines) < 12:
        logger.info("%s: Not enough 5m candles for volume check", symbol)
        return None

    if len(hourly_klines) < VOLUME_BASELINE_HOURS:
        logger.info("%s: Not enough hourly candles for volume baseline", symbol)
        return None

    current_hour_volume = sum(float(k[5]) for k in klines)

    baseline_avg_volume = sum(
        float(k[5]) for k in hourly_klines
    ) / len(hourly_klines)

    spike_ratio = calculate_volume_spike(current_hour_volume, baseline_avg_volume)
    condition_passed = spike_ratio >= VOLUME_SPIKE_MULTIPLIER

    return {
        "symbol": symbol,
        "current_hour_volume": current_hour_volume,
        "baseline_avg_volume": baseline_avg_volume,
        "spike_ratio": spike_ratio,
        "condition_passed": condition_passed,
    }


def scan_symbols(top_symbols):
    passed_symbols = []

    for index, ticker in enumerate(top_symbols):
        symbol = ticker.get("symbol")
        if not symbol:
            continue

        logger.info("Checking %s...", symbol)

        klines = get_klines(symbol)
        hourly_klines = get_hourly_klines(symbol)

        price_result = check_price_momentum(
            symbol,
            klines,
        )
        volume_result = check_volume_spike(
            symbol,
            klines,
            hourly_klines,
        )

        if price_result is not None and volume_result is not None:
            logger.info(
                "%s: %.2f%% price, %.2fx volume",
                symbol,
                price_result["price_change"],
                volume_result["spike_ratio"],
            )

            if (
                price_result["condition_passed"]
                and volume_result["condition_passed"]
            ):
                passed_symbols.append(
                    {**price_result, **volume_result}
                )

        # Small delay before the next Binance API request
        if index < len(top_symbols) - 1:
            time.sleep(0.15)

    return passed_symbols