import unittest
from transaction.external_income_transaction import ExternalFreelanceIncome
from transaction.transaction_adapter import TransactionAdapter
from transaction.transaction import Transaction
from transaction.transaction_category import TransactionCategory


class TestTransactionAdapter(unittest.TestCase):

    def test_adapter_converts_freelance_income(self):
        ext_txn = ExternalFreelanceIncome(
            500, "INV-12345", "Website development")
        adapter = TransactionAdapter(ext_txn)
        txn = adapter.to_transaction()
        self.assertEqual(txn, Transaction(500, TransactionCategory.INCOME))

    def test_adapter_result_is_a_transaction_instance(self):
        ext_txn = ExternalFreelanceIncome(75.5, "INV-1", "Logo design")
        txn = TransactionAdapter(ext_txn).to_transaction()
        self.assertIsInstance(txn, Transaction)
        self.assertEqual(txn.amount, 75.5)

    def test_adapter_maps_expense_type(self):
        ext_txn = ExternalFreelanceIncome(10, "INV-2", "Refund")
        ext_txn.typ = "expense"
        txn = TransactionAdapter(ext_txn).to_transaction()
        self.assertEqual(txn.category, TransactionCategory.EXPENSE)

    def test_adapter_rejects_unknown_type(self):
        ext_txn = ExternalFreelanceIncome(10, "INV-3", "Mystery")
        ext_txn.typ = "barter"
        with self.assertRaises(ValueError):
            TransactionAdapter(ext_txn).to_transaction()

    def test_adapter_rejects_object_without_type(self):
        class Incomplete:
            amount = 10
        with self.assertRaises(ValueError):
            TransactionAdapter(Incomplete()).to_transaction()


if __name__ == "__main__":
    unittest.main()