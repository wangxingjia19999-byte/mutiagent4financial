class BaseAgent:
    """Base agent abstraction."""

    def execute(self, *args, **kwargs):
        raise NotImplementedError
