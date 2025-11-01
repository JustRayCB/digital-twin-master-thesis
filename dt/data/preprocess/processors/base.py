from abc import ABC, abstractmethod

from dt.data.preprocess.pipeline.context import ProcessingContext


class BaseProcessor(ABC):
    """Abstract base class for all pipeline processors.

    Each processor handles one specific concern in the data processing pipeline
    (calibration, validation, imputation, smoothing, or normalization).

    The processor receives a ProcessingContext, performs its operation, updates
    the context, and returns the modified context for the next processor.
    """

    @abstractmethod
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Process the reading and update the context.

        Parameters
        ----------
        context : ProcessingContext
            Current processing state containing the reading and accumulated results.

        Returns
        -------
        ProcessingContext
            Updated context with this processor's results.

        Raises
        ------
        DropReadingException
            When the reading should be dropped (e.g., imputation failed).
        """
