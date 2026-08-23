"""Validation utilities for generated Web Builder projects (Story 27.1, AC-1)."""

import json
from pathlib import Path


def validate_project_structure(project_dir: str | Path) -> tuple[bool, list[str]]:
    """Validate that the generated project has the minimum required files for a runnable Next.js app.

    Returns:
        tuple[bool, list[str]]: (is_valid, list of validation issues or missing requirements)
    """
    root = Path(project_dir)
    issues: list[str] = []

    if not root.exists() or not root.is_dir():
        return False, [f"Project directory does not exist: {project_dir}"]

    # 1. Check package.json
    pkg_file = root / "package.json"
    if not pkg_file.exists():
        issues.append("Missing package.json")
    else:
        try:
            pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
            deps = {
                **pkg_data.get("dependencies", {}),
                **pkg_data.get("devDependencies", {}),
            }
            if "next" not in deps:
                issues.append("package.json missing 'next' dependency")
            if "react" not in deps:
                issues.append("package.json missing 'react' dependency")
        except Exception as e:
            issues.append(f"Invalid package.json format: {e}")

    # 2. Check entrypoint page (app/page.tsx or app/page.jsx or pages/index.tsx)
    has_page = (
        (root / "app" / "page.tsx").exists()
        or (root / "app" / "page.jsx").exists()
        or (root / "app" / "page.js").exists()
        or (root / "pages" / "index.tsx").exists()
        or (root / "pages" / "index.jsx").exists()
    )
    if not has_page:
        issues.append("Missing entrypoint page (expected app/page.tsx)")

    # 3. Check layout (app/layout.tsx or app/layout.jsx) if using App Router
    if (root / "app").exists():
        has_layout = (
            (root / "app" / "layout.tsx").exists()
            or (root / "app" / "layout.jsx").exists()
            or (root / "app" / "layout.js").exists()
        )
        if not has_layout:
            issues.append("Missing root layout (expected app/layout.tsx)")

    return len(issues) == 0, issues
