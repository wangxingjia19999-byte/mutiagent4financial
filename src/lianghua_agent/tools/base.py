class BaseTool:
    """Base class for tools."""

    name: str = "base_tool"

    def run(self, *args, **kwargs):
        raise NotImplementedError
