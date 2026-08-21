import logging
import html
import os
import time

import requests

from binance_client import (
    get_filtered_symbols,
    fetch_top_volume_symbols,
)
from scanner import scan_symbols

from config import MIN_1H_PRICE_CHANGE, ALERT_COOLDOWN_SECONDS

logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CONFIGURED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

INTERVAL_SECONDS = int(
    os.getenv("TOP_INTERVAL_SECONDS", "300")
)

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def telegram_request(method, **kwargs):
    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        json=kwargs,
        timeout=40,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            result.get(
                "description",
                "Telegram API error",
            )
        )

    return result["result"]


def get_top_symbols():
    """
    Get the configured number of USDT trading pairs
    with the highest 24-hour quote volume.
    """

    filtered_symbols = get_filtered_symbols()

    if not filtered_symbols:
        raise RuntimeError(
            "Failed to get filtered symbols"
        )

    top_symbols = fetch_top_volume_symbols(
        filtered_symbols
    )

    if not top_symbols:
        raise RuntimeError(
            "Failed to get top symbols"
        )

    return top_symbols


def send_alert(chat_id, results):
    """
    Send one Telegram alert for all symbols that passed
    Condition 1.
    """
    symbol_lines = []

    for result in results:
        symbol = html.escape(result["symbol"])
        starting_price = result["starting_price"]
        ending_price = result["ending_price"]
        price_change = result["price_change"]

        symbol_lines.append(
            f"<b>{symbol}</b>: +{price_change:.2f}%\n"
            f"Starting: {starting_price} | Ending: {ending_price}"
        )

    message = (
        "🚨 <b>Market Scanner Alert</b>\n\n"
        + "\n\n".join(symbol_lines)
        + "\n\n"
        "✅ <b>Condition 1 passed</b>\n"
        f"Price increased by at least {MIN_1H_PRICE_CHANGE:g}% "
        "during the last hour."
    )

    telegram_request(
        "sendMessage",
        chat_id=chat_id,
        text=message,
        parse_mode="HTML",
    )

    logger.info("Alert sent for %d symbol(s)", len(results))


def scan_and_send_alerts(chat_id, last_alert_times):
    """
    Get top symbols, scan them, and send alerts for symbols
    that passed Condition 1, skipping any symbol still within
    its alert cooldown.
    """
    logger.info("Starting market scan...")

    top_symbols = get_top_symbols()

    passed_symbols = scan_symbols(top_symbols)

    if passed_symbols is None:
        print("Scan failed — no alerts sent")
        return
    if not passed_symbols:
        logger.info("No symbols passed Condition 1")
        return

    logger.info("%d symbol(s) passed Condition 1", len(passed_symbols))

    now = time.monotonic()
    alert_results = []

    for result in passed_symbols:
        symbol = result["symbol"]
        last_alert = last_alert_times.get(symbol)

        if last_alert is not None and (now - last_alert) < ALERT_COOLDOWN_SECONDS:
            remaining = ALERT_COOLDOWN_SECONDS - (now - last_alert)
            logger.info("%s: skipping alert, cooldown (%.0fs left)", symbol, remaining)
            continue

        alert_results.append(result)

    if not alert_results:
        logger.info("No symbols eligible for an alert")
        return

    send_alert(chat_id, alert_results)

    for result in alert_results:
        symbol = result["symbol"]
        last_alert_times[symbol] = now

def run_bot():
    active_chat_id = CONFIGURED_CHAT_ID
    offset = None
    next_scan_time = 0
    last_alert_times = {}

    if active_chat_id:
        logger.info("Using configured chat_id: %s", active_chat_id)
    else:
        logger.info("Send /start to the bot to detect your chat ID")

    while True:
        try:
            current_time = time.monotonic()

            # Run scheduled market scan
            if (
                active_chat_id
                and current_time >= next_scan_time
            ):
                try:
                    scan_and_send_alerts(
                        active_chat_id, last_alert_times
                    )

                    next_scan_time = (
                        current_time
                        + INTERVAL_SECONDS
                    )

                except Exception as error:
                    logger.error("Market scan failed: %s", error)

                    # Retry after 60 seconds
                    next_scan_time = (
                        current_time + 60
                    )

            # Check for Telegram updates
            params = {"timeout": 25}

            if offset is not None:
                params["offset"] = offset

            updates = telegram_request(
                "getUpdates",
                **params,
            )

            for update in updates:
                offset = (
                    update["update_id"] + 1
                )

                message = update.get(
                    "message",
                    {},
                )

                text = message.get(
                    "text",
                    "",
                ).strip()

                chat_id = str(
                    message.get(
                        "chat",
                        {},
                    ).get(
                        "id",
                        "",
                    )
                )

                if not chat_id:
                    continue

                if (
                    CONFIGURED_CHAT_ID
                    and chat_id
                    != CONFIGURED_CHAT_ID
                ):
                    continue

                command = (
                    text.split()[0]
                    .split("@")[0]
                    .lower()
                    if text
                    else ""
                )

                if command == "/start":

                    if not active_chat_id and not CONFIGURED_CHAT_ID:
                        active_chat_id = chat_id

                        logger.info("Detected chat_id: %s", active_chat_id)

                    telegram_request(
                        "sendMessage",
                        chat_id=chat_id,
                        text=(
                            "The Market Scanner is running.\n\n"
                            "It checks the top trading pairs "
                            "and sends an alert when a symbol "
                            f"increases by at least {MIN_1H_PRICE_CHANGE:g}% "
                            "during the last hour.\n\n"
                            "Use /scan to start a manual scan."
                        ),
                    )

                    # Run scan immediately
                    scan_and_send_alerts(chat_id, last_alert_times)

                    next_scan_time = (
                        time.monotonic()
                        + INTERVAL_SECONDS
                    )

                elif command == "/scan":

                    telegram_request(
                        "sendMessage",
                        chat_id=chat_id,
                        text="Starting manual market scan...",
                    )

                    scan_and_send_alerts(chat_id, last_alert_times)

                    # Reset scheduled scan timer
                    next_scan_time = (
                        time.monotonic()
                        + INTERVAL_SECONDS
                    )

        except KeyboardInterrupt:
            logger.info("Bot stopped")
            break

        except Exception as error:
            logger.error("Bot error: %s", error)

            time.sleep(5)