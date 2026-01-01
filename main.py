from datetime import datetime, timezone
from t_tech.invest import Client
from t_tech.invest.schemas import InstrumentIdType
from _token import TOKEN
import pandas as pd
from config import *
from pathlib import Path
import json
from decimal import Decimal
import sys
from os import getenv
import logging

print(getenv("PYCHARM"))
print(getenv("PYCHARM_HOSTED"))
autorun = "--autorun" in sys.argv

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "run.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)


def main():
    logging.info("Script started")
    if Path(TABLE_NAME).exists():
        df = pd.read_csv(TABLE_NAME)
        df["datetime"] = pd.to_datetime(df["datetime"])
    else:
        df = pd.DataFrame(
            columns=["datetime", "figi", "name", "quantity", "price", "value", "dividends"]
        )

    with Client(TOKEN) as client:
        # 1. Получаем счета
        accounts = client.users.get_accounts().accounts
        if not accounts:
            print("Нет счетов")
            logging.info("No accounts found")
            return

        account = accounts[0]
        account_id = account.id
        print(f"Используем счёт: {account.name} ({account_id})")
        logging.info(f"Found account: {account.name} ({account_id})")
        now = datetime.now(timezone.utc)
        new_rows = []

        if Path(INSTRUMENT_CACHE_NAME).exists():
            instrument_cache = json.loads(Path(INSTRUMENT_CACHE_NAME).read_text(encoding="utf-8"))
        else:
            instrument_cache = {}

        # 3. Текущие акции в портфеле
        portfolio = client.operations.get_portfolio(account_id=account_id)
        for pos in portfolio.positions:
            if pos.instrument_type != "share":
                continue
            qty = pos.quantity.units
            curr_price = (
                Decimal(pos.current_price.units) +
                Decimal(pos.current_price.nano) / Decimal(1000000000)
            ).quantize(Decimal("0.01"))

            uid = pos.instrument_uid
            if uid not in instrument_cache:
                uid_name = client.instruments.get_instrument_by(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID,
                    id=pos.instrument_uid,
                )
                instrument_cache[uid] = uid_name.instrument.name

            new_rows.append({
                "datetime": now,
                "figi": pos.figi,
                "name": instrument_cache[uid],
                "quantity": qty,
                "price": curr_price,
                "value": (Decimal(qty) * curr_price).quantize(Decimal("0.01")),
                "dividends": 0.0
            })
            print(
                pos.figi,
                instrument_cache[uid],
                qty,
                curr_price
            )
        if new_rows:
            total_value = sum(row["value"] for row in new_rows)
            total_qty = sum(row["quantity"] for row in new_rows)
            total_dividends = sum(row["dividends"] for row in new_rows)

            new_rows.append({
                "datetime": now,
                "figi": None,
                "name": "Сумма",
                "quantity": total_qty,
                "price": None,
                "value": total_value,
                "dividends": total_dividends
            })
            new_rows.append({
                "datetime": None,
                "figi": None,
                "name": None,
                "quantity": None,
                "price": None,
                "value": None,
                "dividends": None
            })
            df_new = pd.DataFrame(new_rows)
            if df.empty:
                df = df_new
            else:
                df = pd.concat([df, df_new], ignore_index=True)
            logging.info("Saved new dataframe successfully")
    try:
        if autorun:
            df.to_csv(AUTORUN_TABLE_NAME, index=False)
        else:
            df.to_csv(TABLE_NAME, index=False)
    except Exception:
        logging.error(f"ERROR: Failed to save {TABLE_NAME}", exc_info=True)
        sys.exit(1)
    logging.info(f"{TABLE_NAME} saved successfully")

    try:
        Path(INSTRUMENT_CACHE_NAME).write_text(
            json.dumps(instrument_cache, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        logging.error(f"ERROR: failed to save instrument cache", exc_info=True)
        sys.exit(1)
    logging.info(f"Instrument cache saved successfully")


if __name__ == "__main__":
    main()
