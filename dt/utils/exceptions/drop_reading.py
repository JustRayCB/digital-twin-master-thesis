from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dt.data.preprocess.pipeline.context import ProcessingContext


class DropReadingException(Exception):
    """Exception raised to indicate that a reading should be dropped.

    This exception is used to signal that a particular reading is invalid
    or should not be processed further.

    Parameters
    ----------
    message : str
        Explanation of why the reading is being dropped.
    context : ProcessingContext
        Processing context associated with the dropped reading.
    """

    def __init__(self, message: str, context: "ProcessingContext"):
        super().__init__(message)
        self.message = message
        self.context = context
