# ADK LoopAgent Usage Guide — Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Pipeline override:** this pipeline forbids all Git write operations. The usual "Commit" steps are replaced by read-only `git diff` verification steps. Never run `git add` / `git commit` / `git checkout`.

**Goal:** Finalize the beginner ADK `LoopAgent` usage guide (`docs/loop_agent_guide.md`) so that every factual claim is traceable to this repository's source and the embedded runnable example is syntax- and construction-verified.

**Architecture:** The deliverable is a single Markdown doc. The clarify stage already produced a complete 7-section draft (commit `e83a8a9`) with a runnable example and 10 best practices. This plan corrects the two source-citation defects found by a fact audit against `src/google/adk/**`, statically verifies the embedded example (extract → `py_compile` → optional import/construction smoke), then runs a closeout self-review. No live model run: the pipeline environment has no `google.adk` installed and no `GOOGLE_API_KEY`.

**Tech Stack:** Markdown; Python 3.12 (stdlib only for primary checks); repo source `src/google/adk/**` as the single source of truth. Project floor: `requires-python = ">=3.9"` (`pyproject.toml:8`).

## Global Constraints

- Deliverable path is exactly `docs/loop_agent_guide.md`. Do not rename, do not split.
- Doc stays in English (repo convention; the clarify-approved artifact is English).
- The only repo file this plan may modify is `docs/loop_agent_guide.md`. No changes to `src/`, `tests/`, or any config file.
- Scratch artifacts go to `/tmp` only, never inside the repo; delete them in Task 2.
- Git is read-only: verification uses `git status --porcelain` / `git diff` only.
- Every behavioral claim in the doc must cite `src/google/adk/...:line-range`; citations must match the audited ranges in the Fact baseline below.
- Verification budget ≤ 5 minutes total. If the optional editable install (Task 2, Step 3) fails or exceeds 300 s, stop it, prefix the report with `[降级说明]`, and finish with static review only. Do not retry with different flags.
- Do not use `grep`/`glob` shell commands; content checks use `rg` or `python3`.

## Fact baseline (audited this session against HEAD)

All rows verified — the executor must not re-derive them. Only the two "Corrections needed" are outstanding.

| # | Doc claim | Source (this repo) | Status |
|---|---|---|---|
| 1 | Loop engine: sequential sub-agent passes, `escalate` checked on every event, counter incremented after a full pass | `src/google/adk/agents/loop_agent.py:44-55` (core loop 47-54) | verified |
| 2 | Live/streaming runs raise `NotImplementedError` | `src/google/adk/agents/loop_agent.py:57-61` | verified |
| 3 | `{key}` required / `{key?}` optional injection; missing required key raises `KeyError`; optional renders `''` | `src/google/adk/utils/instructions_utils.py:76-106` | verified |
| 4 | `output_key` stores the agent's final reply in session state | `src/google/adk/agents/llm_agent.py:179-185` | verified |
| 5 | `tool_context.actions` is attached to the function-response event (so the loop sees `escalate`) | `src/google/adk/flows/llm_flows/functions.py:473-481` (line 477) | verified |
| 6 | `ToolContext.actions` property | `src/google/adk/tools/tool_context.py:58-60` | verified |
| 7 | Built-in `exit_loop` tool sets `actions.escalate = True` | `src/google/adk/tools/exit_loop_tool.py:18-23`; exported at `src/google/adk/tools/__init__.py:20,41` | verified |
| 8 | Name validator enforces: valid Python identifier, not `"user"` | `src/google/adk/agents/base_agent.py:361-376` | verified |
| 9 | "unique within the agent tree" is documented in the docstring but NOT enforced by any validator | `src/google/adk/agents/base_agent.py:72` | verified |
| 10 | Single-parent rule enforced (`parent_agent` already set → `ValueError`) | `src/google/adk/agents/base_agent.py:378-387` | verified |
| 11 | Callback arg must be named `callback_context` | `src/google/adk/agents/base_agent.py:95-122` | verified |
| 12 | `Runner.run_async(*, user_id, session_id, new_message)` is async | `src/google/adk/runners.py:155-162` | verified |
| 13 | `InMemorySessionService.create_session(*, app_name, user_id, ...)` is async (`await` required) | `src/google/adk/sessions/in_memory_session_service.py:48-61` | verified |
| 14 | Demo imports resolve (`LlmAgent`, `LoopAgent`, `ToolContext`, `exit_loop`) | `src/google/adk/agents/__init__.py:19-20`; `src/google/adk/tools/__init__.py:20,28` | verified |

Corrections needed (the only known defects — Task 1):

1. §5 cites `loop_agent.py:43-55` for the engine; the loop core is `47-54` (the impl method spans 44-55).
2. §6 item 6 cites `base_agent.py:361-375` and implies uniqueness is enforced alongside the identifier/`"user"` checks; actually the validator covers identifier + `"user"` only (361-376), uniqueness is docstring-only (`base_agent.py:72`), and the *enforced* reuse constraint is the single-parent check (`base_agent.py:378-387`).

## File Structure

- Modify: `docs/loop_agent_guide.md` — two hunks: §5 (line ~225) and §6 item 6 (lines ~295-300). No other hunks.
- Create: `docs/superpowers/plans/2026-11-24-adk-loop-agent-usage-doc.md` — this plan (written by the plan stage).
- Scratch (outside the repo, deleted in Task 2): `/tmp/loop_agent_demo_check.py`.

---

### Task 1: Correct the two defective source citations

**Files:**
- Modify: `docs/loop_agent_guide.md:225` (one line) and `docs/loop_agent_guide.md:295-300` (one block)

**Interfaces:**
- Consumes: Fact baseline corrections 1 and 2.
- Produces: a doc in which `loop_agent.py:43-55` and `base_agent.py:361-375` no longer appear; §6 item 6 states uniqueness is docstring-only and cites `base_agent.py:72` and `base_agent.py:378-387`. Later tasks depend on the §4.1 code block being untouched.

- [ ] **Step 1: Run the citation audit and confirm the two defects (failing check)**

```
rg -n 'loop_agent\.py:43-55|base_agent\.py:361-375' docs/loop_agent_guide.md
```

Expected: exactly 2 matches — line ~225 (`loop_agent.py:43-55`) and line ~297 (`base_agent.py:361-375`). If a match is missing, stop and re-read the file; do not blind-edit.

- [ ] **Step 2: Apply correction 1 (§5 engine citation)**

Replace exactly:

```
The whole engine is ~10 lines. Simplified from
`src/google/adk/agents/loop_agent.py:43-55`:
```

with:

```
The whole engine is ~10 lines. Simplified from
`src/google/adk/agents/loop_agent.py:47-54`:
```

- [ ] **Step 3: Apply correction 2 (§6 naming rules)**

Replace exactly:

```
6. **Follow the naming rules.** Agent names must be valid Python identifiers,
   must be unique within the agent tree, and cannot be `"user"`
   (`src/google/adk/agents/base_agent.py:361-375`). A single agent instance
   can be added to only one parent; to reuse a configuration, create two
   instances with different names
   (`src/google/adk/agents/base_agent.py:83-91`).
```

with:

```
6. **Follow the naming rules.** Agent names must be valid Python identifiers
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
```

- [ ] **Step 4: Re-run the audit (check passes)**

```
rg -n 'loop_agent\.py:43-55|base_agent\.py:361-375' docs/loop_agent_guide.md
```
Expected: no matches (empty output).

```
rg -n 'loop_agent\.py:47-54|base_agent\.py:361-376|base_agent\.py:378-387' docs/loop_agent_guide.md
```
Expected: ≥ 3 matches (§5 engine line, plus two §6 item 6 refs; `base_agent.py:72` appears once inside item 6 as well).

```
git diff --stat
```
Expected: only `docs/loop_agent_guide.md` changed (roughly 12 added / 6 removed lines); nothing else.

---

### Task 2: Verify the embedded example (syntax + construction smoke)

**Files:**
- Read: `docs/loop_agent_guide.md` §4.1 python block (must be identical before/after this task)
- Scratch: `/tmp/loop_agent_demo_check.py` (created, then deleted)

**Interfaces:**
- Consumes: the §4.1 fenced python block; Fact baseline rows 12-14.
- Produces: verification evidence (compile OK; smoke OK, or `[降级说明]`); no repo file changes.

- [ ] **Step 1: Extract the §4.1 code block to /tmp**

```
python3 - <<'EOF'
import pathlib, re
text = pathlib.Path("docs/loop_agent_guide.md").read_text()
section = text.split("### 4.1 The full code (`loop_agent_demo.py`)")[1]
fence = "`" * 3
code = re.search(fence + r"python\n(.*?)" + fence, section, re.S).group(1)
pathlib.Path("/tmp/loop_agent_demo_check.py").write_text(code)
print("extracted", len(code), "chars")
EOF
```

Expected: `extracted <N> chars` with N ≈ 4000 (positive; the block is the full demo ending in `asyncio.run(main())`).

- [ ] **Step 2: Syntax check**

```
python3 -m py_compile /tmp/loop_agent_demo_check.py && echo COMPILE_OK
```
Expected: `COMPILE_OK`, exit 0.

- [ ] **Step 3 (optional, bounded): make `google.adk` importable**

Run only if the environment allows installs:

```
timeout 300 python3 -m pip install -e . --quiet
```

- Exit 0 → continue with Steps 4-5.
- Failure or timeout → print `[降级说明] editable install unavailable; Task 2 verified syntax only (Steps 1-2); API-usage correctness was verified by source audit (Fact baseline rows 12-14)` and jump to Step 6. Do not retry with different flags.

- [ ] **Step 4: Construction smoke — execute the demo module's import path**

Executing the extracted module constructs `writer`, `reviewer`, and `polish_loop` (all constructor kwargs validated) without calling `main()` (guarded by `__name__`); no model call, no API key needed:

```
python3 - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("demo", "/tmp/loop_agent_demo_check.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert [a.name for a in m.polish_loop.sub_agents] == ["writer", "reviewer"]
assert m.polish_loop.max_iterations == 5
assert m.writer.output_key == "current_text"
assert callable(m.check_quality)
print("CONSTRUCTION_SMOKE_OK")
EOF
```

Expected: `CONSTRUCTION_SMOKE_OK`, exit 0.

- [ ] **Step 5: Naming-rule behavior check (supports the corrected §6 item 6)**

```
python3 - <<'EOF'
from google.adk.agents import LoopAgent
loop = LoopAgent(name="ok", sub_agents=[])
assert loop.max_iterations is None  # documented default: loop until escalate
for bad in ("bad name", "user"):
    try:
        LoopAgent(name=bad, sub_agents=[])
        raise SystemExit(f"FAIL: name={bad!r} was accepted")
    except ValueError:
        pass
print("NAMING_RULES_OK")
EOF
```

Expected: `NAMING_RULES_OK`, exit 0.

- [ ] **Step 6: Clean up scratch and confirm no repo residue**

```
rm -f /tmp/loop_agent_demo_check.py /tmp/__pycache__/loop_agent_demo_check*.pyc
git status --porcelain
```

Expected: the only repo-side change remains ` M docs/loop_agent_guide.md` from Task 1 (plus any pipeline-committed plan files); no untracked scratch files inside the repo.

---

### Task 3: Self-review and closeout

**Files:**
- Read: `docs/loop_agent_guide.md` (final state)

**Interfaces:**
- Consumes: Tasks 1-2 results.
- Produces: the acceptance evidence list for the pipeline summary.

- [ ] **Step 1: Spec coverage — required sections exist**

```
rg -n '^## [0-9]+\.' docs/loop_agent_guide.md
```
Expected: exactly 7 matches — `## 1. What is LoopAgent?` through `## 7. Parameter quick reference`.

```
rg -n '^[0-9]+\. \*\*' docs/loop_agent_guide.md
```
Expected: exactly 10 matches (the §6 best-practices list — the requirement's "code best practices").

- [ ] **Step 2: Placeholder scan**

```
rg -n 'TBD|TODO|implement later|fill in|待定|占位' docs/loop_agent_guide.md
```
Expected: no matches.

- [ ] **Step 3: Code-fence balance**

```
python3 - <<'EOF'
import pathlib
t = pathlib.Path("docs/loop_agent_guide.md").read_text()
n = t.count("`" * 3)
print("fences:", n, "balanced:", n % 2 == 0)
assert n % 2 == 0
EOF
```
Expected: `fences: 10 balanced: True` (5 blocks: §3 bash, §4.1 python, §4.2 bash, §4.3 text, §5 python).

- [ ] **Step 4: Read-only change audit**

```
git status --porcelain && git diff --stat
```
Expected: exactly one content change — `docs/loop_agent_guide.md`; no untracked scratch files inside the repo. Git stays read-only.

- [ ] **Step 5: Report**

Summarize: corrections applied (2), verification evidence (compile / smoke results, or the `[降级说明]`), and the deliverable path `docs/loop_agent_guide.md`.

---

## Out of scope

- No changes to `src/`, `tests/`, `pyproject.toml`, or CI.
- No live LLM run of the demo (no `GOOGLE_API_KEY`; behavior claims are source-audited instead).
- No translation of the guide; no new standalone example scripts in the repo (the example lives in §4.1 by design).
