# main.py
import logging
from telegram_bot import run_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),                           # console
        logging.FileHandler("market_scanner.log"),         # file
    ],
)

def main():
    run_bot()

if __name__ == "__main__":
    main()