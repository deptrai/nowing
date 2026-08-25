"""Unit tests for Design View Mark Tool (Story 27.1d / AD-114).

Acceptance Criteria:
- AC-4: Mark Tool bounding box selector mapping & JSX AST mutation.
- AC-3: unresolvable / non-unique selectors return ``mark_unresolvable``.
- NFR-2: patch values are escaped/validated before insertion.
"""

from __future__ import annotations

import pytest

from app.services.web_builder.mark_tool import MarkToolASTMutator

pytestmark = [pytest.mark.unit]


@pytest.fixture
def mutator() -> MarkToolASTMutator:
    return MarkToolASTMutator()


class TestMarkToolASTMutator:
    """AC-4: Mark Tool AST Mutation tests."""

    def test_map_selector_to_jsx_node_and_apply_text_patch(
        self, mutator: MarkToolASTMutator
    ):
        """AC-4: Given a CSS selector / XPath and text patch, mutator updates JSX AST correctly."""
        sample_jsx = """
        export default function Page() {
            return (
                <div className="container mx-auto">
                    <h1 id="hero-title" className="text-4xl font-bold">Original Title</h1>
                    <p className="description">Subtitle text</p>
                </div>
            );
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero-title",
            patch={"type": "text", "value": "Updated Hero Headline"},
        )

        assert result.status == "patched"
        assert "Updated Hero Headline" in result.patched_code
        assert "Original Title" not in result.patched_code

    def test_map_selector_apply_style_patch(self, mutator: MarkToolASTMutator):
        """AC-4: Given a selector and style patch, mutator updates className attributes."""
        sample_jsx = """
        export default function Hero() {
            return <button id="cta-btn" className="bg-blue-500 text-white">Click Me</button>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#cta-btn",
            patch={
                "type": "className",
                "value": "bg-emerald-600 text-white font-semibold",
            },
        )

        assert result.status == "patched"
        assert "bg-emerald-600" in result.patched_code

    def test_unresolvable_selector_returns_graceful_status(
        self, mutator: MarkToolASTMutator
    ):
        """AC-3: Given a selector not matching any JSX node, return status mark_unresolvable without mutating."""
        sample_jsx = """
        export default function Page() {
            return <div><h1>Title</h1></div>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#non-existent-element",
            patch={"type": "text", "value": "New Value"},
        )

        assert result.status == "mark_unresolvable"
        assert result.patched_code == sample_jsx

    def test_text_patch_by_class_selector(self, mutator: MarkToolASTMutator):
        """Mutator can select by tag + class and patch the text node."""
        sample_jsx = """
        export default function Page() {
            return <p className="description">Subtitle text</p>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="p.description",
            patch={"type": "text", "value": "Updated description"},
        )

        assert result.status == "patched"
        assert "Updated description" in result.patched_code
        assert "Subtitle text" not in result.patched_code

    def test_attribute_patch_replaces_existing(self, mutator: MarkToolASTMutator):
        """attribute patch replaces an existing JSX attribute value."""
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero" data-label="old-label">Title</h1>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={
                "type": "attribute",
                "attribute": "data-label",
                "value": "new-label",
            },
        )

        assert result.status == "patched"
        assert 'data-label={"new-label"}' in result.patched_code
        assert "old-label" not in result.patched_code

    def test_attribute_patch_adds_missing(self, mutator: MarkToolASTMutator):
        """attribute patch inserts the attribute if it is not already present."""
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={
                "type": "attribute",
                "attribute": "data-testid",
                "value": "hero-heading",
            },
        )

        assert result.status == "patched"
        assert 'data-testid={"hero-heading"}' in result.patched_code

    def test_replace_patch(self, mutator: MarkToolASTMutator):
        """replace patch swaps the whole JSX element for a new snippet."""
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={
                "type": "replace",
                "value": '<p id="hero" className="lead">Replaced</p>',
            },
        )

        assert result.status == "patched"
        assert '<p id="hero" className="lead">Replaced</p>' in result.patched_code
        assert "<h1" not in result.patched_code

    def test_replace_invalid_jsx_returns_error(self, mutator: MarkToolASTMutator):
        """replace patch rejects JSX snippets that do not parse."""
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={"type": "replace", "value": "<p"},
        )

        assert result.status == "error"
        assert "Invalid replacement JSX" in (result.message or "")

    def test_non_unique_selector_returns_unresolvable(
        self, mutator: MarkToolASTMutator
    ):
        """AC-3: more than one match returns mark_unresolvable without mutating."""
        sample_jsx = """
        export default function Page() {
            return (
                <div>
                    <h1 className="title">First</h1>
                    <h1 className="title">Second</h1>
                </div>
            );
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="h1.title",
            patch={"type": "text", "value": "Patched"},
        )

        assert result.status == "mark_unresolvable"
        assert "Patched" not in result.patched_code

    def test_self_closing_tag_unresolvable_for_text(self, mutator: MarkToolASTMutator):
        """Text patches cannot be applied to self-closing elements."""
        sample_jsx = """
        export default function Page() {
            return <img id="logo" src="/logo.png" className="h-8" />;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#logo",
            patch={"type": "text", "value": "new"},
        )

        assert result.status == "error"
        assert "self-closing" in (result.message or "").lower()

    def test_text_value_is_escaped(self, mutator: MarkToolASTMutator):
        """NFR-2: text values containing JSX control characters are escaped."""
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """

        payload = "</h1><script>alert(1)</script>"
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={"type": "text", "value": payload},
        )

        assert result.status == "patched"
        # The original closing tag must remain; the payload must be inside a JSX expression.
        assert (
            result.patched_code.count("</h1>") == 2
        )  # one inside the string, one real
        assert "alert(1)" in result.patched_code
        assert '"</h1><script>alert(1)</script>"' in result.patched_code

    def test_classname_value_is_escaped(self, mutator: MarkToolASTMutator):
        """NFR-2: className values with quotes cannot break out of the attribute."""
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero" className="old">Title</h1>;
        }
        """

        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={"type": "className", "value": 'a" onClick="evil'},
        )

        assert result.status == "patched"
        # The raw, unescaped injection string must not appear in output.
        assert 'a" onClick="evil' not in result.patched_code
        assert 'onClick="evil"' not in result.patched_code

    def test_empty_selector_is_unresolvable(self, mutator: MarkToolASTMutator):
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="   ",
            patch={"type": "text", "value": "X"},
        )
        assert result.status == "mark_unresolvable"
        assert result.patched_code == sample_jsx

    def test_multi_class_selector_requires_all_classes(
        self, mutator: MarkToolASTMutator
    ):
        sample_jsx = """
        export default function Page() {
            return (
                <div>
                    <p className="lead muted">A</p>
                    <p className="lead">B</p>
                </div>
            );
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="p.lead.muted",
            patch={"type": "text", "value": "Patched"},
        )
        assert result.status == "patched"
        assert "Patched" in result.patched_code

    def test_invalid_attribute_name_is_rejected(self, mutator: MarkToolASTMutator):
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={
                "type": "attribute",
                "attribute": "x onClick={fetch}",
                "value": "1",
            },
        )
        assert result.status == "error"
        assert "Invalid attribute name" in (result.message or "")

    def test_style_patch_writes_style_attribute(self, mutator: MarkToolASTMutator):
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Title</h1>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={"type": "style", "value": "color: red"},
        )
        assert result.status == "patched"
        assert "style=" in result.patched_code
        assert "color: red" in result.patched_code

    def test_text_patch_refuses_nested_jsx(self, mutator: MarkToolASTMutator):
        sample_jsx = """
        export default function Page() {
            return <h1 id="hero">Hello <span>World</span></h1>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero",
            patch={"type": "text", "value": "Nope"},
        )
        assert result.status == "error"
        assert "nested JSX" in (result.message or "")
        assert "<span>World</span>" in result.patched_code
