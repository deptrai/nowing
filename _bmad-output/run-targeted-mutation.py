#!/usr/bin/env python3
"""Targeted mutation run for a single module with a specific test file."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "nowing_backend"
SCRIPT_FILE = REPO / "scripts" / "mutation-gate.py"
OUT_DIR = REPO / "_bmad-output" / "test-artifacts"

spec = importlib.util.spec_from_file_location("mutation_gate", SCRIPT_FILE)
assert spec and spec.loader, "mutation-gate.py not found"
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)


def resolve_module(service: str) -> Path:
    module = BACKEND / "app" / service.replace("/", "/")
    if module.suffix != ".py":
        module = module.with_suffix(".py")
    if not module.exists():
        raise FileNotFoundError(f"module not found: {module}")
    return module


def run_service(service: str, test_file: str) -> int:
    safe = service.replace("/", "-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config = BACKEND / f"mutation-nowing-{safe}-{stamp}.toml"
    session = OUT_DIR / f"mutation-nowing-{safe}-{stamp}.sqlite"
    module = resolve_module(service)

    original_src = module.read_bytes()
    try:
        test_cmd = (
            'bash -c "COSMIC_RAY=1 .venv/bin/python -m pytest '
            f'{test_file} '
            '-m unit -x 2>&1"'
        )
        toml = f"""[cosmic-ray]
module-path = "{module.relative_to(BACKEND)}"
timeout = 60.0
excluded-modules = ["tests", "migrations", "proprietary"]
test-command = '{test_cmd}'

[cosmic-ray.distributor]
name = "local"
"""
        config.write_text(toml)
        print(f"[mutation] service: {service}")
        print(f"[mutation] config: {config}")
        print(f"[mutation] session: {session}")

        for step, cmd in [
            ("baseline", ["uv", "run", "--no-sync", "cosmic-ray", "baseline", str(config)]),
            ("init", ["uv", "run", "--no-sync", "cosmic-ray", "init", str(config), str(session)]),
            (
                "filter-pragma",
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-m",
                    "cosmic_ray.tools.filters.pragma_no_mutate",
                    str(session),
                ],
            ),
            ("exec", ["uv", "run", "--no-sync", "cosmic-ray", "exec", str(config), str(session)]),
        ]:
            print(f"[mutation] cosmic-ray {step} {config.name}")
            result = mg.run(cmd, cwd=BACKEND, timeout=7200)
            if result.returncode != 0:
                print(result.stdout, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                raise RuntimeError(f"cosmic-ray {step} failed for {config.name}")

        records = mg.dump_session(BACKEND, session)
        result = mg.evaluate_service(service, records)

        report = OUT_DIR / f"mutation-nowing-{safe}-{stamp}.json"
        report.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        result["reportPath"] = str(report)
        result["sessionPath"] = str(session)
        result["configPath"] = str(config)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        summary_path = OUT_DIR / "mutation-nowing-summary-latest.json"
        summary = {
            "dimension": "mutation",
            "runAt": datetime.now(timezone.utc).isoformat(),
            "services": [result],
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

        config.unlink(missing_ok=True)
        return 0 if result.get("verdict") == "PASS" else 1
    except Exception as exc:
        import traceback

        print(traceback.format_exc(), file=sys.stderr)
        return 2
    finally:
        module.write_bytes(original_src)
        for ext in (".bak", ".crswap"):
            swap = module.with_suffix(module.suffix + ext)
            if swap.exists():
                swap.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run targeted mutation gate")
    parser.add_argument("--service", required=True, help="Service path under app/")
    parser.add_argument("--test-file", required=True, help="Test file path relative to nowing_backend")
    args = parser.parse_args()
    return run_service(args.service, args.test_file)


if __name__ == "__main__":
    sys.exit(main())
