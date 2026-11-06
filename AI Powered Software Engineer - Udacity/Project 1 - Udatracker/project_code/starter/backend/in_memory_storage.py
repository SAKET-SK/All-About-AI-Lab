# This file provides a simple in-memory storage implementation for orders.
# Data stored here will be lost when the application restarts.

class InMemoryStorage:
    """
    A simple in-memory implementation of the storage interface.
    Stores orders in a Python dictionary.
    """
    def __init__(self):
        self._orders = {}

    def save_order(self, order_id: str, order_data: dict):
        self._orders[order_id] = order_data.copy()

    def get_order(self, order_id: str):
        return self._orders.get(order_id, {}).copy() if self._orders.get(order_id) else None

    def get_all_orders(self):
        return {k: v.copy() for k, v in self._orders.items()}

    def clear(self):
        self._orders = {}
