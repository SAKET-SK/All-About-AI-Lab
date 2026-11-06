# Personal Finance Manager

A small Python application that tracks income and expenses, keeps a running
balance, and alerts the user when the balance gets low. It is built to show
four classic design patterns working together, with dependency injection to
keep every part easy to test.

## Run it

All commands run from this folder (`starter/`). No external packages needed
(Python 3.8+).

```
python main.py                                        # run the demo
python -m unittest discover -s . -t . -p "test_*.py"  # run all tests
```

## Project structure

```
starter/
├── main.py                              # demo: wires everything together
├── balance/
│   ├── balance.py                       # Singleton Balance (+ Observer subject)
│   ├── balance_observer.py              # Observer interface and observers
│   ├── test_balance.py
│   └── test_balance_observer.py
├── transaction/
│   ├── transaction.py                   # Transaction value object
│   ├── transaction_category.py          # INCOME / EXPENSE enum
│   ├── external_income_transaction.py   # third-party freelance income
│   ├── transaction_adapter.py           # Adapter pattern
│   ├── test_transaction.py
│   └── test_transaction_adapter.py
└── commands/                            # Command pattern (my choice)
    ├── command.py                       # ICommand interface
    ├── apply_transaction_command.py     # apply a transaction / undo it
    ├── command_manager.py               # history, undo and redo
    └── test_commands.py
```

## The four design patterns

### 1. Singleton: `Balance` (creational)
- **Where:** `balance/balance.py`. `Balance.get_instance()` returns the one
  shared object, and calling `Balance()` a second time raises `RuntimeError`.
- **Why it fits:** the app has exactly one account balance. If two parts of
  the program each held their own `Balance`, they would disagree about how
  much money there is.
- **Benefit:** a single source of truth without passing global state around.

### 2. Adapter: `TransactionAdapter` (structural)
- **Where:** `transaction/transaction_adapter.py`.
  `ExternalFreelanceIncome` has its own shape (`amount`, `invoice_id`,
  `description`, `typ`). The adapter converts it into the app's own
  `Transaction`.
- **Why it fits:** we cannot (and should not) change a third-party class, and
  the rest of the app should not know it exists.
- **Benefit:** a new income source only needs a new adapter. `Balance` and the
  observers never change.

### 3. Observer: `PrintObserver` and `LowBalanceAlertObserver` (behavioral)
- **Where:** `Balance` is the subject (`register_observer`,
  `unregister_observer`). After every applied transaction it calls
  `update(balance, transaction)` on each observer in
  `balance/balance_observer.py`.
  - `PrintObserver` prints the new balance on every change.
  - `LowBalanceAlertObserver` sets `alert_triggered` and sends an alert
    whenever the balance is below its threshold, and clears it again when the
    balance recovers.
- **Why it fits:** reacting to balance changes (printing, alerting) is
  separate from managing the balance itself.
- **Benefit:** new reactions (email, logging, a UI) are added by registering
  one more observer, with no edits to `Balance`.

### 4. Command: `ApplyTransactionCommand` + `CommandManager` (my choice)
- **Where:** the `commands/` package. Applying a transaction is wrapped in an
  object with `execute()` and `undo()`. `CommandManager` keeps undo and redo
  history.
- **Why I chose it:** it is a behavioral pattern not used by the other three,
  and a finance app naturally needs "I entered that by mistake". Undo is
  hard to bolt on later if actions are plain function calls.
- **Benefit:** flexibility (undo and redo with no changes to `Balance`),
  testability (commands and the manager are tested with fake balances), and
  scalability (history, batching or audit logs can be layered on the manager).

## Dependency injection

Dependencies are passed in rather than created inside the classes:

- `ApplyTransactionCommand(balance, transaction)` receives the balance, so
  it works with the real singleton or a test fake.
- `PrintObserver(output=print)` and
  `LowBalanceAlertObserver(threshold, notifier=print)` receive the function
  that delivers their message, so tests capture messages instead of printing.
- `TransactionAdapter(external_transaction)` receives the object to convert.
- `main.py` is the only place that builds the objects and connects them.

## Testing

47 `unittest` tests cover `Balance` (including the singleton guarantee and
invalid amounts), `Transaction`, the adapter (including unknown types), both
observers (including threshold edge cases and registration rules), and the
command pattern (undo, redo, history rules, failed commands). Because
`Balance` is a singleton, each test resets it and clears its observers in
`setUp` so tests do not affect one another.

## Reflection

**Patterns and how each improved the design.** The Singleton gives one
trusted balance. The Adapter keeps the third-party freelance format out of the
core code. The Observer separates "the balance changed" from "what to do about
it". The Command pattern turns applying a transaction into an object, which
made undo and redo simple. Injecting the balance, output functions and
notifiers made all of it easy to test without touching the console.

**Trade-offs and challenges.**
- **Singleton and testing:** global state leaks between tests, so each test
  had to reset the balance and clear observers. The implementation is also
  not thread-safe; a lock would be needed in a multi-threaded app.
- **Adapter loses data:** `Transaction` has no place for the invoice ID or
  project description, so the adapter drops them. Adding optional metadata to
  `Transaction` would fix this.
- **Undo is a reversing transaction:** undoing an income applies an equal
  expense, so observers see a new transaction (the printout shows an
  "EXPENSE" for an undo) instead of the original being erased. This keeps
  one simple code path and an honest history, but it is not a true rollback.
- **Floats for money:** simple, but `decimal.Decimal` would be safer for real
  currency.
- **More code:** the Command pattern adds three small files for a feature the
  demo uses lightly, which is worthwhile only because undo is needed.