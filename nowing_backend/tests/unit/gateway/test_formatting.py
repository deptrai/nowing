from app.gateway.telegram.formatting import (
    chunk_message,
    escape_markdown_v2,
    unescape_markdown_v2,
)


def test_escape_markdown_v2_reserved_chars():
    text = r"_*[]()~`>#+-=|{}.!"

    assert escape_markdown_v2(text) == r"\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"


def test_unescape_markdown_v2_only_reserved_chars():
    text = r"hello \*world and \\not reserved"
    assert unescape_markdown_v2(text) == r"hello *world and \\not reserved"


def test_chunk_message_preserves_content_and_limits_size():
    text = "First paragraph.\n\n" + ("x" * 5000)

    chunks = chunk_message(text, max_units=4096)

    assert "".join(chunks) == text
    assert len(chunks) > 1
    assert all(len(chunk.encode("utf-16-le")) // 2 <= 4096 for chunk in chunks)
