class DropReadingException(Exception):
    """Exception raised to indicate that a reading should be dropped.

    This exception is used to signal that a particular reading is invalid
    or should not be processed further.

    Parameters
    ----------
    message : str
        Explanation of why the reading is being dropped.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
