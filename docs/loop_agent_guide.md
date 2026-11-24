# LoopAgent Guide: Iterative Workflows in Google ADK (Python)

`LoopAgent` is a workflow agent that runs its sub-agents **sequentially, over and
over**, until either the work is done or an iteration budget is exhausted. It is
the building block for "refine until good enough" pipelines: write → review →
revise → review → ...

This guide is for beginners. It walks through one complete, runnable example and
then explains the mechanics and best practices behind it. All behavior described
here is verified against the source in this repository
(`src/google/adk/agents/loop_agent.py` and friends).

## 1. What is LoopAgent?

A `LoopAgent` never calls the model itself. It is a *shell* agent that:

- Runs its `sub_agents` **one after another, in the listed order** (iteration
  pass 1), then repeats them in the same order (pass 2), and so on.
- Shares **one session** across all passes, so every sub-agent reads and writes
  the same `session.state`.
- Stops in exactly two situations:

| Exit condition | Trigger | When it takes effect |
| --- | --- | --- |
| **Escalation** | Any yielded event has `actions.escalate` set to `True` | Immediately, mid-iteration |
| **Iteration budget** | `max_iterations` full passes have completed | After the current full pass |

If `max_iterations` is not set (the default `None`), the loop runs **forever**
until some sub-agent escalates. This is why every production loop should set
both: a `max_iterations` safety net *and* a deterministic escalation exit.

## 2. When to use it

Good fits:

- **Iterative refinement**: draft writing, code fixing, data cleaning — any
  task where a *producer* agent and a *checker* agent alternate until the
  checker approves.
- **Retry-with-feedback**: a checker fails the result, writes concrete feedback
  into session state, and the producer revises based on that feedback.

Not a good fit:

- A fixed, single-pass pipeline — use `SequentialAgent` (it runs sub-agents
  once, in order, with no exit logic).
- Independent branches that should run **in parallel** — use `ParallelAgent`.
- Live (voice/video streaming) sessions — `LoopAgent` raises
  `NotImplementedError` for live runs
  (`src/google/adk/agents/loop_agent.py:57-61`).

## 3. Prerequisites

```bash
pip install google-adk
export GOOGLE_API_KEY="your-key-here"   # used by the Gemini model below
```

## 4. A complete runnable example

One file, no project scaffold needed: a `writer` agent produces or revises a
draft, a `reviewer` agent evaluates the draft through a small Python tool, and
the tool **escapes the loop** once the draft passes the quality bar.

### 4.1 The full code (`loop_agent_demo.py`)

```python
"""Iteratively polish a short story with an ADK LoopAgent.

Run:
    python loop_agent_demo.py

Requires:
    pip install google-adk
    export GOOGLE_API_KEY="..."
"""

import asyncio

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types

MIN_WORDS = 50


def check_quality(tool_context: ToolContext) -> dict:
    """Evaluates the current draft and exits the loop once it passes.

    The reviewer agent must call this tool after reading the draft.
    """
    draft = str(tool_context.state.get("current_text", "")).strip()
    word_count = len(draft.split()) if draft else 0

    if word_count >= MIN_WORDS:
        # Tell the LoopAgent to stop iterating. This is the ONLY supported
        # way for a plain tool to end the loop, and it takes effect
        # immediately: the loop exits as soon as this response event is seen.
        tool_context.actions.escalate = True
        return {"status": "approved", "word_count": word_count}

    feedback = (
        f"The draft has {word_count} words. "
        f"Expand it to at least {MIN_WORDS} words."
    )
    # Persist the feedback in session state so the next writer pass can
    # read it via the {last_feedback?} template below.
    tool_context.state["last_feedback"] = feedback
    return {
        "status": "needs_revision",
        "word_count": word_count,
        "feedback": feedback,
    }


writer = LlmAgent(
    name="writer",
    model="gemini-2.0-flash",
    description="Writes and revises the story draft.",
    instruction=(
        "You are a short-story writer.\n"
        "Current draft:\n{current_text?}\n"
        "Reviewer feedback:\n{last_feedback?}\n"
        "If there is no draft yet, write a new short story about a lighthouse"
        " keeper. Otherwise, revise the draft so it addresses the reviewer"
        " feedback. Output only the story text, no commentary."
    ),
    # Store this agent's final reply in session state under `current_text`,
    # so the reviewer and the next writer pass can read it.
    output_key="current_text",
)

reviewer = LlmAgent(
    name="reviewer",
    model="gemini-2.0-flash",
    description="Reviews the current draft by calling check_quality.",
    instruction=(
        "You are a strict reviewer.\n"
        "Current draft:\n{current_text}\n"
        "Call the `check_quality` tool exactly once to evaluate the draft,"
        " then report the tool's verdict in one concise sentence."
    ),
    tools=[check_quality],
)

polish_loop = LoopAgent(
    name="polish_loop",
    description="Iterates writer and reviewer until the draft passes.",
    sub_agents=[writer, reviewer],
    # Safety net: never loop forever. Without this, the loop runs until
    # some sub-agent escalates (see section 5).
    max_iterations=5,
)


async def main() -> None:
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="polish_loop_demo", user_id="demo_user"
    )
    runner = Runner(
        app_name="polish_loop_demo",
        agent=polish_loop,
        session_service=session_service,
    )

    new_message = types.Content(
        role="user",
        parts=[
            types.Part(text="Polish a very short story about a lighthouse keeper.")
        ],
    )

    async for event in runner.run_async(
        user_id="demo_user",
        session_id=session.id,
        new_message=new_message,
    ):
        text = "".join(part.text or "" for part in event.content.parts or [])
        if text.strip():
            print(f"[{event.author}] {text.strip()}")

    final_session = await session_service.get_session(
        app_name="polish_loop_demo",
        user_id="demo_user",
        session_id=session.id,
    )
    print("\n=== Final draft (session.state['current_text']) ===")
    print(final_session.state.get("current_text", "<empty>"))


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 Run it

```bash
python loop_agent_demo.py
```

### 4.3 What you'll see

Output varies with the model, but the shape is always the same (this sample
shows a run that needed one revision; if the first draft already passes, the
loop exits after a single review):

```text
[writer] The old keeper climbed the spiral stairs each evening, ...
[reviewer] The draft needs revision: it has only 12 words and the target is 50.
[writer] Every evening the keeper climbed the spiral stairs of the white ...
=== Final draft (session.state['current_text']) ===
Every evening the keeper climbed the spiral stairs of the white ...
```

Notice where the deliverable ends up: in `session.state["current_text"]`, not
in the last printed event. When `check_quality` escalates, the loop stops
immediately — the reviewer never gets to summarize the approving round — so
the durable result is the state value written by the writer's `output_key`.

## 5. How the loop works

The whole engine is ~10 lines. Simplified from
`src/google/adk/agents/loop_agent.py:47-54`:

```python
times_looped = 0
while max_iterations is None or times_looped < max_iterations:
    for sub_agent in self.sub_agents:        # fixed order, every pass
        async for event in sub_agent.run_async(ctx):
            yield event
            if event.actions.escalate:       # checked on EVERY event
                return                       # exit immediately
    times_looped += 1
```

Key consequences:

- **Escalation is checked after every single event**, including tool response
  events. When a tool sets `tool_context.actions.escalate = True`, ADK attaches
  that flag to the tool's function-response event
  (`src/google/adk/flows/llm_flows/functions.py:477`), and the loop stops
  right there — even mid-way through a sub-agent.
- **`max_iterations=5` means 5 full passes**, not 5 event yields. The counter
  increments after all sub-agents complete a pass.
- **All sub-agents share the same invocation context and session.** That is why
  the `output_key="current_text"` write from the writer is visible to the
  reviewer in the same pass, and to the writer again on the next pass.
- With `max_iterations=None`, the loop never ends on its own. There is no
  error and no warning when the budget is omitted.

**How state flows through the example:**

1. Writer replies; ADK stores the reply in `state["current_text"]`
   (`output_key`, `src/google/adk/agents/llm_agent.py:179-185`).
2. Reviewer reads the draft via the `{current_text}` instruction injection
   (`src/google/adk/utils/instructions_utils.py:96-104`) and calls
   `check_quality`.
3. If the draft is too short, the tool writes `state["last_feedback"]` and
   returns a `needs_revision` verdict; the loop continues to the next pass.
4. On the next pass the writer's instruction injects both
   `{current_text?}` and `{last_feedback?}` and revises the draft.
5. Once the draft reaches the bar, the tool sets `escalate = True` and the
   loop exits.

## 6. Best practices

1. **Always set `max_iterations`.** The default (`None`) means "loop until
   escalate, forever". If your checker has a bug or the model keeps failing,
   you get an unbounded run and an unbounded bill.
2. **Give the loop a deterministic exit, not just instructions.** In this
   version of ADK, plain tools are the supported way to escalate: receive
   `tool_context: ToolContext` and set `tool_context.actions.escalate = True`.
   For an unconditional "we're done" exit you can also use the built-in
   `exit_loop` tool (`from google.adk.tools import exit_loop`,
   `src/google/adk/tools/exit_loop_tool.py`).
   > Version note: agent-level callbacks (`before_agent_callback` /
   > `after_agent_callback`) exist on every agent, but in this version
   > `CallbackContext` exposes no public `actions` attribute, so callbacks
   > **cannot** set `escalate`. Put the exit decision in a tool.
3. **Move data between passes through session state, not conversation history.**
   Use `output_key` on producer agents, `{key}` / `{key?}` injection in
   instructions, and `tool_context.state[...] = ...` inside tools. The `?`
   suffix makes a placeholder render as an empty string when the key does not
   exist yet (first pass!); without it, a missing key raises `KeyError`
   (`src/google/adk/utils/instructions_utils.py:78-104`).
4. **Order sub-agents produce → check.** Sub-agents run sequentially in list
   order on every pass. If the checker runs before the producer, it reviews a
   stale draft from the previous pass.
5. **Make the checker deterministic where possible.** `check_quality` measures
   word count with plain Python — no model judgment — and only the *writing*
   is delegated to the model. The more of your exit condition is real code,
   the more reliable (and cheaper) your loop is.
6. **Follow the naming rules.** Agent names must be valid Python identifiers,
   and cannot be `"user"` — both enforced by a validator
   (`src/google/adk/agents/base_agent.py:361-376`). Uniqueness within the
   agent tree is a documented requirement
   (`src/google/adk/agents/base_agent.py:72`), but no validator enforces it in
   this version; keep names unique anyway — event attribution and logs get
   ambiguous with duplicates. A single agent instance can be added to only one
   parent, and this one *is* enforced
   (`src/google/adk/agents/base_agent.py:378-387`). To reuse a configuration,
   create two instances with different names
   (`src/google/adk/agents/base_agent.py:83-91`).
7. **Remember the escalation asymmetry.** An approval verdict must escalate;
   a rejection verdict must *not*. Only the passing branch of your checker
   should touch `actions.escalate`.
8. **No live/streaming support.** `LoopAgent._run_live_impl` raises
   `NotImplementedError` — only use it behind `run_async()` / `run()`.
9. **Budget exhaustion is silent.** If `max_iterations` passes complete
   without escalation, the loop just ends. Decide in your application what to
   do with the last state (accept, alert, or surface the failure).
10. **Watch the loop while learning.** Print `event.author` and the event text
    (as the example does) and inspect `session.state` afterwards; the last
    event is not necessarily the final artifact.

## 7. Parameter quick reference

`LoopAgent` (`src/google/adk/agents/loop_agent.py:29-41`):

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | `str` | required | Valid Python identifier, unique in the tree, not `"user"` |
| `description` | `str` | `""` | One-line description of the loop's job |
| `sub_agents` | `list[BaseAgent]` | `[]` | Run sequentially, in order, every pass |
| `max_iterations` | `int \| None` | `None` | Max full passes; `None` = loop until escalate |
| `before_agent_callback` / `after_agent_callback` | callback(s) | `None` | Hook before/after each loop run; the parameter **must** be named `callback_context` (`src/google/adk/agents/base_agent.py:95-122`) |

`LlmAgent` fields used in the example
(`src/google/adk/agents/llm_agent.py:117-186`):

| Field | Meaning |
| --- | --- |
| `model` | Model string (e.g. `"gemini-2.0-flash"`) or a `BaseLlm`; unset inherits the parent's model |
| `instruction` | Prompt for the model; supports `{state_key}` (required) and `{state_key?}` (optional) injection |
| `description` | Helps the model decide about delegation |
| `tools` | Python functions or `BaseTool` instances the model may call |
| `output_key` | Session-state key that receives this agent's final reply |
| `include_contents` | `"default"` keeps conversation history; `"none"` strips it (advanced: use with `{key?}` state injection to keep loop context small) |

`ToolContext` essentials used in the example
(`src/google/adk/tools/tool_context.py:54-70`):

| API | Meaning |
| --- | --- |
| `tool_context.state` | Read/write session state (writes are committed with the tool response event) |
| `tool_context.actions.escalate = True` | Escalates; a running `LoopAgent` stops immediately after this event |
