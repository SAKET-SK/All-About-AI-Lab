import unittest
from transaction.transaction import Transaction
from transaction.transaction_category import TransactionCategory
from balance.balance import Balance
from balance.balance_observer import LowBalanceAlertObserver
from balance.balance_observer import IBalanceObserver, PrintObserver


class TestLowBalanceAlertObserver(unittest.TestCase):

    def setUp(self):
        self.balance = Balance.get_instance()
        self.balance.reset()
        self.balance.clear_observers()

    def test_alert_triggers_on_low_balance(self):
        observer = LowBalanceAlertObserver(threshold=50)
        self.balance.register_observer(observer)

        self.balance.apply_transaction(
            Transaction(100, TransactionCategory.INCOME))
        self.assertFalse(observer.alert_triggered)

        self.balance.apply_transaction(
            Transaction(60, TransactionCategory.EXPENSE))
        self.assertTrue(observer.alert_triggered)

        self.balance.apply_transaction(
            Transaction(100, TransactionCategory.INCOME))
        self.assertFalse(observer.alert_triggered)

        self.balance.apply_transaction(
            Transaction(60, TransactionCategory.EXPENSE))
        self.assertFalse(observer.alert_triggered)

        self.balance.apply_transaction(
            Transaction(60, TransactionCategory.EXPENSE))
        self.assertTrue(observer.alert_triggered)

    def test_alert_message_is_sent_to_injected_notifier(self):
        messages = []
        observer = LowBalanceAlertObserver(50, notifier=messages.append)
        self.balance.register_observer(observer)

        self.balance.apply_transaction(
            Transaction(60, TransactionCategory.INCOME))
        self.assertEqual(messages, [])

        self.balance.apply_transaction(
            Transaction(20, TransactionCategory.EXPENSE))
        self.assertEqual(len(messages), 1)
        self.assertIn("below", messages[0])

    def test_balance_equal_to_threshold_does_not_alert(self):
        observer = LowBalanceAlertObserver(50, notifier=lambda msg: None)
        self.balance.register_observer(observer)
        self.balance.apply_transaction(
            Transaction(50, TransactionCategory.INCOME))
        self.assertFalse(observer.alert_triggered)


class TestPrintObserver(unittest.TestCase):

    def setUp(self):
        self.balance = Balance.get_instance()
        self.balance.reset()
        self.balance.clear_observers()

    def test_prints_once_per_applied_transaction(self):
        messages = []
        self.balance.register_observer(PrintObserver(output=messages.append))

        self.balance.apply_transaction(
            Transaction(100, TransactionCategory.INCOME))
        self.balance.apply_transaction(
            Transaction(40, TransactionCategory.EXPENSE))

        self.assertEqual(len(messages), 2)
        self.assertIn("$100.00", messages[0])
        self.assertIn("$60.00", messages[1])

    def test_not_notified_by_direct_add_or_failed_transaction(self):
        messages = []
        self.balance.register_observer(PrintObserver(output=messages.append))
        self.balance.add_income(10)
        with self.assertRaises(ValueError):
            self.balance.apply_transaction(Transaction(10, object()))
        self.assertEqual(messages, [])


class TestObserverRegistration(unittest.TestCase):

    def setUp(self):
        self.balance = Balance.get_instance()
        self.balance.reset()
        self.balance.clear_observers()

    def test_unregistered_observer_is_not_notified(self):
        messages = []
        observer = PrintObserver(output=messages.append)
        self.balance.register_observer(observer)
        self.balance.unregister_observer(observer)
        self.balance.apply_transaction(
            Transaction(10, TransactionCategory.INCOME))
        self.assertEqual(messages, [])

    def test_registering_twice_notifies_once(self):
        messages = []
        observer = PrintObserver(output=messages.append)
        self.balance.register_observer(observer)
        self.balance.register_observer(observer)
        self.balance.apply_transaction(
            Transaction(10, TransactionCategory.INCOME))
        self.assertEqual(len(messages), 1)

    def test_all_observers_are_notified(self):
        first, second = [], []
        self.balance.register_observer(PrintObserver(output=first.append))
        self.balance.register_observer(PrintObserver(output=second.append))
        self.balance.apply_transaction(
            Transaction(10, TransactionCategory.INCOME))
        self.assertEqual((len(first), len(second)), (1, 1))

    def test_rejects_object_without_update_method(self):
        with self.assertRaises(TypeError):
            self.balance.register_observer(object())

    def test_base_interface_requires_update(self):
        with self.assertRaises(NotImplementedError):
            IBalanceObserver().update(0, None)


if __name__ == "__main__":
    unittest.main()