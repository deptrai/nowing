import pytest


@pytest.fixture
def patched_chunker_instance(mocker):
    mock = mocker.patch("app.indexing_pipeline.document_chunker.config.chunker_instance")
    mock.chunk.return_value = [mocker.Mock(text="prose chunk")]
    return mock


@pytest.fixture
def patched_code_chunker_instance(mocker):
    mock = mocker.patch("app.indexing_pipeline.document_chunker.config.code_chunker_instance")
    mock.chunk.return_value = [mocker.Mock(text="code chunk")]
    return mock
