from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.stages.base import BaseProcessor
from dt.data.preprocess.stages.calibration import CalibrationProcessor
from dt.data.preprocess.stages.imputation import ImputationProcessor
from dt.data.preprocess.stages.normalization import NormalizationProcessor
from dt.data.preprocess.stages.smoothing import SmoothingProcessor
from dt.data.preprocess.stages.validation import ValidationProcessor
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


class PipelineBuilder:
    """Factory for constructing preprocessing pipelines.

    Provides methods to build different pipeline configurations for
    various use cases (standard processing, validation only, etc.).

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing strategies and rules.
    """

    def __init__(self, config_manager: ConfigurationManager) -> None:
        """Initialize the pipeline builder.

        Parameters
        ----------
        config_manager : ConfigurationManager
            Configuration manager for processor initialization.
        """
        self._config_manager: ConfigurationManager = config_manager

    def build_standard_pipeline(self) -> ProcessingPipeline:
        """Build the standard end-to-end preprocessing pipeline.

        The standard pipeline includes:
        1. Calibration
        2. Validation
        3. Imputation
        4. Smoothing
        5. Normalization

        Returns
        -------
        ProcessingPipeline
            Configured pipeline ready for processing.
        """
        pipeline = ProcessingPipeline()

        pipeline.add_processor(CalibrationProcessor(self._config_manager))
        pipeline.add_processor(ValidationProcessor(self._config_manager))
        pipeline.add_processor(ImputationProcessor(self._config_manager))
        pipeline.add_processor(SmoothingProcessor(self._config_manager))
        pipeline.add_processor(NormalizationProcessor(self._config_manager))

        logger.info("Built standard preprocessing pipeline with 5 processors")
        return pipeline

    def build_validation_only_pipeline(self) -> ProcessingPipeline:
        """Build a minimal pipeline for validation without processing.

        This pipeline only includes:
        1. Calibration
        2. Validation

        Useful for testing or when downstream systems handle processing.

        Returns
        -------
        ProcessingPipeline
            Minimal validation pipeline.
        """
        pipeline = ProcessingPipeline()

        pipeline.add_processor(CalibrationProcessor(self._config_manager))
        pipeline.add_processor(ValidationProcessor(self._config_manager))

        logger.info("Built validation-only pipeline with 2 processors")
        return pipeline
