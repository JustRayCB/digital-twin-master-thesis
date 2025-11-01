from unittest.mock import Mock

from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.pipeline.pipeline_builder import PipelineBuilder
from dt.data.preprocess.pipeline.processing_pipeline import ProcessingPipeline
from dt.data.preprocess.processors import (CalibrationProcessor,
                                           ImputationProcessor,
                                           NormalizationProcessor,
                                           SmoothingProcessor,
                                           ValidationProcessor)


def test_pipeline_builder_creates_standard_pipeline() -> None:
    """Standard builder should wire the five core processors in order."""
    config_manager = Mock(spec=ConfigurationManager)
    builder = PipelineBuilder(config_manager)

    pipeline = builder.build_standard_pipeline()

    assert isinstance(pipeline, ProcessingPipeline)
    assert len(pipeline) == 5
    processor_types = [type(proc) for proc in pipeline._processors]
    assert processor_types == [
        CalibrationProcessor,
        ValidationProcessor,
        ImputationProcessor,
        SmoothingProcessor,
        NormalizationProcessor,
    ]


def test_pipeline_builder_creates_validation_only_pipeline() -> None:
    """Validation-only builder should wire calibration followed by validation."""
    config_manager = Mock(spec=ConfigurationManager)
    builder = PipelineBuilder(config_manager)

    pipeline = builder.build_validation_only_pipeline()

    assert isinstance(pipeline, ProcessingPipeline)
    assert len(pipeline) == 2
    processor_types = [type(proc) for proc in pipeline._processors]
    assert processor_types == [
        CalibrationProcessor,
        ValidationProcessor,
    ]
