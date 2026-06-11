# organ-app-prompts-autonomous-session-v2

A **pure organ** that selects and renders persona prompts for autonomous work
sessions in DataFlow Advisory.

**Re-extracted** from `discovery-engine/app/prompts/autonomous_session.py` as a
clean fork of `organ-app-prompts-autonomous-session` (which went RED on CI for
packaging reasons — its workflow never installed `pytest` and its sample `.py`
scripts couldn't import `organ` from the `samples/` cwd). This v2 keeps the
prompt logic verbatim and fixes the harness: JSON samples + a contract checker +
a CI workflow that installs its deps.

## What it does

Given a session type and persona context, the organ returns the appropriate
system prompt(s) and supplementary prompts:

- **`autonomous`** — general persona work session. Renders a system prompt that
  frames the persona's role, expertise, accumulated knowledge, board directive,
  platform identity, and available tools.
- **`spec`** — technical-specification writing session. Renders a spec-research
  system prompt **plus** an `extraction` prompt that steers the persona toward
  JSON-structured task output.
- **`team_synthesis`** — sub-team spec synthesis. Renders a parent-persona
  (e.g. Matt) system prompt **plus** a `synthesis` prompt; when
  `partial_specs_text` is supplied it is filled into the `{partial_specs_text}`
  placeholder.

## Interface (orchestrator CONTRACT.md)

```python
def decide(state: dict, context: dict | None = None) -> dict:
    """
    state keys (all optional — safe defaults apply):
        - session_type: "autonomous" | "spec" | "team_synthesis"  (default "autonomous")
        - persona_ctx:  {display_name, role, expertise[list], communication_style}
        - knowledge_text:        accumulated knowledge block
        - directive:             the board's instruction for this session
        - capabilities_summary:  tool-capabilities text
        - partial_specs_text:    team_synthesis only — fills the placeholder
    context keys:
        - platform_identity:     override for the embedded identity block

    Returns:
        {
          "output": {"prompts": {...}, "session_type": str},
          "rationale": str,
          "self_metric": {"confidence": float in [0.0, 1.0]},
        }
    """
```

## Key properties

- **Pure / deterministic** — same input, same output; no I/O, no model calls.
- **Fail-safe** — unknown session types and malformed state never raise; they
  return an empty prompt set with low confidence. A defensive `except` makes
  even a bug fail to `confidence: 0.0` rather than crash.
- **Stdlib-only** — no third-party imports.
- **Caller-preloaded identity** — the large platform-identity block is injected
  via `context["platform_identity"]`; a faithful default is embedded as a
  fallback so a bare `decide()` still emits a complete prompt.

## Samples

`samples/*.json` carry `{"state": ..., "context": ...}` payloads:

- `autonomous_sales_session.json` — Tim (Head of Sales) prioritising prospects
- `spec_session.json` — Matt-Proto writing a technical spec
- `team_synthesis.json` — Matt synthesising sub-team partial specs

Run any sample:

```bash
ORGAN_INPUT=samples/spec_session.json python3 organ.py | python3 -m json.tool
# or via stdin
cat samples/spec_session.json | python3 organ.py
```

## Testing

```bash
python3 check_contract.py          # contract shape on every sample + empty state
python -m pip install pytest && python -m pytest -q
```

CI (`.github/workflows/conformance.yml`) runs both on every push/PR.
