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


class TestStaticEvalMatching:
    """Spec 31-3: AST Static-Eval Policy for Dynamic JSX Expression Matching.

    Covers every row of the I/O & Edge-Case Matrix:
    - className string literal (unchanged baseline)
    - cn all-literal args
    - clsx nested literal
    - Template literal, all-literal subs
    - cn with non-known arg
    - cond && "x" guard
    - Non-whitelisted call
    - Identifier / member callee
    - Template with identifier sub
    - id literal still works
    - Patch writing path verification
    """

    def test_classname_string_literal_unchanged(
        self, mutator: MarkToolASTMutator
    ):
        """Row 1: <div className="a b"> sel .a -> match."""
        sample_jsx = """
        export default function Page() {
            return <div className="a b">Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "patched"
        assert "Updated" in result.patched_code

    def test_cn_all_literal_args(self, mutator: MarkToolASTMutator):
        """Row 2: <div className={cn("a b","c")}> sel .c -> match."""
        sample_jsx = """
        export default function Page() {
            return <div className={cn("a b", "c")}>Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".c",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "patched"
        assert "Updated" in result.patched_code

        # Also test .a and .b match
        result_a = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated A"},
        )
        assert result_a.status == "patched"

    def test_clsx_nested_literal(self, mutator: MarkToolASTMutator):
        """Row 3: <div className={clsx("a",["b","c"])}> sel .b -> match."""
        sample_jsx = """
        export default function Page() {
            return <div className={clsx("a", ["b", "c"])}>Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".b",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "patched"
        assert "Updated" in result.patched_code

        # Also test object literal inside clsx
        sample_obj_jsx = """
        export default function Page() {
            return <div className={clsx("a", { "b": true, "c": false })}>Text</div>;
        }
        """
        result_obj_b = mutator.apply_patch(
            jsx_code=sample_obj_jsx,
            selector=".b",
            patch={"type": "text", "value": "Updated B"},
        )
        assert result_obj_b.status == "patched"

        result_obj_c = mutator.apply_patch(
            jsx_code=sample_obj_jsx,
            selector=".c",
            patch={"type": "text", "value": "Updated C"},
        )
        assert result_obj_c.status == "mark_unresolvable"

    def test_template_literal_all_literal_subs(
        self, mutator: MarkToolASTMutator
    ):
        """Row 4: <div className={`px-4 ${"m"}`}> sel .m -> match."""
        sample_jsx = """
        export default function Page() {
            return <div className={`px-4 ${"m"}`}>Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".m",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "patched"
        assert "Updated" in result.patched_code

        result_px = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".px-4",
            patch={"type": "text", "value": "Updated PX"},
        )
        assert result_px.status == "patched"

    def test_cn_with_non_known_arg(self, mutator: MarkToolASTMutator):
        """Row 5: <div className={cn("a", cond)}> sel .a -> match; sel .cond -> no match."""
        sample_jsx = """
        export default function Page() {
            return <div className={cn("a", cond)}>Text</div>;
        }
        """
        result_a = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated A"},
        )
        assert result_a.status == "patched"
        assert "Updated A" in result_a.patched_code

        result_cond = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".cond",
            patch={"type": "text", "value": "Updated Cond"},
        )
        assert result_cond.status == "mark_unresolvable"

    def test_cond_and_string_guard(self, mutator: MarkToolASTMutator):
        """Row 6: <div className={cn("a", ok && "x")}> sel .a -> match; sel .x -> no match."""
        sample_jsx = """
        export default function Page() {
            return <div className={cn("a", ok && "x")}>Text</div>;
        }
        """
        result_a = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated A"},
        )
        assert result_a.status == "patched"
        assert "Updated A" in result_a.patched_code

        result_x = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".x",
            patch={"type": "text", "value": "Updated X"},
        )
        assert result_x.status == "mark_unresolvable"

    def test_non_whitelisted_call(self, mutator: MarkToolASTMutator):
        """Row 7: <div className={styles("a")}> sel .a -> None -> no match."""
        sample_jsx = """
        export default function Page() {
            return <div className={styles("a")}>Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "mark_unresolvable"
        assert result.patched_code == sample_jsx

    def test_identifier_and_member_callee(self, mutator: MarkToolASTMutator):
        """Row 8: <div className={u.cn("a")}> / {C} sel .a -> None -> no match."""
        sample_member_jsx = """
        export default function Page() {
            return <div className={u.cn("a")}>Text</div>;
        }
        """
        result_member = mutator.apply_patch(
            jsx_code=sample_member_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated"},
        )
        assert result_member.status == "mark_unresolvable"
        assert result_member.patched_code == sample_member_jsx

        sample_ident_jsx = """
        export default function Page() {
            return <div className={C}>Text</div>;
        }
        """
        result_ident = mutator.apply_patch(
            jsx_code=sample_ident_jsx,
            selector=".a",
            patch={"type": "text", "value": "Updated"},
        )
        assert result_ident.status == "mark_unresolvable"
        assert result_ident.patched_code == sample_ident_jsx

    def test_template_with_identifier_sub(self, mutator: MarkToolASTMutator):
        """Row 9: <div className={`px-${s}`}> sel .px- -> None -> no match."""
        sample_jsx = """
        export default function Page() {
            return <div className={`px-${s}`}>Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".px-",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "mark_unresolvable"
        assert result.patched_code == sample_jsx

    def test_id_literal_still_works(self, mutator: MarkToolASTMutator):
        """Row 10: <div id="i"> sel #i -> match."""
        sample_jsx = """
        export default function Page() {
            return <div id="i">Text</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="#i",
            patch={"type": "text", "value": "Updated"},
        )
        assert result.status == "patched"
        assert "Updated" in result.patched_code

        # Dynamic id expression with static string also works
        sample_dyn_id_jsx = """
        export default function Page() {
            return <div id={"dynamic-id"}>Text</div>;
        }
        """
        result_dyn = mutator.apply_patch(
            jsx_code=sample_dyn_id_jsx,
            selector="#dynamic-id",
            patch={"type": "text", "value": "Updated Dyn"},
        )
        assert result_dyn.status == "patched"
        assert "Updated Dyn" in result_dyn.patched_code

    def test_classnames_and_class_names_whitelisted(
        self, mutator: MarkToolASTMutator
    ):
        """Whitelist covers classnames and classNames variants."""
        sample_jsx = """
        export default function Page() {
            return (
                <div>
                    <span className={classnames("badge", "primary")}>One</span>
                    <span className={classNames("alert", "warn")}>Two</span>
                </div>
            );
        }
        """
        res1 = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="span.badge",
            patch={"type": "text", "value": "Patched One"},
        )
        assert res1.status == "patched"
        assert "Patched One" in res1.patched_code

        res2 = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector="span.alert",
            patch={"type": "text", "value": "Patched Two"},
        )
        assert res2.status == "patched"
        assert "Patched Two" in res2.patched_code

    def test_patch_attribute_still_writes_string_literal(
        self, mutator: MarkToolASTMutator
    ):
        """Patching className on dynamic element replaces attribute with standard string literal."""
        sample_jsx = """
        export default function Page() {
            return <div className={cn("btn", "btn-primary")}>Button</div>;
        }
        """
        result = mutator.apply_patch(
            jsx_code=sample_jsx,
            selector=".btn",
            patch={"type": "className", "value": "btn btn-secondary"},
        )
        assert result.status == "patched"
        assert 'className={"btn btn-secondary"}' in result.patched_code
        assert "cn(" not in result.patched_code


class TestStaticEvalEdgeCases:
    """Spec 31-3 review hardening: coercion, escapes, falsy, top-level exprs."""

    def _patch(self, mutator, jsx, selector):
        return mutator.apply_patch(
            jsx_code=jsx, selector=selector, patch={"type": "text", "value": "X"}
        )

    def test_falsy_zero_arg_not_a_class(self, mutator: MarkToolASTMutator):
        """cn("btn", 0) — falsy 0 must NOT become a .0 token."""
        jsx = 'export default function P(){return <div className={cn("btn", 0)}>t</div>}'
        assert self._patch(mutator, jsx, ".btn").status == "patched"
        assert self._patch(mutator, jsx, ".0").status == "mark_unresolvable"

    def test_binary_plus_bool_coercion_lowercase(self, mutator: MarkToolASTMutator):
        """"is-" + false -> "is-false" (JS lowercase), not "is-False"."""
        jsx = 'export default function P(){return <div className={"is-" + false}>t</div>}'
        assert self._patch(mutator, jsx, ".is-false").status == "patched"
        assert self._patch(mutator, jsx, ".is-False").status == "mark_unresolvable"

    def test_binary_plus_null_coercion(self, mutator: MarkToolASTMutator):
        """"v-" + null -> "v-null" (JS), consistent with template `${null}`."""
        jsx = 'export default function P(){return <div className={"v-" + null}>t</div>}'
        assert self._patch(mutator, jsx, ".v-null").status == "patched"

    def test_template_null_sub_coerces(self, mutator: MarkToolASTMutator):
        """`v-${null}` -> "v-null" (consistent with binary +)."""
        jsx = 'export default function P(){return <div className={`v-${null}`}>t</div>}'
        assert self._patch(mutator, jsx, ".v-null").status == "patched"

    def test_single_quoted_escape_decoded(self, mutator: MarkToolASTMutator):
        """'a\\nb' single-quoted escape decodes; token 'a' after split."""
        jsx = "export default function P(){return <div className='a\\nb'>t</div>}"
        assert self._patch(mutator, jsx, ".a").status == "patched"

    def test_tailwind_colon_escape(self, mutator: MarkToolASTMutator):
        """"hover\:bg" -> 'hover:bg' (JS-only escape decoded)."""
        jsx = 'export default function P(){return <div className={cn("hover\\:bg")}>t</div>}'
        assert self._patch(mutator, jsx, ".hover:bg").status == "patched"

    def test_numeric_literal_radices(self, mutator: MarkToolASTMutator):
        """hex/octal/bigint args resolve; falsy 0x0 dropped."""
        jsx = 'export default function P(){return <div className={cn("a", 0x10)}>t</div>}'
        assert self._patch(mutator, jsx, ".16").status == "patched"

    def test_empty_cn_resolves_empty_not_none(self, mutator: MarkToolASTMutator):
        """cn("") resolves to "" — consistent with className={""}."""
        jsx = 'export default function P(){return <div className={cn("")}>t</div>}'
        # "" has no tokens; a class selector must not match, but no crash either.
        assert self._patch(mutator, jsx, ".a").status == "mark_unresolvable"

    def test_top_level_binary_concat(self, mutator: MarkToolASTMutator):
        """className={"btn " + "btn-primary"} resolves at top level."""
        jsx = 'export default function P(){return <div className={"btn " + "btn-primary"}>t</div>}'
        assert self._patch(mutator, jsx, ".btn-primary").status == "patched"

    def test_top_level_nullish(self, mutator: MarkToolASTMutator):
        """className={null ?? "default"} -> "default"."""
        jsx = 'export default function P(){return <div className={null ?? "default"}>t</div>}'
        assert self._patch(mutator, jsx, ".default").status == "patched"

    def test_top_level_logical_or(self, mutator: MarkToolASTMutator):
        """className={false || "fallback"} -> "fallback"."""
        jsx = 'export default function P(){return <div className={false || "fallback"}>t</div>}'
        assert self._patch(mutator, jsx, ".fallback").status == "patched"

    def test_top_level_ternary(self, mutator: MarkToolASTMutator):
        """className={true ? "on" : "off"} -> "on"."""
        jsx = 'export default function P(){return <div className={true ? "on" : "off"}>t</div>}'
        assert self._patch(mutator, jsx, ".on").status == "patched"
        assert self._patch(mutator, jsx, ".off").status == "mark_unresolvable"

    def test_object_literal_truthy_keys(self, mutator: MarkToolASTMutator):
        """clsx({ "active": true, "off": false }) -> only truthy key emitted."""
        jsx = 'export default function P(){return <div className={clsx({ "active": true, "off": false })}>t</div>}'
        assert self._patch(mutator, jsx, ".active").status == "patched"
        assert self._patch(mutator, jsx, ".off").status == "mark_unresolvable"


    def test_spread_static_array(self, mutator: MarkToolASTMutator):
        """cn("a", ...["b","c"]) flattens the spread into tokens."""
        jsx = 'export default function P(){return <div className={cn("a", ...["b","c"])}>t</div>}'
        assert self._patch(mutator, jsx, ".b").status == "patched"
        assert self._patch(mutator, jsx, ".c").status == "patched"

    def test_computed_property_name_literal(self, mutator: MarkToolASTMutator):
        """clsx({ ["btn-primary"]: true }) emits the computed key."""
        jsx = 'export default function P(){return <div className={clsx({ ["btn-primary"]: true })}>t</div>}'
        assert self._patch(mutator, jsx, ".btn-primary").status == "patched"

    def test_and_array_literal(self, mutator: MarkToolASTMutator):
        """cn(true && ["a","b"]) evaluates the array via _eval_node."""
        jsx = 'export default function P(){return <div className={cn(true && ["a","b"])}>t</div>}'
        assert self._patch(mutator, jsx, ".a").status == "patched"
        assert self._patch(mutator, jsx, ".b").status == "patched"

    def test_satisfies_expression(self, mutator: MarkToolASTMutator):
        """cn("a" satisfies string) unwraps to the string."""
        jsx = 'export default function P(){return <div className={cn("a" satisfies string)}>t</div>}'
        assert self._patch(mutator, jsx, ".a").status == "patched"

    def test_non_null_unknown_still_failsafe(self, mutator: MarkToolASTMutator):
        """cn(classes!) — identifier still unknown, no false-positive."""
        jsx = 'export default function P(){return <div className={cn(classes!)}>t</div>}'
        assert self._patch(mutator, jsx, ".classes").status == "mark_unresolvable"
