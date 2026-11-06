import unittest
from transaction.transaction import Transaction
from transaction.transaction_category import TransactionCategory


class TestTransaction(unittest.TestCase):

    def test_transaction_creation(self):
        t = Transaction(100, TransactionCategory.EXPENSE)
        self.assertEqual(t.amount, 100)
        self.assertEqual(t.category, TransactionCategory.EXPENSE)

    def test_transaction_str(self):
        t = Transaction(50, TransactionCategory.INCOME)
        self.assertEqual(
            str(t), "Transaction($50, category='TransactionCategory.INCOME')")

    def test_transaction_equality(self):
        t1 = Transaction(20, TransactionCategory.EXPENSE)
        t2 = Transaction(20, TransactionCategory.EXPENSE)
        t3 = Transaction(30, TransactionCategory.EXPENSE)
        self.assertEqual(t1, t2)
        self.assertNotEqual(t1, t3)

    def test_transaction_not_equal_when_category_differs(self):
        self.assertNotEqual(
            Transaction(20, TransactionCategory.INCOME),
            Transaction(20, TransactionCategory.EXPENSE),
        )

    def test_transaction_not_equal_to_other_types(self):
        self.assertNotEqual(Transaction(20, TransactionCategory.INCOME), 20)

    def test_equal_transactions_have_equal_hashes(self):
        t1 = Transaction(20, TransactionCategory.EXPENSE)
        t2 = Transaction(20, TransactionCategory.EXPENSE)
        self.assertEqual(hash(t1), hash(t2))

    def test_category_enum_members(self):
        self.assertEqual(
            {c.name for c in TransactionCategory}, {"INCOME", "EXPENSE"}
        )


if __name__ == "__main__":
    unittest.main()