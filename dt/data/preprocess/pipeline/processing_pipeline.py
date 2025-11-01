from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.base import BaseProcessor
from dt.utils import get_logger

logger = get_logger(__name__)


class ProcessingPipeline:
    """Chain of responsibility pipeline for sensor data processing.

    Executes a sequence of processors in order, passing the context through
    each step. Each processor can modify the context and pass it to the next.
    """

    def __init__(self) -> None:
        self._processors: list[BaseProcessor] = []

    def add_processor(self, processor: BaseProcessor) -> None:
        """Add a processor to the end of the pipeline.

        Parameters
        ----------
        processor : BaseProcessor
            Processor to add to the chain.
        """
        self._processors.append(processor)
        logger.debug(
            f"Added processor to pipeline: ProcessingPipeline (total={len(self._processors)})"
        )

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Execute the pipeline on the given context.

        Parameters
        ----------
        context : ProcessingContext
            Initial processing context.

        Returns
        -------
        ProcessingContext
            Context after passing through all processors.

        Raises
        ------
        Exception
            Any exception raised by processors propagates to the caller.
        """
        for processor in self._processors:
            context = processor.process(context)
        return context

    def __len__(self) -> int:
        return len(self._processors)
