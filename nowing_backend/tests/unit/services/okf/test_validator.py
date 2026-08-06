"""OKF validator self-checks."""

from app.services.okf import (
    is_conformant_concept,
    parse_frontmatter,
    validate_bundle,
    validate_concept,
)


def test_parse_frontmatter_success() -> None:
    text = "---\ntype: Note\ntitle: T\n---\n\nBody"
    fm, error = parse_frontmatter(text)
    assert error is None
    assert fm == {"type": "Note", "title": "T"}


def test_parse_frontmatter_errors() -> None:
    assert parse_frontmatter("no frontmatter")[0] is None
    assert parse_frontmatter("---\ntype: x")[0] is None  # missing closing delimiter


def test_validate_concept_requires_non_empty_type() -> None:
    assert not validate_concept("---\ntype: Note\n---\nbody")
    assert validate_concept("---\n---\nbody")
    assert validate_concept('---\ntype: ""\n---\nbody')
    assert validate_concept("plain text")


def test_is_conformant_concept() -> None:
    assert is_conformant_concept("---\ntype: Note\n---\nbody")
    assert not is_conformant_concept("---\n---\nbody")


def test_validate_bundle_exempts_reserved_files() -> None:
    files = {
        "ok.md": "---\ntype: Note\n---\nbody",
        "index.md": "plain index with no frontmatter",
        "log.md": "plain log with no frontmatter",
        "bad.md": "no frontmatter here",
    }
    errors = validate_bundle(files)
    assert "ok.md" not in errors
    assert "index.md" not in errors
    assert "log.md" not in errors
    assert "bad.md" in errors


def test_validate_bundle_conformant() -> None:
    files = {
        "Root Note.md": "---\ntype: Note\n---\nbody",
        "Research/Note.md": "---\ntype: Note\n---\nbody",
        "index.md": "no frontmatter",
    }
    assert validate_bundle(files) == {}
