class BadSensorBindingException(Exception):
    """Exception raised for errors during the sensor binding process.

    This exception is raised when there is an issue with binding a sensor to the
    system, such as when the sensor is already bound or when the binding
    request is invalid.

    Parameters
    ----------
    message : str
        Explanation of the error.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
