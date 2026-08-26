from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import time
from collections.abc import Sequence

import cssselect
from lxml import etree

try:
    import re2
except ImportError:
    re2 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class InvalidSelectorError(ValueError):
    """Raised when a CSS selector cannot be parsed."""


class ReDoSTimeoutError(ValueError):
    """Raised when a regex exceeds the 50ms ReDoS budget."""


class InvalidRegexError(ValueError):
    """Raised when a regex is syntactically invalid or unsupported."""


_HTML = etree.Element("html")


def validate_css_selectors(selectors: dict[str, str]) -> bool:
    """Parse each CSS selector and raise InvalidSelectorError on failure."""
    for name, value in selectors.items():
        try:
            parsed = cssselect.parse(value)
            # Translate to XPath to confirm the selector is meaningful.
            translator = cssselect.HTMLTranslator()
            for selector in parsed:
                translator.selector_to_xpath(selector)
        except (cssselect.SelectorSyntaxError, cssselect.ExpressionError) as exc:
            raise InvalidSelectorError(f"Invalid CSS selector '{name}': {exc}") from exc
    return True


def _build_test_inputs(pattern: str) -> list[str]:
    """Generate inputs of increasing length from the regex's alphabet."""
    # Extract a simple alphabet from the pattern: use the char class contents.
    # This is intentionally naive — the real defense is google-re2. We use it
    # only when re2 is not available.
    chars = set(re.sub(r"[^a-zA-Z0-9]", "", pattern))
    if not chars:
        chars = set("abc123")
    alpha = "".join(sorted(chars))[:4] or "a"
    return [
        "".join(alpha[i % len(alpha)] for i in range(size))
        for size in (256, 2560, 25600)
    ]


def _benchmark_with_re(pattern: str, test_inputs: Sequence[str]) -> float:
    """Benchmark ``re`` (fallback) on inputs with a hard 50ms timeout."""
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise InvalidRegexError(f"Invalid regex: {exc}") from exc

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        max_ms = 0.0
        for text in test_inputs:
            future = executor.submit(compiled.search, text)
            start = time.perf_counter()
            try:
                future.result(timeout=0.05)
            except concurrent.futures.TimeoutError as exc:
                raise ReDoSTimeoutError(
                    f"Regex exceeded 50ms ReDoS limit on input length {len(text)}"
                ) from exc
            elapsed_ms = (time.perf_counter() - start) * 1000
            max_ms = max(max_ms, elapsed_ms)
        return max_ms
    finally:
        executor.shutdown(wait=False)


# Heuristic: nested quantifiers on a group (or alternation inside a group)
# are the classic ReDoS shape. Even when using google-re2, we reject these
# patterns because the spec requires the sandbox to reject them (AC-3).
_DANGEROUS_PATTERN = re.compile(
    r"\([^()]*?([+*|])[^()]*?\)\s*[*+]",
    re.VERBOSE,
)


def _is_dangerous_pattern(pattern: str) -> bool:
    return bool(_DANGEROUS_PATTERN.search(pattern))


def _benchmark_with_re2(pattern: str, test_inputs: Sequence[str]) -> float:
    """Benchmark ``google-re2`` on inputs. re2 is linear time by design."""
    if _is_dangerous_pattern(pattern):
        raise ReDoSTimeoutError(
            f"REDOS_TIMEOUT: regex contains nested quantifiers/alternation disallowed by the sandbox: {pattern}"
        )
    if re2 is None:
        raise ImportError("google-re2 is not installed")
    try:
        compiled = re2.compile(pattern)
    except re2.error as exc:
        raise InvalidRegexError(f"Invalid regex: {exc}") from exc

    max_ms = 0.0
    for text in test_inputs:
        start = time.perf_counter()
        compiled.search(text)
        max_ms = max(max_ms, (time.perf_counter() - start) * 1000)
    return max_ms


def benchmark_redos(pattern: str, test_inputs: Sequence[str] | None = None) -> float:
    """Run a regex against inputs and return max ms, or raise ReDoSTimeoutError."""
    if test_inputs is None:
        test_inputs = _build_test_inputs(pattern)

    if re2 is not None:
        return _benchmark_with_re2(pattern, test_inputs)

    logger.warning("google-re2 not installed; falling back to re with 50ms timeout")
    return _benchmark_with_re(pattern, test_inputs)


def validate_regexes(patterns: dict[str, str]) -> bool:
    """Compile and benchmark each regex; raise on invalid/timeout."""
    for name, pattern in patterns.items():
        if not isinstance(pattern, str):
            raise InvalidRegexError(f"Regex '{name}' must be a string")
        benchmark_redos(pattern)
    return True


async def validate_regexes_async(patterns: dict[str, str]) -> None:
    """Async wrapper for ``validate_regexes``; offloads to a thread."""
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, validate_regexes, patterns),
            timeout=5.0,
        )
    except TimeoutError as exc:
        raise ReDoSTimeoutError("Regex validation timed out") from exc
