from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.core.pipeline import PipelineBuilder, ProcessingPipeline
from dt.data.preprocess.stages.calibration import CalibrationProcessor
from dt.data.preprocess.stages.imputation import ImputationProcessor
from dt.data.preprocess.stages.normalization import NormalizationProcessor
from dt.data.preprocess.stages.smoothing import SmoothingProcessor
from dt.data.preprocess.stages.validation import ValidationProcessor


def test_pipeline_builder_creates_standard_pipeline(
    test_config_path, configure_preprocess_db_client
) -> None:
    """Standard builder should wire the five core processors in order."""
    builder = PipelineBuilder(ConfigurationManager(test_config_path))

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


def test_pipeline_builder_creates_validation_only_pipeline(
    test_config_path, configure_preprocess_db_client
) -> None:
    """Validation-only builder should wire calibration followed by validation."""
    builder = PipelineBuilder(ConfigurationManager(test_config_path))

    pipeline = builder.build_validation_only_pipeline()

    assert isinstance(pipeline, ProcessingPipeline)
    assert len(pipeline) == 2
    processor_types = [type(proc) for proc in pipeline._processors]
    assert processor_types == [
        CalibrationProcessor,
        ValidationProcessor,
    ]
