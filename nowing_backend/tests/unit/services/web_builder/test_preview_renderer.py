"""Unit tests for PreviewRenderer (Story 27.1)."""

from pathlib import Path

from app.services.web_builder.preview_renderer import PreviewRenderer


def test_preview_renderer_compiles_html_with_tailwind_and_react(tmp_path: Path):
    """Verify that PreviewRenderer loads page.tsx, globals.css and renders executable HTML."""
    app_dir = tmp_path / "web-app" / "1" / "app-123"
    app_dir.mkdir(parents=True, exist_ok=True)
    app_page = app_dir / "app" / "page.tsx"
    app_page.parent.mkdir(parents=True, exist_ok=True)
    app_css = app_dir / "app" / "globals.css"

    app_page.write_text(
        """import React from "react";

export default function Home() {
  return (
    <div className="p-8 bg-slate-900 text-white">
      <h1 id="hero-title" className="text-3xl font-bold">Crypto Tracker Pro</h1>
      <p className="text-slate-400">Track crypto in real time</p>
    </div>
  );
}""",
        encoding="utf-8",
    )

    app_css.write_text(
        """@import "tailwindcss";
body { background: black; }""",
        encoding="utf-8",
    )

    rendered_html = PreviewRenderer.render_app_html(app_dir, app_name="Crypto Tracker")

    assert "<!DOCTYPE html>" in rendered_html
    assert "cdn.tailwindcss.com" in rendered_html
    assert "unpkg.com/@babel/standalone" in rendered_html
    assert "Crypto Tracker Pro" in rendered_html
    assert "TOGGLE_MARK_TOOL" in rendered_html
    assert "MARK_ELEMENT_SELECTED" in rendered_html
