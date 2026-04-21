"""Unit tests for EtlPipelineService — file classification, skip logic, and image vision."""

import pytest

from app.etl_pipeline.etl_document import EtlRequest
from app.etl_pipeline.etl_pipeline_service import EtlPipelineService

pytestmark = pytest.mark.unit


async def test_unknown_extension_uses_document_etl(tmp_path, mocker):
    """An allowlisted document extension (.docx) routes to the document ETL path."""
    docx_file = tmp_path / "doc.docx"
    docx_file.write_bytes(b"PK fake docx")

    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    fake_docling = mocker.AsyncMock()
    fake_docling.process_document.return_value = {"content": "Docx content"}
    mocker.patch(
        "app.services.docling_service.create_docling_service",
        return_value=fake_docling,
    )

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(docx_file), filename="doc.docx")
    )

    assert result.markdown_content == "Docx content"
    assert result.content_type == "document"


def test_etl_request_requires_filename():
    """EtlRequest rejects missing filename."""
    with pytest.raises(ValueError, match="filename must not be empty"):
        EtlRequest(file_path="/tmp/some.txt", filename="")


async def test_unknown_etl_service_raises(tmp_path, mocker):
    """An unknown ETL_SERVICE raises EtlServiceUnavailableError."""
    from app.etl_pipeline.exceptions import EtlServiceUnavailableError

    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF fake")

    mocker.patch("app.config.config.ETL_SERVICE", "NONEXISTENT")

    with pytest.raises(EtlServiceUnavailableError, match="Unknown ETL_SERVICE"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(pdf_file), filename="report.pdf")
        )


def test_unknown_extension_classified_as_unsupported():
    """An unknown extension defaults to UNSUPPORTED (allowlist behaviour)."""
    from app.etl_pipeline.file_classifier import FileCategory, classify_file

    assert classify_file("random.xyz") == FileCategory.UNSUPPORTED


@pytest.mark.parametrize(
    "filename",
    [
        "malware.exe",
        "archive.zip",
        "video.mov",
        "font.woff2",
        "model.blend",
        "data.parquet",
        "package.deb",
        "firmware.bin",
    ],
    ids=["exe", "zip", "mov", "woff2", "blend", "parquet", "deb", "bin"],
)
def test_unsupported_extensions_classified_correctly(filename):
    """Extensions not in any allowlist are classified as UNSUPPORTED."""
    from app.etl_pipeline.file_classifier import FileCategory, classify_file

    assert classify_file(filename) == FileCategory.UNSUPPORTED


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("report.pdf", "document"),
        ("doc.docx", "document"),
        ("slides.pptx", "document"),
        ("sheet.xlsx", "document"),
        ("photo.png", "image"),
        ("photo.jpg", "image"),
        ("photo.webp", "image"),
        ("photo.gif", "image"),
        ("photo.heic", "image"),
        ("book.epub", "document"),
        ("letter.odt", "document"),
        ("readme.md", "plaintext"),
        ("data.csv", "direct_convert"),
    ],
    ids=["pdf", "docx", "pptx", "xlsx", "png", "jpg", "webp", "gif", "heic", "epub", "odt", "md", "csv"],
)
def test_parseable_extensions_classified_correctly(filename, expected):
    """Parseable files are classified into their correct category."""
    from app.etl_pipeline.file_classifier import FileCategory, classify_file

    result = classify_file(filename)
    assert result != FileCategory.UNSUPPORTED
    assert result.value == expected


@pytest.mark.parametrize(
    "filename,content",
    [
        ("program.exe", b"\x00" * 10),
        ("archive.zip", b"PK\x03\x04"),
    ],
    ids=["exe", "zip"],
)
async def test_extract_unsupported_file_raises_error(tmp_path, filename, content):
    """EtlPipelineService.extract() raises EtlUnsupportedFileError for unsupported file types."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    f = tmp_path / filename
    f.write_bytes(content)

    with pytest.raises(EtlUnsupportedFileError, match="not supported"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(f), filename=filename)
        )


@pytest.mark.parametrize(
    "filename,etl_service,expected_skip",
    [
        ("file.eml", "DOCLING", True),
        ("file.eml", "UNSTRUCTURED", False),
        ("file.docm", "LLAMACLOUD", False),
        ("file.docm", "DOCLING", True),
        ("file.txt", "DOCLING", False),
        ("file.csv", "LLAMACLOUD", False),
        ("file.mp3", "UNSTRUCTURED", False),
        ("file.exe", "LLAMACLOUD", True),
        ("file.pdf", "DOCLING", False),
        ("file.webp", "DOCLING", False),
        ("file.webp", "UNSTRUCTURED", True),
        ("file.gif", "LLAMACLOUD", False),
        ("file.gif", "DOCLING", True),
        ("file.heic", "UNSTRUCTURED", False),
        ("file.heic", "DOCLING", True),
        ("file.svg", "LLAMACLOUD", False),
        ("file.svg", "DOCLING", True),
        ("file.p7s", "UNSTRUCTURED", False),
        ("file.p7s", "LLAMACLOUD", True),
        ("file.heif", "LLAMACLOUD", True),
        ("file.heif", "DOCLING", True),
        ("file.heif", "UNSTRUCTURED", True),
    ],
    ids=[
        "eml_docling", "eml_unstructured",
        "docm_llamacloud", "docm_docling",
        "txt_docling", "csv_llamacloud",
        "mp3_unstructured", "exe_llamacloud",
        "pdf_docling", "webp_docling", "webp_unstructured",
        "gif_llamacloud", "gif_docling",
        "heic_unstructured", "heic_docling",
        "svg_llamacloud", "svg_docling",
        "p7s_unstructured", "p7s_llamacloud",
        "heif_llamacloud", "heif_docling", "heif_unstructured",
    ],
)
def test_should_skip_for_service(filename, etl_service, expected_skip, monkeypatch):
    monkeypatch.setattr("app.config.config.AZURE_DI_ENDPOINT", None, raising=False)
    monkeypatch.setattr("app.config.config.AZURE_DI_KEY", None, raising=False)
    from app.etl_pipeline.file_classifier import should_skip_for_service

    assert should_skip_for_service(filename, etl_service) is expected_skip, (
        f"{filename} with {etl_service}: expected skip={expected_skip}"
    )


def test_heif_not_skipped_for_llamacloud_when_azure_di_configured(monkeypatch):
    """With Azure DI credentials, .heif is accepted by LLAMACLOUD."""
    monkeypatch.setattr(
        "app.config.config.AZURE_DI_ENDPOINT",
        "https://fake.cognitiveservices.azure.com/",
        raising=False,
    )
    monkeypatch.setattr("app.config.config.AZURE_DI_KEY", "fake-key", raising=False)
    from app.etl_pipeline.file_classifier import should_skip_for_service

    assert should_skip_for_service("file.heif", "LLAMACLOUD") is False


@pytest.mark.parametrize(
    "filename,content",
    [
        ("macro.docm", b"\x00" * 10),
        ("mail.eml", b"From: test@example.com"),
    ],
    ids=["docm", "eml"],
)
async def test_extract_docling_raises_unsupported_for_parser_incompatible(
    tmp_path, mocker, filename, content
):
    """Docling cannot parse .docm or .eml -- pipeline should reject before dispatching."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    test_file = tmp_path / filename
    test_file.write_bytes(content)

    with pytest.raises(EtlUnsupportedFileError, match="not supported by DOCLING"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(test_file), filename=filename)
        )


async def test_extract_image_with_vision_llm(tmp_path):
    """An image file is analyzed by the vision LLM when provided."""
    from unittest.mock import AsyncMock, MagicMock

    img_file = tmp_path / "photo.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    fake_response = MagicMock()
    fake_response.content = "# A photo of a sunset over the ocean"
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = fake_response

    service = EtlPipelineService(vision_llm=fake_llm)
    result = await service.extract(
        EtlRequest(file_path=str(img_file), filename="photo.png")
    )

    assert result.markdown_content == "# A photo of a sunset over the ocean"
    assert result.etl_service == "VISION_LLM"
    assert result.content_type == "image"
    fake_llm.ainvoke.assert_called_once()


async def test_extract_image_falls_back_to_document_without_vision_llm(
    tmp_path, mocker
):
    """Without a vision LLM, image files fall back to the document parser."""
    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    fake_docling = mocker.AsyncMock()
    fake_docling.process_document.return_value = {"content": "# OCR text from image"}
    mocker.patch(
        "app.services.docling_service.create_docling_service",
        return_value=fake_docling,
    )

    img_file = tmp_path / "scan.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    service = EtlPipelineService()
    result = await service.extract(
        EtlRequest(file_path=str(img_file), filename="scan.png")
    )

    assert result.markdown_content == "# OCR text from image"
    assert result.etl_service == "DOCLING"
    assert result.content_type == "document"
