"""DEBUG: Check what tools the LLM actually receives."""
import json
import pytest
from typing import Any

_debug_calls = []

def _patch_litellm():
    try:
        import litellm
        original = litellm.acompletion

        async def patched(*args, **kwargs):
            tools = kwargs.get('tools', [])
            tool_names = [
                t.get('function', {}).get('name', '?') if isinstance(t, dict) else str(t)[:30]
                for t in tools
            ]
            msgs = kwargs.get('messages', [])
            # Extract system msg (first msg with role=system)
            sys_msg = next((m.get('content','')[:300] for m in msgs if isinstance(m,dict) and m.get('role')=='system'), None)
            # Last user msg
            last_user = next((m.get('content','')[:200] for m in reversed(msgs) if isinstance(m,dict) and m.get('role')=='user'), None)
            
            call_record = {
                "tool_count": len(tools),
                "tool_names": tool_names,
                "msg_count": len(msgs),
                "system_msg_preview": sys_msg,
                "last_user_msg": last_user,
            }
            _debug_calls.append(call_record)
            print(f"\n[LITELLM] acompletion tools={len(tools)}: {tool_names}")
            print(f"[LITELLM] system_msg[:300]: {repr(sys_msg)}")
            print(f"[LITELLM] last_user_msg: {repr(last_user)}")
            
            result = await original(*args, **kwargs)
            if hasattr(result, 'choices') and result.choices:
                m = result.choices[0].message
                tc = getattr(m, 'tool_calls', None)
                tc_names = [
                    getattr(getattr(t, 'function', None), 'name', '?')
                    for t in tc
                ] if tc else []
                content = str(m.content or '')
                print(f"[LITELLM] response tool_calls={tc_names}, content={repr(content[:400])}")
                call_record["response_tool_calls"] = tc_names
                call_record["response_content"] = content[:200]
            return result

        litellm.acompletion = patched
        print("[DEBUG] litellm.acompletion patched")
    except Exception as e:
        print(f"[DEBUG] litellm patch failed: {e}")


_patch_litellm()


@pytest.mark.integration
async def test_debug_tools_sent_to_llm(agent_factory):
    """DEBUG: Verify what tools the LLM receives during agent invocation."""
    from tests.integration.agents.conftest import _TaskSpawnCollector, parse_agent_timings_from_trace

    _QUERY = "Phân tích toàn diện $UNI cho long position"

    _debug_calls.clear()

    agent = await agent_factory()

    trace_events: list[dict[str, Any]] = []
    collector = _TaskSpawnCollector(trace_events)

    config = {
        "configurable": {
            "thread_id": "debug-test-thread",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "search_space_id": 1,
        },
        "callbacks": [collector],
    }

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": _QUERY}]},
        config=config,
    )

    print(f"\n\n===== DEBUG SUMMARY =====")
    print(f"Total litellm calls: {len(_debug_calls)}")
    for i, call in enumerate(_debug_calls):
        print(f"\n  Call {i+1}:")
        print(f"    tools ({call['tool_count']}): {call['tool_names']}")
        print(f"    response_tool_calls: {call.get('response_tool_calls', 'N/A')}")
        print(f"    response_content: {repr(call.get('response_content', ''))}")

    print(f"\nTrace events: {len(trace_events)}")
    timings = parse_agent_timings_from_trace(trace_events)
    print(f"Agent timings: {[t['agent_name'] for t in timings]}")

    assert True
