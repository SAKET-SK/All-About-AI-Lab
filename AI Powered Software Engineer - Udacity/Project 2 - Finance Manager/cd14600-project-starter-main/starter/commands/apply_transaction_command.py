# apply_transaction_command.py

from commands.command import ICommand
from transaction.transaction import Transaction
from transaction.transaction_category import TransactionCategory


class ApplyTransactionCommand(ICommand):
    """Command that applies a Transaction to a Balance and can reverse it."""

    _OPPOSITE = {
        TransactionCategory.INCOME: TransactionCategory.EXPENSE,
        TransactionCategory.EXPENSE: TransactionCategory.INCOME,
    }

    def __init__(self, balance, transaction):
        # The balance is injected, so the command never reaches for the
        # singleton itself and can be tested with any balance-like object.
        self._balance = balance
        self._transaction = transaction

    def execute(self):
        self._balance.apply_transaction(self._transaction)

    def undo(self):
        opposite = self._OPPOSITE[self._transaction.category]
        self._balance.apply_transaction(
            Transaction(self._transaction.amount, opposite)
        )