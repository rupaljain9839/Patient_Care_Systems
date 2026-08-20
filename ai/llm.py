"""Groq LLM access via LangChain, per the model configured in .env (GROQ_MODEL)."""
import traceback
from functools import lru_cache

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from core.config import settings


@lru_cache(maxsize=1)
def get_llm():
    """Cached — building a fresh ChatGroq client on every single call (as this used
    to do) is pure overhead. The API key/model don't change during a run, so one
    client is reused for the life of the process.

    max_tokens=900 is set deliberately: with no cap, a call can run all the way to
    the model's full output limit even for a short factual answer, which is pure
    added latency for no benefit here — chat answers in this app are never meant
    to be that long."""
    if not settings.llm_configured:
        raise RuntimeError(
            "GROQ_API_KEY is not set in .env — SmartCare AI needs it to work. "
            "Get a free key at https://console.groq.com and add it to .env."
        )
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        max_tokens=900,
    )


def _to_langchain_messages(system_prompt: str, history: list, user_message: str):
    messages = [SystemMessage(content=system_prompt)]
    for turn in history:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))
    messages.append(HumanMessage(content=user_message))
    return messages


def chat_completion(system_prompt: str, history: list, user_message: str) -> str:
    """history: list of {"role": "user"|"assistant", "content": str}, oldest first."""
    llm = get_llm()
    messages = _to_langchain_messages(system_prompt, history, user_message)
    response = llm.invoke(messages)
    return response.content


def run_agent(system_prompt: str, history: list, user_message: str, tools: list, max_iterations: int = 3) -> str:
    """Runs a tool-calling loop: the model can call any of `tools`, see the result, and
    either call more tools or produce a final text answer. max_iterations is a hard
    ceiling on latency, not just a safety net — most real flows here need at most 2-3
    tool calls (e.g. resolve doctor -> check slots -> quote), so this bounds
    worst-case round trips to Groq rather than letting a confused model burn through
    a long chain before giving up."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)
    messages = _to_langchain_messages(system_prompt, history, user_message)
    tool_map = {t.name: t for t in tools}

    for _ in range(max_iterations):
        response = _invoke_with_tool_retry(llm_with_tools, llm, messages)
        if not getattr(response, "tool_calls", None):
            return response.content

        messages.append(response)
        for call in response.tool_calls:
            tool_obj = tool_map.get(call["name"])
            if tool_obj is None:
                result = f"Unknown tool: {call['name']}"
            else:
                try:
                    result = tool_obj.invoke(call["args"])
                except Exception as e:
                    result = f"Error running {call['name']}: {e}"
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    # Ran out of iterations — most commonly because the model kept retrying a
    # booking tool that the confirmation guard correctly blocked. Rather than a
    # dead-end apology, force ONE more plain-text-only completion (no tools bound)
    # using everything gathered so far, so the patient still gets a real, useful
    # answer instead of "I wasn't able to finish that."
    try:
        wrap_up = messages + [HumanMessage(
            content="Stop calling tools now. Based on everything above, give the "
                    "patient a clear, complete answer in plain text."
        )]
        return llm.invoke(wrap_up).content
    except Exception:
        print("[SmartCare AI] max_iterations wrap-up completion failed:")
        traceback.print_exc()
        return "I wasn't able to finish that after several steps — could you rephrase your request with a bit more detail?"


def _invoke_with_tool_retry(llm_with_tools, llm_plain, messages):
    """Groq's Llama models occasionally emit a malformed inline tool call (literal
    text like '<function=list_doctors{...}</function>' instead of a proper
    structured tool_calls entry), which Groq's API rejects outright with an HTTP
    400 'tool_use_failed' error — a model output quirk, not something our tool
    definitions can prevent. It's usually non-deterministic, so one retry often
    just works. If it fails twice in a row, fall back to a plain (no-tools)
    completion so the patient still gets a real answer instead of a raw API
    error dumped into the chat.

    Every failure is logged to the console (traceback + attempt label) even
    though the patient never sees it — the UI only ever shows a clean fallback
    message, but silently swallowing the real error everywhere would leave
    nothing to debug from when something's wrong. Check the terminal running
    `streamlit run app.py` for the actual cause."""
    try:
        return llm_with_tools.invoke(messages)
    except Exception:
        print("[SmartCare AI] Tool-call attempt 1 failed:")
        traceback.print_exc()

    try:
        return llm_with_tools.invoke(messages)
    except Exception:
        print("[SmartCare AI] Tool-call attempt 2 failed:")
        traceback.print_exc()

    # Both tool-calling attempts failed — degrade to a plain completion rather
    # than propagating the raw Groq error up into the visible chat message.
    try:
        return llm_plain.invoke(messages + [HumanMessage(
            content="(A tool call just failed on the backend. Without using any tools, "
                    "answer as best you can in plain text, or ask the patient a "
                    "clarifying question if you need more detail to help them.)"
        )])
    except Exception:
        print("[SmartCare AI] Plain-completion fallback ALSO failed "
              "(likely GROQ_API_KEY, network, or rate-limit issue, not the tool-call quirk):")
        traceback.print_exc()
        raise