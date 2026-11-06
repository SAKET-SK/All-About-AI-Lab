# command.py


class ICommand:
    """Interface for an action that can be executed and undone."""

    def execute(self):
        """Perform the action."""
        raise NotImplementedError("Subclasses must implement execute.")

    def undo(self):
        """Reverse the action."""
        raise NotImplementedError("Subclasses must implement undo.")