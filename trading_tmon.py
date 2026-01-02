import json
import time
import uuid
from t_tech.invest import Client, Quotation
from t_tech.invest.schemas import InstrumentIdType, OrderDirection, OrderExecutionReportStatus, OrderType
from _token import TOKEN
from _logging import *
from config import *


def dec_price(n) -> Decimal:
    return Decimal(str(n.units)) + Decimal(str(n.nano)) / Decimal('1000000000')

def normailze(data: dict):
    out = {}
    for k, v in data.items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out

def denormolize(data: dict):
    out = {}
    for k, v in data.items():
        if k == "price":
            out[k] = Decimal(v)
        elif k == "id":
            out[k] = str(v)
        else:
            out[k] = v
    return out

def save_to_json(path: str, data: dict):
    new_data = normailze(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)

def dec_to_quotation(dec: Decimal):
    n = float(dec)
    units = int(n)
    nano = int(round(n - units, 2) * 1000000000)
    return Quotation(units, nano)

configure_logging("trading_tmon.log")
def main():
    with Client(TOKEN) as client:
        try:
            accounts = client.users.get_accounts().accounts
        except Exception as e:
            logging.error(f"Getting account failed: {e}")
            return
        logging.info(f"Got accounts successfully")
        account = accounts[0]
        account_id = account.id
        logging.info(f"Using account: {accounts[0]}")

        portfolio = client.operations.get_portfolio(account_id=account_id)
        for pos in portfolio.positions:
            if pos.instrument_type != "etf":
                continue
            ticker = client.instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID,
                id=pos.instrument_uid
            ).instrument.ticker
            if ticker != "TMON@":
                continue

            cur_price = pos.current_price
            print(f"units: {cur_price.units}")
            print(type(cur_price.units))
            print(f"nano: {cur_price.nano}")
            print(type(cur_price.nano))

            ob = client.market_data.get_order_book(figi=pos.figi, depth=1)
            best_ask = dec_price(ob.asks[0].price)
            best_bid = dec_price(ob.bids[0].price)
            print(f"Best ask: {best_ask}")
            print(f"Best bid: {best_bid}")
            step = Decimal("0.01")
            quantity = pos.quantity.units
            if best_ask * quantity >= MAX_PRICE_TMON: # За сколько могу продать прямо сейчас
                continue

            if Path(TMON_PURCHASE_NAME).exists():
                purchase = denormolize(json.loads(Path(TMON_PURCHASE_NAME).read_text(encoding="utf-8")))
                purchase["price"] = Decimal(purchase["price"]).quantize(Decimal(DECIMAL_ACCURACY))
            else:
                purchase = {"price": Decimal(), "quantity": 0, "id": "", "time": time.time()}
                save_to_json(TMON_PURCHASE_NAME, purchase)
            if Path(TMON_SALE_NAME).exists():
                sale = denormolize(json.loads(Path(TMON_SALE_NAME).read_text(encoding="utf-8")))
            else:
                sale = {"price": Decimal(), "quantity": 0, "id": "", "time": time.time()}
                save_to_json(TMON_SALE_NAME, sale)

            if purchase["quantity"] == 0 and sale["quantity"] == 0:
                qty = 1
                buy_price = best_bid - step
                quot = dec_to_quotation(buy_price)
                print(f"{quot.units}, {quot.nano}")
                print(f"Buy price: {buy_price}")
                resp = client.orders.post_order(
                    figi=pos.figi,
                    quantity=qty,
                    direction=OrderDirection.ORDER_DIRECTION_BUY,
                    price=dec_to_quotation(buy_price),
                    account_id=account_id,
                    order_type=OrderType.ORDER_TYPE_LIMIT
                )
                purchase["quantity"] += qty
                purchase["id"] = resp.order_id
                purchase["price"] = best_bid - step
                save_to_json(TMON_PURCHASE_NAME, purchase)
                logging.info("Saved purchase to json")
            elif purchase["quantity"] == 0 and sale["quantity"] > 0:
                status = client.orders.get_order_state(
                    order_id=sale["id"],
                    account_id=account_id
                ).execution_report_status

                if status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL:
                    sale["quantity"] = 0
                    save_to_json(TMON_SALE_NAME, sale)
                    logging.info("Saved sale to json")
                elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
                    pass  # Пока что такого быть не может, так как один пай
                elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_NEW:
                    if time.time() - sale["time"] > TMON_WAIT_TIME:
                        client.orders.cancel_order(
                            order_id=sale["id"],
                            account_id=account_id
                        )
                        qty = 1
                        sell_price = max(best_ask, purchase["price"])
                        resp = client.orders.post_order(
                            figi=pos.figi,
                            account_id=account_id,
                            quantity=qty,
                            direction=OrderDirection.ORDER_DIRECTION_SELL,
                            price=dec_to_quotation(sell_price),
                            order_type=OrderType.ORDER_TYPE_LIMIT
                        )
                        sale["id"] = resp.order_id
                        save_to_json(TMON_SALE_NAME, sale)
            elif sale["quantity"] == 0 and purchase["quantity"] > 0:
                status = client.orders.get_order_state(
                    order_id=purchase["id"],
                    account_id=account_id
                ).execution_report_status

                if status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL:
                    # Купилось полностью
                    qty = 1
                    sell_price = max(best_ask, purchase["price"] + step)
                    sale["time"] = time.time()
                    resp = client.orders.post_order(
                        figi=pos.figi,
                        quantity=qty,
                        direction=OrderDirection.ORDER_DIRECTION_SELL,
                        price=dec_to_quotation(sell_price),
                        order_type=OrderType.ORDER_TYPE_LIMIT
                    )
                    sale["quantity"] += qty
                    sale["id"] = resp.order_id
                    sale["price"] = sell_price
                    purchase['quantity'] = 0
                    save_to_json(TMON_SALE_NAME, sale)
                    save_to_json(TMON_PURCHASE_NAME, purchase)
                elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
                    # Купилось частично
                    pass
                elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_NEW:
                    if best_bid > purchase["price"] + step:
                        client.orders.cancel_order(
                            account_id=account_id,
                            order_id=purchase["id"]
                        )
                        purchase["quantity"] = 0
                        save_to_json(TMON_PURCHASE_NAME, purchase)
            else:
                # И покупка не прошла, и продажа есть. Так нельзя и так опасно.
                logging.error("Dangerous situation happened!")
                client.orders.cancel_order(
                    account_id=account_id,
                    order_id=purchase["id"]
                )
                client.orders.cancel_order(
                    account_id=account_id,
                    order_id=sale["id"]
                )
                raise AssertionError("Dangerous situation!")


if __name__ == "__main__":
    while True:
        main()
        time.sleep(60)
