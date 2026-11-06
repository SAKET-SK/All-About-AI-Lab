import unittest
from balance.balance import Balance
from commands.apply_transaction_command import ApplyTransactionCommand
from commands.command import ICommand
from commands.command_manager import CommandManager
from transaction.transaction import Transaction
from transaction.transaction_category import TransactionCategory


class TestApplyTransactionCommand(unittest.TestCase):

    def setUp(self):
        self.balance = Balance.get_instance()
        self.balance.reset()
        self.balance.clear_observers()

    def test_execute_applies_income(self):
        ApplyTransactionCommand(
            self.balance, Transaction(100, TransactionCategory.INCOME)
        ).execute()
        self.assertEqual(self.balance.get_balance(), 100)

    def test_undo_reverses_income(self):
        command = ApplyTransactionCommand(
            self.balance, Transaction(100, TransactionCategory.INCOME)
        )
        command.execute()
        command.undo()
        self.assertEqual(self.balance.get_balance(), 0)

    def test_undo_reverses_expense(self):
        command = ApplyTransactionCommand(
            self.balance, Transaction(40, TransactionCategory.EXPENSE)
        )
        command.execute()
        command.undo()
        self.assertEqual(self.balance.get_balance(), 0)

    def test_accepts_any_balance_like_object(self):
        """DI: a fake balance works in place of the real one."""
        class FakeBalance:
            def __init__(self):
                self.applied = []

            def apply_transaction(self, transaction):
                self.applied.append(transaction)

        fake = FakeBalance()
        transaction = Transaction(5, TransactionCategory.INCOME)
        command = ApplyTransactionCommand(fake, transaction)
        command.execute()
        command.undo()
        self.assertEqual(
            fake.applied,
            [transaction, Transaction(5, TransactionCategory.EXPENSE)],
        )

    def test_base_interface_requires_implementation(self):
        with self.assertRaises(NotImplementedError):
            ICommand().execute()
        with self.assertRaises(NotImplementedError):
            ICommand().undo()


class TestCommandManager(unittest.TestCase):

    def setUp(self):
        self.balance = Balance.get_instance()
        self.balance.reset()
        self.balance.clear_observers()
        self.manager = CommandManager()

    def _run(self, amount, category):
        self.manager.execute(
            ApplyTransactionCommand(
                self.balance, Transaction(amount, category))
        )

    def test_execute_runs_command(self):
        self._run(100, TransactionCategory.INCOME)
        self.assertEqual(self.balance.get_balance(), 100)

    def test_undo_restores_previous_balance(self):
        self._run(100, TransactionCategory.INCOME)
        self._run(30, TransactionCategory.EXPENSE)
        self.assertTrue(self.manager.undo())
        self.assertEqual(self.balance.get_balance(), 100)

    def test_redo_reapplies_undone_command(self):
        self._run(100, TransactionCategory.INCOME)
        self.manager.undo()
        self.assertTrue(self.manager.redo())
        self.assertEqual(self.balance.get_balance(), 100)

    def test_undo_and_redo_with_empty_history_return_false(self):
        self.assertFalse(self.manager.undo())
        self.assertFalse(self.manager.redo())

    def test_new_command_clears_redo_history(self):
        self._run(100, TransactionCategory.INCOME)
        self.manager.undo()
        self._run(10, TransactionCategory.INCOME)
        self.assertFalse(self.manager.can_redo())

    def test_failed_command_is_not_recorded(self):
        with self.assertRaises(ValueError):
            self._run(10, object())
        self.assertFalse(self.manager.can_undo())

    def test_multiple_undos_walk_back_through_history(self):
        self._run(100, TransactionCategory.INCOME)
        self._run(50, TransactionCategory.EXPENSE)
        self.manager.undo()
        self.manager.undo()
        self.assertEqual(self.balance.get_balance(), 0)
        self.assertFalse(self.manager.can_undo())


if __name__ == "__main__":
    unittest.main()