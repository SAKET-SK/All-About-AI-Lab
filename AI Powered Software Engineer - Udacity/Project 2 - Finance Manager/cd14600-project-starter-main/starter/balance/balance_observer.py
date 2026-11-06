# balance_observer.py


class IBalanceObserver:
    def update(self, balance, transaction):
        """Handle balance updates."""
        raise NotImplementedError("Subclasses must implement update method.")


class PrintObserver(IBalanceObserver):
    def __init__(self, output=print):
        # The output function is injected so tests can capture messages.
        self._output = output

    def update(self, balance, transaction):
        """Print balance update message."""
        self._output(f"Applied {transaction} -> balance: ${balance:.2f}")


class LowBalanceAlertObserver(IBalanceObserver):
    def __init__(self, threshold, notifier=print):
        self.threshold = threshold
        self.alert_triggered = False
        # The notifier is injected so alerts can go to print, a log, etc.
        self._notifier = notifier

    def update(self, balance, transaction):
        """Alert if balance drops below threshold."""
        self.alert_triggered = balance < self.threshold
        if self.alert_triggered:
            self._notifier(
                f"ALERT: balance ${balance:.2f} is below the "
                f"${self.threshold:.2f} threshold!"
            )