# This module contains the OrderTracker class, which encapsulates the core
# business logic for managing orders.

# The only statuses an order is allowed to have.
VALID_STATUSES = ("pending", "processing", "shipped", "delivered", "cancelled")


class DuplicateOrderError(ValueError):
    """Raised when adding an order whose ID already exists."""


class OrderNotFoundError(ValueError):
    """Raised when an operation targets an order ID that does not exist."""


class OrderTracker:
    """
    Manages customer orders, providing functionalities to add, update,
    and retrieve order information.
    """
    def __init__(self, storage):
        required_methods = ['save_order', 'get_order', 'get_all_orders']
        for method in required_methods:
            if not hasattr(storage, method) or not callable(getattr(storage, method)):
                raise TypeError(f"Storage object must implement a callable '{method}' method.")
        self.storage = storage

    # --- Validation helpers -------------------------------------------------

    @staticmethod
    def _validate_non_empty_string(value, field_name: str):
        """Raise ValueError unless value is a string with visible characters."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")

    @staticmethod
    def _validate_status(status):
        """Raise ValueError unless status is one of VALID_STATUSES."""
        OrderTracker._validate_non_empty_string(status, "status")
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}."
            )

    @staticmethod
    def _validate_quantity(quantity):
        """Raise ValueError unless quantity is a positive integer (bool excluded)."""
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be a positive integer.")

    # --- Public API ---------------------------------------------------------

    def add_order(self, order_id: str, item_name: str, quantity: int, customer_id: str, status: str = "pending"):
        """Validate and store a new order, then return it."""
        self._validate_non_empty_string(order_id, "order_id")
        self._validate_non_empty_string(item_name, "item_name")
        self._validate_non_empty_string(customer_id, "customer_id")
        self._validate_quantity(quantity)
        self._validate_status(status)

        if self.storage.get_order(order_id):
            raise DuplicateOrderError(f"Order with ID '{order_id}' already exists.")

        order = {
            "order_id": order_id,
            "item_name": item_name,
            "quantity": quantity,
            "customer_id": customer_id,
            "status": status
        }
        self.storage.save_order(order_id, order)
        return order

    def get_order_by_id(self, order_id: str):
        """Return the order with the given ID, or None if it does not exist."""
        self._validate_non_empty_string(order_id, "order_id")
        return self.storage.get_order(order_id)

    def update_order_status(self, order_id: str, new_status: str):
        """Change an existing order's status and return the updated order."""
        # Fail fast: validate input before touching storage.
        self._validate_non_empty_string(order_id, "order_id")
        self._validate_status(new_status)

        order = self.storage.get_order(order_id)
        if not order:
            raise OrderNotFoundError(f"Order with ID '{order_id}' not found.")

        # Copy so we never mutate the dict returned by storage in place.
        updated_order = dict(order)
        updated_order["status"] = new_status
        self.storage.save_order(order_id, updated_order)
        return updated_order

    def list_all_orders(self):
        """Return every order as a list of dictionaries."""
        # Storage returns {order_id: order}; callers want just the orders.
        return list(self.storage.get_all_orders().values())

    def list_orders_by_status(self, status: str):
        """Return only the orders whose status matches the given status."""
        self._validate_status(status)
        return [order for order in self.list_all_orders() if order["status"] == status]