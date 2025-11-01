import pytest

from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.pipeline.processing_pipeline import ProcessingPipeline
from dt.data.preprocess.processors.base import BaseProcessor


class MockProcessor(BaseProcessor):
    """Mock processor that appends its name to the context."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.called = False

    def process(self, context: ProcessingContext) -> ProcessingContext:
        self.called = True
        called = getattr(context, "processors_called", [])
        called.append(self.name)
        setattr(context, "processors_called", called)
        return context


@pytest.fixture
def sample_context(sample_reading, mock_state_provider) -> ProcessingContext:
    """Provide a minimal processing context for pipeline tests."""
    return ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )


def test_pipeline_executes_processors_in_order(sample_context: ProcessingContext) -> None:
    """Pipeline should execute processors sequentially."""
    pipeline = ProcessingPipeline()

    first = MockProcessor("first")
    second = MockProcessor("second")
    third = MockProcessor("third")

    pipeline.add_processor(first)
    pipeline.add_processor(third)
    pipeline.add_processor(second)

    result = pipeline.process(sample_context)

    assert first.called
    assert second.called
    assert third.called
    assert result.processors_called == ["first", "third", "second"]  # pyright: ignore[]


def test_pipeline_with_no_processors(sample_context: ProcessingContext) -> None:
    """Pipeline should return the context unchanged when empty."""
    pipeline = ProcessingPipeline()

    result = pipeline.process(sample_context)

    assert result is sample_context


def test_pipeline_stops_on_exception(sample_context: ProcessingContext) -> None:
    """Pipeline should propagate processor exceptions without running later steps."""

    class FailingProcessor(BaseProcessor):
        def process(self, context: ProcessingContext) -> ProcessingContext:
            raise ValueError("expected error")

    first = MockProcessor("first")
    failing = FailingProcessor()
    third = MockProcessor("third")

    pipeline = ProcessingPipeline()
    pipeline.add_processor(first)
    pipeline.add_processor(failing)
    pipeline.add_processor(third)

    with pytest.raises(ValueError, match="expected error"):
        pipeline.process(sample_context)

    assert first.called
    assert not hasattr(
        sample_context, "processors_called"
    ) or sample_context.processors_called == [  # pyright: ignore[]
        "first"
    ]
    assert not third.called
