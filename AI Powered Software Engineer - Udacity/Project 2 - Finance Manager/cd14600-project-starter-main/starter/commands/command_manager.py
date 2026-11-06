# command_manager.py


class CommandManager:
    """Invoker that runs commands and keeps undo/redo history."""

    def __init__(self):
        self._undo_stack = []
        self._redo_stack = []

    def execute(self, command):
        """Run a command and record it. A failed command is not recorded."""
        command.execute()
        self._undo_stack.append(command)
        # A new action invalidates anything that was previously undone.
        self._redo_stack.clear()

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def undo(self):
        """Undo the most recent command. Returns False if none exist."""
        if not self.can_undo():
            return False
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return True

    def redo(self):
        """Re-run the most recently undone command. False if none exist."""
        if not self.can_redo():
            return False
        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        return True