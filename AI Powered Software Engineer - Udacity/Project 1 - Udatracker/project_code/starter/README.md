# Udatracker

An order tracking service built test-first (Red → Green → Refactor) with a framework-independent `OrderTracker` class and a small Flask API. Run it with `python -m backend.app` and run the tests with `pytest` from this directory.

## Reflection

- **Design decision:** I kept all validation in `OrderTracker` and gave it two small exception types (`DuplicateOrderError`, `OrderNotFoundError`) that subclass `ValueError`. The Flask routes stay thin, and one set of error handlers turns these into 409, 404 and 400 JSON responses, so the business logic never imports Flask.
- **Testing insight:** The mock storage returns `get_all_orders()` as a dict, so my `list_all_orders` test failed until I converted it to a list. That test also showed me to check the status before reading storage in `update_order_status`.
- **Next step:** Add a DELETE endpoint and persistent storage (e.g. SQLite) so orders survive a restart.

## Project structure

```
.
├── backend
│   ├── __init__.py
│   ├── app.py
│   ├── in_memory_storage.py
│   ├── order_tracker.py
│   ├── requirements.txt
│   └── tests
│       ├── __init__.py
│       ├── test_api.py
│       └── test_order_tracker.py
├── frontend
│   ├── css
│   │   └── style.css
│   ├── index.html
│   └── js
│       └── script.js
├── pytest.ini
└── README.md
```