# transaction_adapter.py

from transaction.transaction import Transaction
from transaction.transaction_category import TransactionCategory


class TransactionAdapter:
    """
    Adapter that makes a third-party transaction usable by the app.

    The external object (for example ExternalFreelanceIncome) exposes
    ``amount`` and ``typ`` attributes plus extra fields the app does not
    model. The adapter translates it into the app's own Transaction.
    """

    # Maps the external system's type labels onto the app's enum.
    _CATEGORY_BY_EXTERNAL_TYPE = {
        "income": TransactionCategory.INCOME,
        "expense": TransactionCategory.EXPENSE,
    }

    def __init__(self, external_transaction):
        self.external_transaction = external_transaction

    def to_transaction(self):
        """Convert an external transaction to a standard Transaction."""
        external_type = getattr(self.external_transaction, "typ", None)
        category = self._CATEGORY_BY_EXTERNAL_TYPE.get(
            str(external_type).lower()
        )
        if category is None:
            raise ValueError(
                f"Unsupported external transaction type: {external_type!r}"
            )
        return Transaction(self.external_transaction.amount, category)