"""Unit tests for EtlPipelineService — LlamaCloud + Azure DI accelerator integration."""

import pytest

from app.etl_pipeline.etl_document import EtlRequest
from app.etl_pipeline.etl_pipeline_service import EtlPipelineService

pytestmark = pytest.mark.unit


def _mock_azure_di(mocker, content="# Azure DI parsed"):
    """Wire up Azure DI mocks and return the fake client for assertions."""

    class FakeResult:
        pass

    FakeResult.content = content

    fake_poller = mocker.AsyncMock()
    fake_poller.result.return_value = FakeResult()

    fake_client = mocker.AsyncMock()
    fake_client.begin_analyze_document.return_value = fake_poller
    fake_client.__aenter__ = mocker.AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = mocker.AsyncMock(return_value=False)

    mocker.patch(
        "azure.ai.documentintelligence.aio.DocumentIntelligenceClient",
        return_value=fake_client,
    )
    mocker.patch(
        "azure.ai.documentintelligence.models.DocumentContentFormat",
        mocker.MagicMock(MARKDOWN="markdown"),
    )
    mocker.patch(
        "azure.core.credentials.AzureKeyCredential",
        return_value=mocker.MagicMock(),
    )
    return fake_client


def _mock_llamacloud(mocker, content="# LlamaCloud parsed"):
    """Wire up LlamaCloud mocks and return the fake parser for assertions."""

    class FakeDoc:
        pass

    FakeDoc.text = content

    class FakeJobResult:
        pages = []

        def get_markdown_documents(self, split_by_page=True):
            return [FakeDoc()]

    fake_parser = mocker.AsyncMock()
    fake_parser.aparse.return_value = FakeJobResult()
    mocker.patch(
        "llama_cloud_services.LlamaParse",
        return_value=fake_parser,
    )
    mocker.patch(
        "llama_cloud_services.parse.utils.ResultType",
        mocker.MagicMock(MD="md"),
    )
    return fake_parser


async def test_llamacloud_with_azure_di_uses_azure_for_pdf(tmp_path, mocker):
    """When Azure DI is configured, a supported extension (.pdf) is parsed by Azure DI."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content " * 10)

    mocker.patch("app.config.config.ETL_SERVICE", "LLAMACLOUD")
    mocker.patch("app.config.config.LLAMA_CLOUD_API_KEY", "fake-key", create=True)
    mocker.patch(
        "app.config.config.AZURE_DI_ENDPOINT",
        "https://fake.cognitiveservices.azure.com/",
        create=True,
    )
    mocker.patch("app.config.config.AZURE_DI_KEY", "fake-key", create=True)

    fake_client = _mock_azure_di(mocker, "# Azure DI parsed")
    fake_parser = _mock_llamacloud(mocker)

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(pdf_file), filename="report.pdf")
    )

    assert result.markdown_content == "# Azure DI parsed"
    assert result.etl_service == "LLAMACLOUD"
    assert result.content_type == "document"
    fake_client.begin_analyze_document.assert_called_once()
    fake_parser.aparse.assert_not_called()


async def test_llamacloud_azure_di_fallback_on_failure(tmp_path, mocker):
    """When Azure DI fails, LlamaCloud is used as a fallback."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content " * 10)

    mocker.patch("app.config.config.ETL_SERVICE", "LLAMACLOUD")
    mocker.patch("app.config.config.LLAMA_CLOUD_API_KEY", "fake-key", create=True)
    mocker.patch(
        "app.config.config.AZURE_DI_ENDPOINT",
        "https://fake.cognitiveservices.azure.com/",
        create=True,
    )
    mocker.patch("app.config.config.AZURE_DI_KEY", "fake-key", create=True)

    mocker.patch(
        "app.etl_pipeline.parsers.azure_doc_intelligence.parse_with_azure_doc_intelligence",
        side_effect=RuntimeError("Azure DI unavailable"),
    )
    fake_parser = _mock_llamacloud(mocker, "# LlamaCloud fallback")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(pdf_file), filename="report.pdf", estimated_pages=5)
    )

    assert result.markdown_content == "# LlamaCloud fallback"
    assert result.etl_service == "LLAMACLOUD"
    assert result.content_type == "document"
    fake_parser.aparse.assert_called_once()


async def test_llamacloud_skips_azure_di_for_unsupported_ext(tmp_path, mocker):
    """Azure DI is skipped for extensions it doesn't support (e.g. .epub)."""
    epub_file = tmp_path / "book.epub"
    epub_file.write_bytes(b"\x00" * 10)

    mocker.patch("app.config.config.ETL_SERVICE", "LLAMACLOUD")
    mocker.patch("app.config.config.LLAMA_CLOUD_API_KEY", "fake-key", create=True)
    mocker.patch(
        "app.config.config.AZURE_DI_ENDPOINT",
        "https://fake.cognitiveservices.azure.com/",
        create=True,
    )
    mocker.patch("app.config.config.AZURE_DI_KEY", "fake-key", create=True)

    fake_client = _mock_azure_di(mocker)
    fake_parser = _mock_llamacloud(mocker, "# Epub from LlamaCloud")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(epub_file), filename="book.epub", estimated_pages=50)
    )

    assert result.markdown_content == "# Epub from LlamaCloud"
    assert result.etl_service == "LLAMACLOUD"
    fake_client.begin_analyze_document.assert_not_called()
    fake_parser.aparse.assert_called_once()


async def test_llamacloud_without_azure_di_uses_llamacloud_directly(tmp_path, mocker):
    """When Azure DI is not configured, LlamaCloud handles all file types directly."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content " * 10)

    mocker.patch("app.config.config.ETL_SERVICE", "LLAMACLOUD")
    mocker.patch("app.config.config.LLAMA_CLOUD_API_KEY", "fake-key", create=True)
    mocker.patch("app.config.config.AZURE_DI_ENDPOINT", None, create=True)
    mocker.patch("app.config.config.AZURE_DI_KEY", None, create=True)

    fake_parser = _mock_llamacloud(mocker, "# Direct LlamaCloud")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(pdf_file), filename="report.pdf", estimated_pages=5)
    )

    assert result.markdown_content == "# Direct LlamaCloud"
    assert result.etl_service == "LLAMACLOUD"
    assert result.content_type == "document"
    fake_parser.aparse.assert_called_once()


async def test_llamacloud_heif_accepted_only_with_azure_di(tmp_path, mocker):
    """.heif is accepted by LLAMACLOUD only when Azure DI credentials are set."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    heif_file = tmp_path / "photo.heif"
    heif_file.write_bytes(b"\x00" * 100)

    mocker.patch("app.config.config.ETL_SERVICE", "LLAMACLOUD")
    mocker.patch("app.config.config.LLAMA_CLOUD_API_KEY", "fake-key", create=True)
    mocker.patch("app.config.config.AZURE_DI_ENDPOINT", None, create=True)
    mocker.patch("app.config.config.AZURE_DI_KEY", None, create=True)

    with pytest.raises(EtlUnsupportedFileError, match="document parser does not support this format"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(heif_file), filename="photo.heif")
        )

    mocker.patch(
        "app.config.config.AZURE_DI_ENDPOINT",
        "https://fake.cognitiveservices.azure.com/",
    )
    mocker.patch("app.config.config.AZURE_DI_KEY", "fake-key")

    fake_client = _mock_azure_di(mocker, "# HEIF from Azure DI")
    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(heif_file), filename="photo.heif")
    )

    assert result.markdown_content == "# HEIF from Azure DI"
    assert result.etl_service == "LLAMACLOUD"
    fake_client.begin_analyze_document.assert_called_once()
