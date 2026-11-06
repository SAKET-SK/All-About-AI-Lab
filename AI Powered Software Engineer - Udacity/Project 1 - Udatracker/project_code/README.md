# Udatracker with Test-Driven Development (TDD)

Welcome to the Udatracker project! This guide will walk you through implementing the backend logic and API for your project using a strict **Test-Driven Development (TDD)** workflow.

Your goal is to use the provided test suites to drive your implementation. You'll follow the classic **Red → Green → Refactor** cycle: run a test to see it fail, write the code to make it pass, and then move on to the next feature.
<img width="1261" height="805" alt="Screenshot of web application frontend" src="https://github.com/user-attachments/assets/375894d2-6b0b-43a6-aca9-e0e8cc52d20a"/>

---

## Part 1: Environment Setup

If you are completing this project in the Udacity Workspace environment, you do not need to install anything; the dependencies should already be installed. If you are working locally, follow these steps to ensure your environment is ready.


1.  Navigate to the `backend` directory within the `starter` directory
2.  Activate your virtual environment (`source venv/bin/activate` for macOS/Linux, `.\venv\Scripts\Activate.ps1` for Windows)
   - For the remaining examples, we will use macOS/Linux style paths, e.g. `starter/backend` rather than `starter\backend`. If you are using Windows, you will need to replace `/` with `\` in these commands.
3.  Install dependencies from `requirements.txt` using `pip` (`pip install -r requirements.txt`)

To ensure that the dependencies have been installed, run the Flask server (from the `starter` directory, one level above the `backend` directory):

```bash
python -m backend.app
```

Then check that the application is running:

- If you are working in the Udacity Workspace, select the "Flask App" option from the Links menu to open the app in a new tab
- If you are working locally, open a new tab of your web browser and go to `http://127.0.0.1:5000/`
- In either setting, you can type control-C to stop the server. The server also may stop on its own as you edit the source code. To restart, run `python app.py` again

You will see that there are some parts of the application that produce errors. Your task in this project is to complete the backend code and eliminate those errors. Let's get started!

---

## Part 2: Unit Testing The `OrderTracker` (The TDD Cycle)

We will build the `OrderTracker` class one test at a time. Open both `backend/order_tracker.py` and `backend/tests/test_order_tracker.py` files in your editor.

### Cycle 1: Adding a Basic Order

1.  **Write The First Test**: Add the following code to `tests/test_order_tracker.py`. This test checks if we can add a simple order.

    ```python
    def test_add_order_successfully(order_tracker, mock_storage):
        """Tests adding a new order with default 'pending' status."""
        order_tracker.add_order("ORD001", "Laptop", 1, "CUST001")
        
        # We expect save_order to be called once
        mock_storage.save_order.assert_called_once()
    ```

2.  **See It Fail (RED)**: Run the test. It will fail because the `add_order` method is empty.

    ```bash
    # Run this from the project root (starter/)
    pytest backend/tests/test_order_tracker.py
    ```

3.  **Write The Code (GREEN)**: In `order_tracker.py`, write the *minimum* code in the `add_order` method to make the test pass.

    ```python
    # in backend/order_tracker.py
    def add_order(self, order_id: str, item_name: str, quantity: int, customer_id: str, status: str = "pending"):
        order = {
            "order_id": order_id,
            "item_name": item_name,
            "quantity": quantity,
            "customer_id": customer_id,
            "status": status
        }
        self.storage.save_order(order_id, order)
    ```

4.  **See It Pass**: Run the test again. It should now pass.

### Cycle 2: Preventing Duplicate Orders

1.  **Write The Test**: Add a *new* test to `test_order_tracker.py` to check for duplicate IDs.

    ```python
    # Add to tests/test_order_tracker.py
    def test_add_order_raises_error_if_exists(order_tracker, mock_storage):
        """Tests that adding an order with a duplicate ID raises a ValueError."""
        # Simulate that the storage finds an existing order
        mock_storage.get_order.return_value = {"order_id": "ORD_EXISTING"}

        with pytest.raises(ValueError, match="Order with ID 'ORD_EXISTING' already exists."):
            order_tracker.add_order("ORD_EXISTING", "New Item", 1, "CUST001")
    ```

2.  **See It Fail (RED)**: Run `pytest`. The new test will fail.

3.  **Update The Code (GREEN)**: Add the validation logic to the `add_order` method in `order_tracker.py`.

    ```python
    # Update the add_order method in backend/order_tracker.py
    def add_order(self, order_id: str, item_name: str, quantity: int, customer_id: str, status: str = "pending"):
        # This is the new logic
        if self.storage.get_order(order_id):
            raise ValueError(f"Order with ID '{order_id}' already exists.")

        order = {
            "order_id": order_id,
            "item_name": item_name,
            "quantity": quantity,
            "customer_id": customer_id,
            "status": status
        }
        self.storage.save_order(order_id, order)
    ```

4.  **See It Pass**: Run the tests again. Both tests should now pass.

### Cycle 3 and Beyond

Continue to write unit tests and then implement the remaining methods in `OrderTracker`

- `get_order_by_id`
  - Write unit tests to fetch an existing order by its ID
  - Write a test to handle cases where the order ID does not exist
- `update_order_status`
  - Write unit tests to change an order's status (e.g., from 'pending' to 'shipped')
  - Write a test to handle attempts to update a non-existent order
- `list_all_orders`
  - Write unit tests to list all current orders
- `list_orders_by_status`
  - Write unit tests to retrieve only orders with a specific status (e.g., 'shipped')

---

## Part 3: Building The API

Once all the unit tests for `OrderTracker` are written and passing, you can build the API layer. For this part, you are provided with the complete API test suite (`tests/test_api.py`).

1.  **See The API Tests Fail (RED)**: Run the integration tests. They will fail because the API endpoints in `app.py` are empty.

    ```bash
    # Run this from the project root (starter/)
    pytest backend/tests/test_api.py
    ```

2.  **Implement The API Endpoints (GREEN)**: Open `backend/app.py`. Fill in the logic for each route function to make the tests pass.

3.  **Final Test Run**: After implementing all endpoints, run the entire test suite.
    ```bash
    pytest
    ```
    All tests should now pass.

---

## Part 4: Run the Full Application

Now for the final reward. Let's see your application in action!

1.  **Run the Flask Server**:

    ```bash
    python -m backend.app
    ```

2.  **Open in Browser**:

   - If you are working in the Udacity Workspace, select the "Flask App" option from the Links menu to open the app in a new tab
   - If you are working locally, open a new tab of your web browser and go to `http://127.0.0.1:5000/`

3. **Interact with the App**:

   When you have the application open in your browser, you should see a simple frontend interface. From here you can:

    - Add an order using the form
    - View a list of all orders to confirm that your form inputs are being saved
      - *Note:* we are using in-memory storage, so this list of orders will not persist between sessions
    - Update an order's status (for example, changing it from "pending" to "shipped")
    - Filter orders by status to check that your query routes work correctly

    If everything is implemented correctly, each of these actions should succeed without errors and reflect the current state of your `OrderTracker` logic.

🎉 **Congratulations!** You have completed the project with a true test-first approach.
