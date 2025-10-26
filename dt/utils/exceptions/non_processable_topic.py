class NonProcessableTopic(Exception):
    """Exception raised for topics that cannot be processed.

    This exception is raised when a non sensor-related topic tris to use the
    .raw or .processed attributes.

    Parameters
    ----------
    message : str
        Explanation of the error.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
