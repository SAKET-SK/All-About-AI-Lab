import pytest
from unittest.mock import Mock
from ..order_tracker import OrderTracker

# --- Fixtures for Unit Tests ---

@pytest.fixture
def mock_storage():
    """
    Provides a mock storage object for tests.
    This mock will be configured to simulate various storage behaviors.
    """
    mock = Mock()
    # By default, mock get_order to return None (no order found)
    mock.get_order.return_value = None
    # By default, mock get_all_orders to return an empty dict
    mock.get_all_orders.return_value = {}
    return mock

@pytest.fixture
def order_tracker(mock_storage):
    """
    Provides an OrderTracker instance initialized with the mock_storage.
    """
    return OrderTracker(mock_storage)

#
# --- Tests for add_order ---
#

def test_add_order_successfully(order_tracker, mock_storage):
    """Tests adding a new order with default 'pending' status."""
    order_tracker.add_order("ORD001", "Laptop", 1, "CUST001")

    # We expect save_order to be called once
    mock_storage.save_order.assert_called_once()

def test_add_order_raises_error_if_exists(order_tracker, mock_storage):
    """Tests that adding an order with a duplicate ID raises a ValueError."""
    # Simulate that the storage finds an existing order
    mock_storage.get_order.return_value = {"order_id": "ORD_EXISTING"}

    with pytest.raises(ValueError, match="Order with ID 'ORD_EXISTING' already exists."):
        order_tracker.add_order("ORD_EXISTING", "New Item", 1, "CUST001")

def test_add_order_stores_correct_details_with_default_status(order_tracker, mock_storage):
    """Tests that the saved order has the right fields and status 'pending'."""
    order_tracker.add_order("ORD002", "Phone", 3, "CUST002")

    mock_storage.save_order.assert_called_once_with(
        "ORD002",
        {
            "order_id": "ORD002",
            "item_name": "Phone",
            "quantity": 3,
            "customer_id": "CUST002",
            "status": "pending",
        },
    )

def test_add_order_with_explicit_status(order_tracker, mock_storage):
    """Tests that an explicit valid status is stored instead of the default."""
    order_tracker.add_order("ORD003", "Mouse", 1, "CUST003", status="shipped")

    saved_order = mock_storage.save_order.call_args[0][1]
    assert saved_order["status"] == "shipped"

def test_add_order_returns_the_created_order(order_tracker):
    """Tests that add_order returns the order dictionary it created."""
    order = order_tracker.add_order("ORD004", "Desk", 2, "CUST004")

    assert order["order_id"] == "ORD004"
    assert order["status"] == "pending"

@pytest.mark.parametrize("bad_quantity", [0, -5, 1.5, "2", None, True])
def test_add_order_rejects_invalid_quantity(order_tracker, mock_storage, bad_quantity):
    """Tests that quantity must be a positive integer."""
    with pytest.raises(ValueError, match="Quantity must be a positive integer."):
        order_tracker.add_order("ORD005", "Chair", bad_quantity, "CUST005")
    mock_storage.save_order.assert_not_called()

def test_add_order_rejects_invalid_status(order_tracker, mock_storage):
    """Tests that an unknown initial status is rejected."""
    with pytest.raises(ValueError, match="Invalid status 'lost'."):
        order_tracker.add_order("ORD006", "Lamp", 1, "CUST006", status="lost")
    mock_storage.save_order.assert_not_called()

@pytest.mark.parametrize(
    "order_id, item_name, customer_id, missing_field",
    [
        ("", "Laptop", "CUST001", "order_id"),
        ("ORD007", "", "CUST001", "item_name"),
        ("ORD007", "Laptop", "", "customer_id"),
        ("   ", "Laptop", "CUST001", "order_id"),
        (None, "Laptop", "CUST001", "order_id"),
    ],
)
def test_add_order_rejects_missing_required_fields(
    order_tracker, mock_storage, order_id, item_name, customer_id, missing_field
):
    """Tests that empty, blank or missing text fields are rejected."""
    with pytest.raises(ValueError, match=f"{missing_field} must be a non-empty string."):
        order_tracker.add_order(order_id, item_name, 1, customer_id)
    mock_storage.save_order.assert_not_called()

#
# --- Tests for get_order_by_id ---
#

def test_get_order_by_id_returns_existing_order(order_tracker, mock_storage):
    """Tests fetching an order that exists."""
    stored = {"order_id": "ORD100", "item_name": "Laptop", "quantity": 1,
              "customer_id": "CUST1", "status": "pending"}
    mock_storage.get_order.return_value = stored

    assert order_tracker.get_order_by_id("ORD100") == stored
    mock_storage.get_order.assert_called_once_with("ORD100")

def test_get_order_by_id_returns_none_if_not_found(order_tracker):
    """Tests that a non-existent order returns None."""
    assert order_tracker.get_order_by_id("MISSING") is None

@pytest.mark.parametrize("bad_id", ["", "   ", None])
def test_get_order_by_id_raises_for_empty_id(order_tracker, mock_storage, bad_id):
    """Tests that an empty or invalid ID raises a ValueError."""
    with pytest.raises(ValueError, match="order_id must be a non-empty string."):
        order_tracker.get_order_by_id(bad_id)
    mock_storage.get_order.assert_not_called()

#
# --- Tests for update_order_status ---
#

def test_update_order_status_successfully(order_tracker, mock_storage):
    """Tests changing an order's status from 'pending' to 'shipped'."""
    mock_storage.get_order.return_value = {
        "order_id": "ORD200", "item_name": "Laptop", "quantity": 1,
        "customer_id": "CUST1", "status": "pending",
    }

    updated = order_tracker.update_order_status("ORD200", "shipped")

    assert updated["status"] == "shipped"
    mock_storage.save_order.assert_called_once_with("ORD200", updated)

def test_update_order_status_does_not_mutate_stored_dict(order_tracker, mock_storage):
    """Tests that the dict returned by storage is copied, not changed in place."""
    original = {"order_id": "ORD201", "item_name": "Laptop", "quantity": 1,
                "customer_id": "CUST1", "status": "pending"}
    mock_storage.get_order.return_value = original

    order_tracker.update_order_status("ORD201", "processing")

    assert original["status"] == "pending"

def test_update_order_status_rejects_invalid_status_without_reading_storage(
    order_tracker, mock_storage
):
    """Tests that an invalid status fails fast, before any storage read."""
    with pytest.raises(ValueError, match="Invalid status 'teleported'."):
        order_tracker.update_order_status("ORD202", "teleported")
    mock_storage.get_order.assert_not_called()
    mock_storage.save_order.assert_not_called()

def test_update_order_status_raises_if_order_not_found(order_tracker, mock_storage):
    """Tests that updating a non-existent order raises a ValueError."""
    with pytest.raises(ValueError, match="Order with ID 'GHOST' not found."):
        order_tracker.update_order_status("GHOST", "shipped")
    mock_storage.save_order.assert_not_called()

@pytest.mark.parametrize("bad_id", ["", "   ", None])
def test_update_order_status_raises_for_empty_id(order_tracker, mock_storage, bad_id):
    """Tests that an empty order ID raises a ValueError."""
    with pytest.raises(ValueError, match="order_id must be a non-empty string."):
        order_tracker.update_order_status(bad_id, "shipped")
    mock_storage.save_order.assert_not_called()

#
# --- Tests for list_all_orders ---
#

def test_list_all_orders_returns_empty_list_when_no_orders(order_tracker):
    """Tests listing orders when storage is empty."""
    assert order_tracker.list_all_orders() == []

def test_list_all_orders_returns_all_orders_as_list(order_tracker, mock_storage):
    """Tests that the storage dict is converted into a list of order dicts."""
    order_a = {"order_id": "A", "item_name": "Item A", "quantity": 1,
               "customer_id": "C1", "status": "pending"}
    order_b = {"order_id": "B", "item_name": "Item B", "quantity": 2,
               "customer_id": "C2", "status": "shipped"}
    mock_storage.get_all_orders.return_value = {"A": order_a, "B": order_b}

    result = order_tracker.list_all_orders()

    assert isinstance(result, list)
    assert len(result) == 2
    assert order_a in result
    assert order_b in result

#
# --- Tests for list_orders_by_status ---
#

def test_list_orders_by_status_returns_only_matching_orders(order_tracker, mock_storage):
    """Tests that only orders with the requested status are returned."""
    pending = {"order_id": "A", "item_name": "Item A", "quantity": 1,
               "customer_id": "C1", "status": "pending"}
    shipped = {"order_id": "B", "item_name": "Item B", "quantity": 2,
               "customer_id": "C2", "status": "shipped"}
    mock_storage.get_all_orders.return_value = {"A": pending, "B": shipped}

    assert order_tracker.list_orders_by_status("shipped") == [shipped]

def test_list_orders_by_status_returns_empty_list_when_none_match(order_tracker, mock_storage):
    """Tests that a valid status with no matching orders gives an empty list."""
    mock_storage.get_all_orders.return_value = {
        "A": {"order_id": "A", "item_name": "Item A", "quantity": 1,
              "customer_id": "C1", "status": "pending"}
    }

    assert order_tracker.list_orders_by_status("delivered") == []

def test_list_orders_by_status_returns_empty_list_when_storage_empty(order_tracker):
    """Tests filtering when there are no orders at all."""
    assert order_tracker.list_orders_by_status("pending") == []

@pytest.mark.parametrize("bad_status", ["", "   ", None])
def test_list_orders_by_status_raises_for_empty_status(order_tracker, bad_status):
    """Tests that an empty status raises a ValueError."""
    with pytest.raises(ValueError, match="status must be a non-empty string."):
        order_tracker.list_orders_by_status(bad_status)

def test_list_orders_by_status_raises_for_invalid_status(order_tracker):
    """Tests that an unknown status raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid status 'lost'."):
        order_tracker.list_orders_by_status("lost")