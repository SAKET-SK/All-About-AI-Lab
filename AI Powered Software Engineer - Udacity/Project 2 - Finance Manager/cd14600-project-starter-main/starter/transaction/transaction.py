# transaction.py

from transaction.transaction_category import TransactionCategory


class Transaction:
    """Represents a financial transaction with an amount and category."""

    def __init__(self, amount, category: TransactionCategory):
        self.amount = amount
        self.category = category

    def __str__(self):
        return f"Transaction(${self.amount}, category='{self.category}')"

    def __repr__(self):
        return f"Transaction({self.amount!r}, {self.category!r})"

    def __eq__(self, other):
        if not isinstance(other, Transaction):
            return NotImplemented
        return (self.amount, self.category) == (other.amount, other.category)

    def __hash__(self):
        # Defining __eq__ removes the default __hash__, so restore it.
        return hash((self.amount, self.category))