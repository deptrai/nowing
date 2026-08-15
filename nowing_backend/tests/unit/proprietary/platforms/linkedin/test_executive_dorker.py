"""Unit tests for LinkedIn Executive SERP Dorking (Story 21.9 / AD-LI-4)."""

from __future__ import annotations

import pytest
import respx

from app.proprietary.platforms.linkedin.executive_dorker import (
    ExecutiveDorker,
)
from app.proprietary.platforms.linkedin.executive_parser import (
    ExecutiveParser,
    parse_linkedin_slug,
    parse_serp_title_and_snippet,
)
from app.proprietary.platforms.linkedin.query_builder import build_serp_dork_query
from app.proprietary.platforms.linkedin.schemas import ExecutiveProfile


def test_build_serp_dork_query_defaults() -> None:
    """Query builder includes company name and default executive leadership roles."""
    query = build_serp_dork_query("Vingroup")
    assert "site:linkedin.com/in/" in query
    assert '"Vingroup"' in query
    assert '"CEO"' in query
    assert '"Founder"' in query or '"HR Director"' in query


def test_build_serp_dork_query_custom_roles_and_escaping() -> None:
    """Query builder handles custom role lists and escapes double quotes in company name."""
    query = build_serp_dork_query('Công ty "FPT" Software', roles=["CTO", "CFO"])
    assert "site:linkedin.com/in/" in query
    assert '"Công ty FPT Software"' in query or '"Công ty \\"FPT\\" Software"' in query or '"Công ty FPT Software"' in query
    assert '("CTO" OR "CFO")' in query


def test_parse_linkedin_slug() -> None:
    """Extract clean LinkedIn slug from various URL formats."""
    assert (
        parse_linkedin_slug("https://vn.linkedin.com/in/nguyen-van-a-12345")
        == "nguyen-van-a-12345"
    )
    assert (
        parse_linkedin_slug("https://www.linkedin.com/in/john-doe/")
        == "john-doe"
    )
    assert (
        parse_linkedin_slug("https://linkedin.com/in/alice_smith?ref=search")
        == "alice_smith"
    )
    assert parse_linkedin_slug("https://google.com/search?q=test") is None
    assert parse_linkedin_slug("") is None


def test_parse_serp_title_and_snippet() -> None:
    """Extract executive name and role from Google SERP title format."""
    title_1 = "Nguyen Van A - Chief Executive Officer - FPT Software | LinkedIn"
    snippet_1 = "Nguyen Van A is the CEO of FPT Software based in Hanoi, Vietnam."
    name, role, _company = parse_serp_title_and_snippet(title_1, snippet_1, target_company="FPT Software")
    assert name == "Nguyen Van A"
    assert "Chief Executive Officer" in (role or "")

    title_2 = "Jane Doe - HR Director at TechCorp | LinkedIn"
    snippet_2 = "Experienced HR Director with a demonstrated history of working in tech."
    name_2, role_2, _ = parse_serp_title_and_snippet(title_2, snippet_2)
    assert name_2 == "Jane Doe"
    assert role_2 == "HR Director"


MOCK_GOOGLE_SERP_HTML = """
<!DOCTYPE html>
<html>
<body>
  <div class="g">
    <div class="tF2Cxc">
      <div class="yuRUbf">
        <a href="https://vn.linkedin.com/in/nguyen-van-b-998877">
          <h3 class="LC20lb">Nguyen Van B - Founder & CEO - VNTech Solutions | LinkedIn</h3>
        </a>
      </div>
      <div class="VwiC3b">
        <span>Nguyen Van B is Founder &amp; CEO of VNTech Solutions, leading product innovation and strategy.</span>
      </div>
    </div>
  </div>
  <div class="g">
    <div class="tF2Cxc">
      <div class="yuRUbf">
        <a href="https://vn.linkedin.com/in/tran-thi-c-112233">
          <h3 class="LC20lb">Tran Thi C - Human Resources Director - VNTech Solutions | LinkedIn</h3>
        </a>
      </div>
      <div class="VwiC3b">
        <span>Tran Thi C leads talent acquisition and HR operations at VNTech Solutions.</span>
      </div>
    </div>
  </div>
</body>
</html>
"""


def test_parse_serp_html() -> None:
    """HTML parser extracts structured executive profiles from Google SERP results."""
    parser = ExecutiveParser()
    profiles = parser.parse_serp_html(
        html_content=MOCK_GOOGLE_SERP_HTML,
        target_company="VNTech Solutions",
        domain="vntech.vn",
    )
    assert len(profiles) == 2
    assert profiles[0].full_name == "Nguyen Van B"
    assert "CEO" in (profiles[0].title or "")
    assert profiles[0].linkedin_slug == "nguyen-van-b-998877"
    assert profiles[0].linkedin_url == "https://vn.linkedin.com/in/nguyen-van-b-998877"
    assert any("vntech.vn" in email for email in profiles[0].inferred_emails)

    assert profiles[1].full_name == "Tran Thi C"
    assert "Human Resources Director" in (profiles[1].title or "")
    assert profiles[1].linkedin_slug == "tran-thi-c-112233"


@pytest.mark.asyncio
@respx.mock
async def test_executive_dorker_fetch_and_parse() -> None:
    """ExecutiveDorker sends HTTP request, parses HTML, and returns executive list."""
    respx.get("https://html.duckduckgo.com/html/").respond(
        status_code=200,
        html=MOCK_GOOGLE_SERP_HTML,
    )

    dorker = ExecutiveDorker(search_endpoint="https://html.duckduckgo.com/html/")
    results = await dorker.dork_executives(
        company_name="VNTech Solutions",
        roles=["CEO", "HR Director"],
        domain="vntech.vn",
        limit=5,
    )

    assert len(results) >= 2
    assert isinstance(results[0], ExecutiveProfile)
    assert results[0].full_name == "Nguyen Van B"
    assert results[0].linkedin_slug == "nguyen-van-b-998877"


def test_parse_serp_title_pipe_and_vietnamese_prepositions() -> None:
    """Delimiters like pipe and Vietnamese prepositions ('tại', 'ở') are correctly parsed."""
    title_1 = "Nguyen Van A | Giám đốc Điều hành tại Tập đoàn FPT | LinkedIn"
    name, role, comp = parse_serp_title_and_snippet(title_1, "", target_company="FPT")
    assert name == "Nguyen Van A"
    assert role == "Giám đốc Điều hành"
    assert comp == "Tập đoàn FPT"

    title_2 = "Jane Doe • Head of Growth ở Vingroup | LinkedIn"
    name_2, role_2, comp_2 = parse_serp_title_and_snippet(title_2, "")
    assert name_2 == "Jane Doe"
    assert role_2 == "Head of Growth"
    assert comp_2 == "Vingroup"


def test_build_serp_dork_query_sanitizes_injection_and_quotes() -> None:
    """Dork query builder sanitizes role terms and company names to prevent injection."""
    query = build_serp_dork_query(
        'Vingroup "JSC"',
        roles=['CEO"', 'Founder) OR (site:evil.com'],
    )
    assert "site:linkedin.com/in/" in query
    assert '"Vingroup JSC"' in query
    assert '("CEO" OR "Founder OR site:evil.com")' in query



def test_parse_serp_html_ddg_encoded_links_and_unescaped_html() -> None:
    """Parser handles DuckDuckGo URL-encoded redirect links and unescapes HTML entities."""
    raw_html = """
    <div>
        <a href="/l/?uddg=https%3A%2F%2Fvn.linkedin.com%2Fin%2Fle-hoang-nam-556677&rut=1">
            <h3>Le Hoang Nam - Founder &amp; CEO - Tiki &amp; Sendo | LinkedIn</h3>
        </a>
    </div>
    """
    parser = ExecutiveParser()
    profiles = parser.parse_serp_html(raw_html, "Tiki")
    assert len(profiles) == 1
    assert profiles[0].linkedin_slug == "le-hoang-nam-556677"
    assert profiles[0].full_name == "Le Hoang Nam"
    assert profiles[0].title == "Founder & CEO"

