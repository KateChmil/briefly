class RetryableLLMError(RuntimeError):
    """The model answered, but not in a usable way; asking once more may work."""


class MalformedOutput(RetryableLLMError):
    """The model attempted a tool call but produced invalid arguments."""
