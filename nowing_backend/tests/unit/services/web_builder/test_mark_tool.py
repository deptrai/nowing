"""Unit tests for Design View Mark Tool (Story 27.1, AC-4).

Acceptance Criteria:
- AC-4: Mark Tool bounding box selector mapping & JSX AST mutation.
"""

import pytest

pytestmark = [pytest.mark.unit]


class TestMarkToolASTMutator:
    """AC-4: Mark Tool AST Mutation tests."""

    @pytest.mark.skip(reason="RED-PHASE: MarkToolASTMutator not yet implemented")
    def test_map_selector_to_jsx_node_and_apply_text_patch(self):
        """AC-4: Given a CSS selector / XPath and text patch, mutator updates JSX AST correctly."""
        from app.services.web_builder.mark_tool import MarkToolASTMutator

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

        mutator = MarkToolASTMutator()
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#hero-title",
            patch={"type": "text", "value": "Updated Hero Headline"},
        )

        assert result.status == "patched"
        assert "Updated Hero Headline" in result.patched_code
        assert "Original Title" not in result.patched_code

    @pytest.mark.skip(reason="RED-PHASE: MarkToolASTMutator not yet implemented")
    def test_map_selector_apply_style_patch(self):
        """AC-4: Given a selector and style patch, mutator updates className attributes."""
        from app.services.web_builder.mark_tool import MarkToolASTMutator

        sample_jsx = """
        export default function Hero() {
            return <button id="cta-btn" className="bg-blue-500 text-white">Click Me</button>;
        }
        """

        mutator = MarkToolASTMutator()
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#cta-btn",
            patch={"type": "className", "value": "bg-emerald-600 text-white font-semibold"},
        )

        assert result.status == "patched"
        assert "bg-emerald-600" in result.patched_code

    @pytest.mark.skip(reason="RED-PHASE: MarkToolASTMutator not yet implemented")
    def test_unresolvable_selector_returns_graceful_status(self):
        """AC-4: Given a selector not matching any JSX node, return status mark_unresolvable without mutating."""
        from app.services.web_builder.mark_tool import MarkToolASTMutator

        sample_jsx = """
        export default function Page() {
            return <div><h1>Title</h1></div>;
        }
        """

        mutator = MarkToolASTMutator()
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#non-existent-element",
            patch={"type": "text", "value": "New Value"},
        )

        assert result.status == "mark_unresolvable"
        assert result.patched_code == sample_jsx
