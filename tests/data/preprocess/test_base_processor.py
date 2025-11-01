import pytest

from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.base import BaseProcessor


class ConcreteProcessor(BaseProcessor):
    """Concrete processor for testing."""

    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Mark that this processor ran."""
        context.calibrated_reading = context.reading  # Simple pass-through
        return context


def test_base_processor_is_abstract():
    """Test that BaseProcessor cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseProcessor()  # Should fail - abstract class


def test_concrete_processor_can_be_instantiated():
    """Test that a concrete implementation can be created."""
    processor = ConcreteProcessor()
    assert processor is not None


def test_concrete_processor_implements_process(sample_reading, mock_state_provider):
    """Test that concrete processor can process a context."""
    processor = ConcreteProcessor()
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    result = processor.process(context)

    assert result.calibrated_reading == sample_reading
