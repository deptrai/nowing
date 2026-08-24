"""Interactive HTML Preview Renderer for Web Builder (Story 27.1, AC-1).

Renders Next.js 16 + React 19 + Tailwind CSS projects as a self-contained,
interactive HTML page with live Tailwind CDN, Babel/React runtime, and Lucide icons.
"""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ponytail: allow any HTTPS connect-src so generated apps can post lead forms,
# load analytics, and call external APIs. Hardening to per-app allow-lists is
# the next step once app authors can declare their endpoints.
WEB_BUILDER_CSP = (
    "default-src 'self' 'unsafe-inline' https:; "
    "img-src 'self' data: https: blob:; "
    "font-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https: https://fonts.googleapis.com; "
    "connect-src 'self' https:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com;"
)


class PreviewRenderer:
    """Renders stored Next.js web application files into an interactive HTML preview."""

    @staticmethod
    def render_app_html(project_dir: Path | str, app_name: str = "Web App") -> str:
        """Read project files and compile a self-contained interactive browser HTML document."""
        base_dir = Path(project_dir).resolve()

        page_tsx_path = base_dir / "app" / "page.tsx"
        globals_css_path = base_dir / "app" / "globals.css"

        page_code = (
            page_tsx_path.read_text(encoding="utf-8")
            if page_tsx_path.exists()
            else f"""export default function Home() {{
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-slate-950 text-white text-center">
      <h1 id="hero-title" className="text-4xl font-extrabold text-indigo-400 mb-4">{html.escape(app_name)}</h1>
      <p className="text-slate-400 text-lg">Application ready for customization.</p>
    </div>
  );
}}"""
        )

        custom_css = (
            globals_css_path.read_text(encoding="utf-8")
            if globals_css_path.exists()
            else ""
        )
        custom_css_clean = (
            custom_css.replace('@import "tailwindcss";', "")
            .replace("@tailwind base;", "")
            .replace("@tailwind components;", "")
            .replace("@tailwind utilities;", "")
        )

        sanitized_jsx = PreviewRenderer._sanitize_tsx_for_babel(page_code)

        html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="{WEB_BUILDER_CSP}">
  <title>{html.escape(app_name)} - Live Preview</title>
  
  <!-- Tailwind CSS CDN -->
  <!-- Fallback if any CDN fails to load -->
  <script>
    window.__webBuilderCdnFallback = function() {{
      const root = document.getElementById('root');
      if (root) {{
        root.innerHTML = '<div class="min-h-screen flex flex-col items-center justify-center p-8 bg-slate-950 text-white text-center"><div><h1 class="text-2xl font-bold text-indigo-400 mb-2">Preview unavailable</h1><p class="text-slate-400">A required CDN resource could not be loaded. Please try again later.</p></div></div>';
      }}
    }};
  </script>

  <script src="https://cdn.tailwindcss.com" onerror="__webBuilderCdnFallback()"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            brand: {{
              50: '#eef2ff',
              100: '#e0e7ff',
              200: '#c7d2fe',
              300: '#a5b4fc',
              400: '#818cf8',
              500: '#6366f1',
              600: '#4f46e5',
              700: '#4338ca',
              800: '#3730a3',
              900: '#312e81',
            }}
          }}
        }}
      }}
    }}
  </script>

  <!-- React 18 & Babel Standalone for live in-browser JSX execution -->
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js" onerror="__webBuilderCdnFallback()"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" onerror="__webBuilderCdnFallback()"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js" onerror="__webBuilderCdnFallback()"></script>
  
  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest" onerror="__webBuilderCdnFallback()"></script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">

  <style>
    body {{
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 0;
    }}
    .nowing-mark-hover {{
      outline: 2px dashed #6366f1 !important;
      outline-offset: 2px !important;
      cursor: crosshair !important;
    }}
    .nowing-mark-selected {{
      outline: 2px solid #4f46e5 !important;
      outline-offset: 2px !important;
      background-color: rgba(99, 102, 241, 0.1) !important;
    }}
    {custom_css_clean}
  </style>
</head>
<body class="bg-slate-950 text-slate-50 min-h-screen antialiased selection:bg-indigo-500 selection:text-white">
  <div id="root"></div>

  <script type="text/babel">
    const {{ useState, useEffect, useMemo, useRef }} = React;

    {sanitized_jsx}

    const rootElement = document.getElementById('root');
    const root = ReactDOM.createRoot(rootElement);
    
    const MainComponent = typeof Home !== 'undefined' ? Home : 
                          (typeof App !== 'undefined' ? App : 
                          (typeof Page !== 'undefined' ? Page : () => <div>Application Ready</div>));

    root.render(<MainComponent />);
  </script>

  <script>
    let markToolActive = false;
    let hoveredElement = null;

    window.addEventListener('message', (event) => {{
      if (event.data?.type === 'TOGGLE_MARK_TOOL') {{
        markToolActive = !!event.data.active;
        if (!markToolActive && hoveredElement) {{
          hoveredElement.classList.remove('nowing-mark-hover');
          hoveredElement = null;
        }}
      }}
    }});

    document.addEventListener('mouseover', (e) => {{
      if (!markToolActive) return;
      if (hoveredElement && hoveredElement !== e.target) {{
        hoveredElement.classList.remove('nowing-mark-hover');
      }}
      hoveredElement = e.target;
      hoveredElement.classList.add('nowing-mark-hover');
    }});

    document.addEventListener('mouseout', (e) => {{
      if (!markToolActive) return;
      if (hoveredElement) {{
        hoveredElement.classList.remove('nowing-mark-hover');
        hoveredElement = null;
      }}
    }});

    document.addEventListener('click', (e) => {{
      if (!markToolActive) return;
      e.preventDefault();
      e.stopPropagation();
      
      const target = e.target;
      const id = target.id ? '#' + target.id : '';
      const tag = target.tagName.toLowerCase();
      const firstClass = target.className && typeof target.className === 'string' 
        ? '.' + target.className.split(' ')[0] 
        : '';
      const selector = id || (firstClass ? tag + firstClass : tag);
      const text = target.innerText || target.textContent || '';

      window.parent.postMessage({{
        type: 'MARK_ELEMENT_SELECTED',
        selector: selector,
        tag: tag,
        text: text.trim(),
      }}, '*');
    }}, true);

    window.addEventListener('DOMContentLoaded', () => {{
      if (window.lucide) {{
        window.lucide.createIcons();
      }}
    }});
  </script>
</body>
</html>"""
        return html_template

    @staticmethod
    def _sanitize_tsx_for_babel(tsx_code: str) -> str:
        """Strip TypeScript syntax and sanitize scripts from Next.js component for browser Babel."""
        code = tsx_code

        # Prevent closing Babel script tag injection
        code = re.sub(r"</script>", r"<\/script>", code, flags=re.IGNORECASE)

        # Strip access to sensitive browser storage / auth tokens
        code = re.sub(r"\bdocument\.cookie\b", "''", code)
        code = re.sub(
            r"\blocalStorage\b", "{ getItem: () => null, setItem: () => {} }", code
        )
        code = re.sub(
            r"\bsessionStorage\b", "{ getItem: () => null, setItem: () => {} }", code
        )

        # Strip imports
        code = re.sub(r"import\s+[^;]+;?", "", code)

        # Replace export statements
        code = re.sub(r"export\s+default\s+function\s*", "function ", code)
        code = re.sub(r"export\s+function\s*", "function ", code)
        code = re.sub(r"export\s+const\s*", "const ", code)

        # Strip interface / type blocks
        code = re.sub(
            r"(?:interface|type)\s+[A-Za-z0-9_]+\s*=?\s*\{[^}]*\};?", "", code
        )

        # Strip generic types and type annotations (uppercase and lowercase)
        code = re.sub(r":\s*[A-Za-z_][a-zA-Z0-9_<>\[\]|&\s]*", "", code)
        code = re.sub(r"as\s+[A-Za-z_][a-zA-Z0-9_<>\[\]]*", "", code)

        return code
