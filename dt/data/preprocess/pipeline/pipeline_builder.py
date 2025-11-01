from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.pipeline.processing_pipeline import ProcessingPipeline
from dt.data.preprocess.processors import (CalibrationProcessor,
                                           ImputationProcessor,
                                           NormalizationProcessor,
                                           SmoothingProcessor,
                                           ValidationProcessor)
from dt.utils import get_logger

logger = get_logger(__name__)


class PipelineBuilder:
    """Factory for constructing preprocessing pipelines.

    Provides methods to build different pipeline configurations for
    various use cases (standard processing, validation only, etc.).

    Parameters
    ----------
    config_manager : ConfigurationManager
        Configuration manager providing strategies and rules.
    """

    def __init__(self, config_manager) -> None:
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
