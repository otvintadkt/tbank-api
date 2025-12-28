import os
from datetime import datetime, timedelta, timezone
from t_tech.invest import Client
from t_tech.invest.schemas import OperationState
from t_tech.invest.schemas import OperationType
from _token import TOKEN

def main():
    with Client(TOKEN) as client:

        # 1. Получаем счета
        accounts = client.users.get_accounts().accounts
        if not accounts:
            print("Нет счетов")
            return

        account = accounts[0]
        account_id = account.id
        print(f"Используем счёт: {account.name} ({account_id})")

        # 2. Период (пример: последний год)
        now = datetime.now(timezone.utc)
        year_ago = now - timedelta(days=365)

        # 3. Получаем операции
        operations = client.operations.get_operations(
            account_id=account_id,
            from_=year_ago,
            to=now,
            state=OperationState.OPERATION_STATE_EXECUTED,
        ).operations

        print(f"Операций: {len(operations)}")

        # 4. Печатаем несколько операций
        for op in operations[:10]:
            print(
                op.date,
                OperationType(op.operation_type).name,
                op.payment.units,
                op.payment.currency,
                op.figi,
            )


if __name__ == "__main__":
    main()
