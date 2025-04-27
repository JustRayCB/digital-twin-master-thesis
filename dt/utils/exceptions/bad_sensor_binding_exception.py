class BadSensorBindingException(Exception):
    """
    Exception raised when a sensor binding is invalid.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
