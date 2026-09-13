"""The ``task`` tool package — split from the original ``task_tool.py`` module.

Import surface is unchanged: ``from .task_tool import
build_task_tool_with_parent_config`` keeps working for callers, and the
private helpers remain importable from the package for lazy/dynamic access.

- ``_helpers``         — timeout + interrupt-stamping helpers used by both paths.
- ``_factory_helpers`` — closures promoted to module level (captured factory
  locals are now explicit parameters).
- ``_factory``         — :func:`build_task_tool_with_parent_config` itself.
"""

from ._factory import build_task_tool_with_parent_config
from ._helpers import (
    SubagentInvokeTimeoutError,
    _ainvoke_with_timeout as _ainvoke_with_timeout,
    _reraise_stamped_subagent_interrupt as _reraise_stamped_subagent_interrupt,
    _synthesize_timeout_command as _synthesize_timeout_command,
)

__all__ = ["SubagentInvokeTimeoutError", "build_task_tool_with_parent_config"]
