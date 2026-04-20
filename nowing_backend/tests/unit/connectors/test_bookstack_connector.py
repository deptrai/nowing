"""Unit tests for BookStackConnector — PR #894 (shelf exclusion + N+1 fix)."""

from unittest.mock import MagicMock, call, patch

import pytest

from app.connectors.bookstack_connector import BookStackConnector

pytestmark = pytest.mark.unit


def _make_connector() -> BookStackConnector:
    """Return a BookStackConnector with credentials pre-set (no real HTTP)."""
    c = BookStackConnector(
        base_url="https://wiki.example.com",
        token_id="tid",
        token_secret="tsecret",
    )
    return c


# ---------------------------------------------------------------------------
# get_all_shelves
# ---------------------------------------------------------------------------


def test_get_all_shelves_single_page(monkeypatch):
    """get_all_shelves returns all shelves when everything fits in one page."""
    conn = _make_connector()

    shelves_data = [{"id": 1, "name": "Shelf A"}, {"id": 2, "name": "Shelf B"}]
    api_response = {"data": shelves_data, "total": 2}

    monkeypatch.setattr(conn, "make_api_request", MagicMock(return_value=api_response))

    result = conn.get_all_shelves()

    assert result == shelves_data
    conn.make_api_request.assert_called_once_with(
        "shelves", {"count": 500, "offset": 0}
    )


def test_get_all_shelves_pagination(monkeypatch):
    """get_all_shelves paginates correctly when total > page size."""
    conn = _make_connector()

    page1 = {"data": [{"id": 1, "name": "Shelf A"}], "total": 2}
    page2 = {"data": [{"id": 2, "name": "Shelf B"}], "total": 2}

    monkeypatch.setattr(
        conn, "make_api_request", MagicMock(side_effect=[page1, page2])
    )

    result = conn.get_all_shelves()

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2
    assert conn.make_api_request.call_count == 2


def test_get_all_shelves_empty(monkeypatch):
    """get_all_shelves returns empty list when there are no shelves."""
    conn = _make_connector()

    monkeypatch.setattr(
        conn, "make_api_request", MagicMock(return_value={"data": [], "total": 0})
    )

    result = conn.get_all_shelves()

    assert result == []


def test_get_all_shelves_invalid_response_raises(monkeypatch):
    """get_all_shelves raises Exception on malformed API response."""
    conn = _make_connector()

    monkeypatch.setattr(conn, "make_api_request", MagicMock(return_value="bad"))

    with pytest.raises(Exception, match="Invalid response"):
        conn.get_all_shelves()


# ---------------------------------------------------------------------------
# build_book_to_shelf_map
# ---------------------------------------------------------------------------


def test_build_book_to_shelf_map_basic(monkeypatch):
    """build_book_to_shelf_map returns correct book_id -> set(shelf_ids) mapping."""
    conn = _make_connector()

    shelves = [{"id": 10, "name": "S1"}, {"id": 20, "name": "S2"}]

    def _fake_request(endpoint, params=None):
        if endpoint == "shelves/10":
            return {"books": [{"id": 100}, {"id": 200}]}
        if endpoint == "shelves/20":
            return {"books": [{"id": 200}, {"id": 300}]}
        return {"data": shelves, "total": len(shelves)}

    monkeypatch.setattr(conn, "get_all_shelves", MagicMock(return_value=shelves))
    monkeypatch.setattr(conn, "make_api_request", MagicMock(side_effect=_fake_request))

    result = conn.build_book_to_shelf_map()

    assert result[100] == {10}
    assert result[200] == {10, 20}  # book 200 is in both shelves
    assert result[300] == {20}


def test_build_book_to_shelf_map_book_in_multiple_shelves(monkeypatch):
    """A book that belongs to multiple shelves must have all shelf_ids in its set."""
    conn = _make_connector()

    shelves = [{"id": 1}, {"id": 2}, {"id": 3}]

    def _fake_request(endpoint, params=None):
        # Book 42 is in all three shelves
        return {"books": [{"id": 42}]}

    monkeypatch.setattr(conn, "get_all_shelves", MagicMock(return_value=shelves))
    monkeypatch.setattr(conn, "make_api_request", MagicMock(side_effect=_fake_request))

    result = conn.build_book_to_shelf_map()

    assert result[42] == {1, 2, 3}


def test_build_book_to_shelf_map_empty_shelves(monkeypatch):
    """build_book_to_shelf_map returns empty dict when there are no shelves."""
    conn = _make_connector()

    monkeypatch.setattr(conn, "get_all_shelves", MagicMock(return_value=[]))
    make_api_mock = MagicMock()
    monkeypatch.setattr(conn, "make_api_request", make_api_mock)

    result = conn.build_book_to_shelf_map()

    assert result == {}
    make_api_mock.assert_not_called()


# ---------------------------------------------------------------------------
# get_all_pages — no exclusion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "excluded_shelf_ids,pages",
    [
        ([], [{"id": 1, "book_id": 10}, {"id": 2, "book_id": 20}, {"id": 3, "book_id": 30}]),
        (None, [{"id": 1, "book_id": 10}]),
    ],
    ids=["empty_list", "none_default"],
)
def test_get_all_pages_no_exclusion_returns_all(monkeypatch, excluded_shelf_ids, pages):
    """get_all_pages with excluded_shelf_ids=[] or None returns every page without calling build_map."""
    conn = _make_connector()
    monkeypatch.setattr(
        conn,
        "make_api_request",
        MagicMock(return_value={"data": pages, "total": len(pages)}),
    )
    build_map_mock = MagicMock()
    monkeypatch.setattr(conn, "build_book_to_shelf_map", build_map_mock)

    if excluded_shelf_ids is None:
        result = conn.get_all_pages()
    else:
        result = conn.get_all_pages(excluded_shelf_ids=excluded_shelf_ids)

    assert result == pages
    build_map_mock.assert_not_called()


# ---------------------------------------------------------------------------
# get_all_pages — with shelf exclusion
# ---------------------------------------------------------------------------


def test_get_all_pages_excludes_pages_in_shelf(monkeypatch):
    """get_all_pages filters out pages whose book belongs to an excluded shelf."""
    conn = _make_connector()

    # Three pages: books 10, 20, 30 — shelf 99 contains book 20
    pages = [
        {"id": 1, "book_id": 10},
        {"id": 2, "book_id": 20},
        {"id": 3, "book_id": 30},
    ]
    monkeypatch.setattr(
        conn,
        "make_api_request",
        MagicMock(return_value={"data": pages, "total": 3}),
    )
    # Shelf map: book 20 -> shelf 99
    monkeypatch.setattr(
        conn,
        "build_book_to_shelf_map",
        MagicMock(return_value={10: {1}, 20: {99}, 30: {2}}),
    )

    result = conn.get_all_pages(excluded_shelf_ids=[99])

    ids = [p["id"] for p in result]
    assert 2 not in ids, "Page belonging to excluded shelf 99 must be filtered out"
    assert 1 in ids
    assert 3 in ids


def test_get_all_pages_excludes_multiple_shelves(monkeypatch):
    """Pages from any of the excluded shelves are all removed."""
    conn = _make_connector()

    pages = [
        {"id": 1, "book_id": 10},  # shelf 1
        {"id": 2, "book_id": 20},  # shelf 2 — excluded
        {"id": 3, "book_id": 30},  # shelf 3 — excluded
        {"id": 4, "book_id": 40},  # shelf 4
    ]
    monkeypatch.setattr(
        conn,
        "make_api_request",
        MagicMock(return_value={"data": pages, "total": 4}),
    )
    monkeypatch.setattr(
        conn,
        "build_book_to_shelf_map",
        MagicMock(return_value={10: {1}, 20: {2}, 30: {3}, 40: {4}}),
    )

    result = conn.get_all_pages(excluded_shelf_ids=[2, 3])

    ids = [p["id"] for p in result]
    assert ids == [1, 4]


def test_get_all_pages_page_in_multiple_shelves_excluded_if_any_match(monkeypatch):
    """A page whose book is in multiple shelves is excluded if ANY of those shelves is excluded."""
    conn = _make_connector()

    pages = [{"id": 1, "book_id": 10}]
    monkeypatch.setattr(
        conn,
        "make_api_request",
        MagicMock(return_value={"data": pages, "total": 1}),
    )
    # Book 10 belongs to shelves 5 and 6; we exclude shelf 6
    monkeypatch.setattr(
        conn,
        "build_book_to_shelf_map",
        MagicMock(return_value={10: {5, 6}}),
    )

    result = conn.get_all_pages(excluded_shelf_ids=[6])

    assert result == [], "Page must be excluded because its book is in excluded shelf 6"


# ---------------------------------------------------------------------------
# N+1 fix — build_book_to_shelf_map called exactly once
# ---------------------------------------------------------------------------


def test_get_all_pages_build_map_called_once(monkeypatch):
    """build_book_to_shelf_map must be called exactly once (not per page) — N+1 fix."""
    conn = _make_connector()

    pages = [{"id": i, "book_id": i * 10} for i in range(1, 6)]
    monkeypatch.setattr(
        conn,
        "make_api_request",
        MagicMock(return_value={"data": pages, "total": len(pages)}),
    )
    build_map_mock = MagicMock(return_value={})
    monkeypatch.setattr(conn, "build_book_to_shelf_map", build_map_mock)

    conn.get_all_pages(excluded_shelf_ids=[99])

    build_map_mock.assert_called_once()
