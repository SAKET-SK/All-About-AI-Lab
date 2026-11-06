# balance.py

import math

from transaction.transaction_category import TransactionCategory


class Balance:
    """Singleton to track the balance and notify observers of changes."""

    _instance = None

    def __init__(self):
        """Initialize the balance. Prevent direct instantiation."""
        if Balance._instance is not None:
            raise RuntimeError(
                "Balance is a singleton. Use Balance.get_instance()."
            )
        Balance._instance = self
        self._net_balance = 0.0
        self._observers = []

    @classmethod
    def get_instance(cls):
        """Return the single shared Balance, creating it on first use."""
        if Balance._instance is None:
            Balance()
        return Balance._instance

    # --- Observer pattern: subject side --------------------------------

    def register_observer(self, observer):
        """Subscribe an observer to balance changes (ignores duplicates)."""
        if not callable(getattr(observer, "update", None)):
            raise TypeError("Observer must implement an update() method.")
        if observer not in self._observers:
            self._observers.append(observer)

    def unregister_observer(self, observer):
        """Unsubscribe an observer. Unknown observers are ignored."""
        if observer in self._observers:
            self._observers.remove(observer)

    def clear_observers(self):
        """Remove every registered observer."""
        self._observers.clear()

    def _notify_observers(self, transaction):
        """Tell every observer the balance changed because of transaction."""
        for observer in list(self._observers):
            observer.update(self._net_balance, transaction)

    # --- Balance operations --------------------------------------------

    @staticmethod
    def _validate_amount(amount):
        """Raise ValueError unless amount is a positive, finite number."""
        is_number = (
            isinstance(amount, (int, float)) and not isinstance(amount, bool)
        )
        if not is_number or not math.isfinite(amount) or amount <= 0:
            raise ValueError("Amount must be a positive number.")

    def reset(self):
        """Reset the net balance to zero."""
        self._net_balance = 0.0

    def add_income(self, amount):
        """Add income to the balance."""
        self._validate_amount(amount)
        self._net_balance += amount

    def add_expense(self, amount):
        """Subtract expense from the balance."""
        self._validate_amount(amount)
        self._net_balance -= amount

    def apply_transaction(self, transaction):
        """
        Apply a Transaction object to update the balance.

        Observers are notified after the balance has changed.

        Args:
            transaction (Transaction): The transaction to apply.

        Raises:
            ValueError: If the category or amount is not supported.
        """
        category = transaction.category
        if category == TransactionCategory.INCOME:
            self.add_income(transaction.amount)
        elif category == TransactionCategory.EXPENSE:
            self.add_expense(transaction.amount)
        else:
            raise ValueError(f"Unsupported transaction category: {category!r}")
        self._notify_observers(transaction)

    def get_balance(self):
        """Get the current net balance."""
        return self._net_balance

    def summary(self):
        """Return a summary string of the net balance."""
        return f"Current balance: ${self._net_balance:.2f}"