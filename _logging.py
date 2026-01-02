from pathlib import Path
import logging

def configure_logging(filename : str):
    BASE_DIR = Path(__file__).parent
    LOG_FILE = BASE_DIR / filename
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8"
    )
