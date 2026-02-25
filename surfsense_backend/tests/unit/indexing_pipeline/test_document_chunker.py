import pytest

from app.indexing_pipeline.document_chunker import chunk_text

pytestmark = pytest.mark.unit


def test_uses_code_chunker_when_flag_is_true(patched_code_chunker_instance):
    result = chunk_text("def foo(): pass", use_code_chunker=True)

    patched_code_chunker_instance.chunk.assert_called_once_with("def foo(): pass")
    assert result == ["code chunk"]


def test_uses_default_chunker_when_flag_is_false(patched_chunker_instance):
    result = chunk_text("Some prose text.", use_code_chunker=False)

    patched_chunker_instance.chunk.assert_called_once_with("Some prose text.")
    assert result == ["prose chunk"]
