"""Temporary debug conftest: logs litellm.acompletion calls to /tmp/litellm_debug.json"""
import json
import pytest
import asyncio


@pytest.fixture(autouse=True)
def patch_litellm_debug(tmp_path_factory):
    """Intercept litellm.acompletion and log tools + messages to file."""
    try:
        import litellm
    except ImportError:
        yield
        return

    log_path = "/tmp/litellm_debug.json"
    calls = []
    original = litellm.acompletion

    async def patched_acompletion(*args, **kwargs):
        tools = kwargs.get('tools', [])
        tool_names = [
            t.get('function', {}).get('name', 'unknown') if isinstance(t, dict) else str(t)
            for t in tools
        ]
        messages = kwargs.get('messages', [])
        msg_summary = [
            {"role": m.get('role', ''), "content_len": len(str(m.get('content', '')))}
            for m in messages
        ]
        entry = {
            "tool_count": len(tools),
            "tool_names": tool_names,
            "message_count": len(messages),
            "messages": msg_summary,
        }
        
        result = await original(*args, **kwargs)
        
        # Log response
        if hasattr(result, 'choices') and result.choices:
            choice = result.choices[0]
            msg = choice.message
            tc = getattr(msg, 'tool_calls', None)
            entry["response_tool_calls"] = [
                {"name": getattr(getattr(t, 'function', None), 'name', str(t))}
                for t in tc
            ] if tc else []
            entry["response_content_len"] = len(str(getattr(msg, 'content', '') or ''))
        
        calls.append(entry)
        with open(log_path, 'w') as f:
            json.dump(calls, f, indent=2)
        
        return result

    litellm.acompletion = patched_acompletion
    yield
    litellm.acompletion = original
