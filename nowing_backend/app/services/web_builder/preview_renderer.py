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

  <!-- React 18 & Babel Standalone for live in-browser JSX/TSX execution -->
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

  <!-- CDN-fallback must be defined after #root exists, or wait for load. -->
  <script>
    window.__webBuilderCdnFallback = function() {{
      var fallbackHtml = '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#fff;font-family:Inter,sans-serif;text-align:center;padding:2rem;"><div><h1 style="font-size:1.5rem;font-weight:700;color:#818cf8;margin:0 0 .5rem;">Preview unavailable</h1><p style="color:#94a3b8;margin:0;">A required CDN resource could not be loaded. Please try again later.</p></div></div>';
      var root = document.getElementById('root');
      if (root) {{
        root.innerHTML = fallbackHtml;
      }} else {{
        window.addEventListener('load', function() {{
          root = document.getElementById('root');
          if (root) root.innerHTML = fallbackHtml;
        }});
      }}
    }};
  </script>

  <script id="wb-source" type="text/template">
    const React = window.React;
    const ReactDOM = window.ReactDOM;
    const {{ useState, useEffect, useMemo, useRef }} = React;

    {sanitized_jsx}

    const rootElement = document.getElementById('root');
    const root = ReactDOM.createRoot(rootElement);

    const __wbAppKey = Object.keys(window).find(function(k) {{
      if (__wbKnownGlobals.has(k)) return false;
      if (['__wbKnownGlobals', 'MainComponent'].includes(k)) return false;
      if (typeof window[k] !== 'function') return false;
      if (window[k] && window[k].__wbIcon) return false;
      return /^[A-Z]/.test(k);
    }});

    const MainComponent =
      (typeof Home === 'function' && !(Home && Home.__wbIcon)) ? Home :
      (typeof App === 'function' && !(App && App.__wbIcon)) ? App :
      (typeof Page === 'function' && !(Page && Page.__wbIcon)) ? Page :
      (__wbAppKey && typeof window[__wbAppKey] === 'function' && !window[__wbAppKey].__wbIcon
        ? window[__wbAppKey]
        : function() {{ return React.createElement('div', null, 'Application Ready'); }});

    root.render(React.createElement(MainComponent));
  </script>

  <script type="text/javascript">
    (function() {{
      if (typeof Babel === 'undefined' || typeof React === 'undefined' || typeof ReactDOM === 'undefined' || typeof lucide === 'undefined') {{
        if (typeof __webBuilderCdnFallback === 'function') __webBuilderCdnFallback();
        return;
      }}
      window.__wbKnownGlobals = new Set(Object.keys(window));

      const source = document.getElementById('wb-source').textContent;
      const iconMatch = source.match(/\\b[A-Z][A-Za-z0-9]+\\b/g) || [];
      const iconNames = Array.from(new Set(iconMatch)).filter(function(k) {{
        if (typeof window[k] !== 'undefined') return false;
        return k in lucide && Array.isArray(lucide[k]);
      }});

      iconNames.forEach(function(name) {{
        window[name] = (function(name) {{
          var icon = lucide[name];
          var fn = function(props) {{
            return React.createElement('svg', Object.assign({{
              xmlns: 'http://www.w3.org/2000/svg',
              width: 24,
              height: 24,
              viewBox: '0 0 24 24',
              fill: 'none',
              stroke: 'currentColor',
              strokeWidth: 2,
              strokeLinecap: 'round',
              strokeLinejoin: 'round'
            }}, props), icon.map(function(node, i) {{
              return React.createElement(node[0], Object.assign({{ key: i }}, node[1]));
            }}));
          }};
          fn.__wbIcon = true;
          return fn;
        }})(name);
      }});

      try {{
        const transformed = Babel.transform(source, {{
          presets: [['react', {{ runtime: 'classic' }}], 'typescript'],
          filename: 'page.tsx',
        }}).code;
        const script = document.createElement('script');
        script.textContent = transformed;
        document.body.appendChild(script);
      }} catch (err) {{
        console.error('Babel transform failed:', err);
        if (typeof __webBuilderCdnFallback === 'function') __webBuilderCdnFallback();
      }}
    }})();
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
        """Sanitize TSX for in-browser Babel execution.

        Babel standalone is configured with the ``typescript`` preset, so we do
        not strip TypeScript type annotations by regex. We only escape the
        closing ``</script>`` tag and neutralise storage/auth APIs and dynamic
        imports that could leak data or fetch external code (P8).
        """
        code = tsx_code

        # Prevent generated code from closing the Babel <script> tag.
        code = re.sub(r"</script\s*>", r"<\\/script>", code, flags=re.IGNORECASE)

        # Neutralise storage / auth token access. Replacing with ({}).cookie
        # keeps the syntax valid on both read and assignment sides.
        code = re.sub(r"\bwindow\.document\.cookie\b", "({}).cookie", code)
        code = re.sub(r"\bdocument\[(['\"])cookie\1\]", "({}).cookie", code)
        code = re.sub(r"\bdocument\.cookie\b", "({}).cookie", code)
        code = re.sub(r"\blocalStorage\b", "({})", code)
        code = re.sub(r"\bsessionStorage\b", "({})", code)

        # Strip static imports and neutralise dynamic imports/requires that
        # could load arbitrary third-party code in the preview sandbox.
        code = re.sub(r"^\s*import\s+[^;]+;?", "", code, flags=re.MULTILINE)
        code = re.sub(r"\bimport\s*\(", "(function(){{return Promise.resolve({{}});}})(", code)
        code = re.sub(r"\brequire\s*\(", "(function(){{return {{}};}})(", code)

        # Convert ESM exports to local declarations so Babel can execute the
        # component in the browser's global scope.
        code = re.sub(r"export\s+default\s+function\s*", "function ", code)
        code = re.sub(r"export\s+function\s*", "function ", code)
        code = re.sub(r"export\s+const\s*", "const ", code)
        code = re.sub(r"export\s+default\s+\w+\s*;?", "", code)

        # ponytail: Babel's typescript preset handles type annotations and
        # interface/type declarations, so we no longer strip them with regex.

        return code
