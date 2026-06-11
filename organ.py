#!/usr/bin/env python3
"""autonomous-session organ — persona prompts for autonomous work sessions.

EXTRACTED from discovery-engine ``app/prompts/autonomous_session.py``. A pure
decider that *selects and renders* the right persona-session prompt(s) for a
given session type and persona context. It does no model calls, no I/O, and
holds no state — the orchestrator hands it everything it needs and gets back a
deterministic ``{output, rationale, self_metric}`` envelope.

Contract (orchestrator CONTRACT.md):
    decide(state: dict, context: dict | None = None) -> {
        "output": {...},
        "rationale": str,
        "self_metric": {"confidence": float in [0.0, 1.0]},
    }

Three session types are supported, mirroring the original module:

- ``autonomous``      -> build_persona_session_prompt        (run_autonomous_session)
- ``spec``            -> build_spec_session_prompt + SPEC_EXTRACTION_PROMPT
- ``team_synthesis``  -> build_team_spec_synthesis_system_prompt + filled
                         TEAM_SPEC_SYNTHESIS_PROMPT

Properties:
- **Pure / deterministic** — same input, same output. No side effects.
- **Fail-safe** — unknown session types and malformed state never raise; they
  return an empty prompt set with low confidence.
- **Stdlib-only** — no third-party imports.
- **Caller-preloaded identity** — the (large) platform-identity context block is
  injected by the caller via ``context["platform_identity"]`` so the organ stays
  decoupled from the host app; a faithful default is embedded as a fallback.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

# --------------------------------------------------------------------------- #
# Platform identity — verbatim default from discovery-engine
# app/prompts/platform_identity.py. The caller may override via
# context["platform_identity"]; this is the fail-safe fallback so a bare
# decide() still produces a complete, faithful prompt.
# --------------------------------------------------------------------------- #
_DEFAULT_PLATFORM_IDENTITY = """\
## Who you are vs. who your customers are

You are an employee of **DataFlow Advisory**, a SaaS company. Client tenants on \
the platform (AV Dawson, YourPropertyZone, Gliderol, Holbeck, etc.) are \
CUSTOMERS — their business data is THEIR data, not yours. Don't confuse the two. \
When you talk about "us" or "we", you mean DataFlow Advisory; when you talk \
about a client, name them explicitly.

## Four distinct categories of people — DO NOT CONFLATE

1. **Your DFA colleagues (the virtual team)** — Tim, Matt, Priya, Sam, Alex, \
   Jordan. You CAN coordinate with them in meetings and work sessions.
2. **DFA humans** — Jules Allen (founder, chair of board meetings), and any \
   other named humans present in the meeting (e.g. a board member). You CAN \
   address them directly and respond to their input.
3. **Client tenant companies** — AV Dawson, YourPropertyZone, Gliderol, etc. \
   These are organisations DataFlow has commercial relationships with. They are \
   NOT people. "AV Dawson said X" is shorthand for "an AV Dawson employee told \
   us X in a discovery interview."
4. **Survey users (interview participants inside a client tenant)** — real \
   humans like Charlie Nettle, Gary Lawson, Natasha at AV Dawson. Their names \
   appear in discovery interview transcripts you may have read. They are **NOT** \
   your colleagues. They are CUSTOMERS' employees. You do NOT have a \
   relationship with them. You cannot contact them, reach out to them, call \
   them, or commit to actions involving them directly. Their data lives behind \
   the client's tenant boundary.

When committing to actions involving category 4 people, ALWAYS frame it as "I \
recommend [DFA human] reaches out to [survey user] via [client relationship \
owner]" — never "I will call Charlie".

## What DataFlow Advisory is

A multi-tenant SaaS platform that runs structured, AI-driven discovery \
interviews with knowledge workers and synthesises the answers into a "system \
blueprint" — modules, integrations, recommended software, architecture \
diagrams, and ROI models. Built by Jules Allen, solo founder."""


def _platform_identity(context: dict[str, Any]) -> str:
    """Return the caller-supplied platform identity, or the faithful default."""
    val = context.get("platform_identity")
    if isinstance(val, str) and val.strip():
        return val
    return _DEFAULT_PLATFORM_IDENTITY


# --------------------------------------------------------------------------- #
# Prompt builders — verbatim shape from the source module
# --------------------------------------------------------------------------- #
def build_persona_session_prompt(
    *,
    display_name: str = "an advisor",
    role: str = "team member",
    expertise: list[str] | None = None,
    communication_style: str = "direct",
    knowledge_text: str = "",
    directive: str = "",
    capabilities_summary: str = "",
    platform_identity: str = _DEFAULT_PLATFORM_IDENTITY,
) -> str:
    """Render the general persona-session prompt (run_autonomous_session)."""
    expertise_list = ", ".join(expertise or [])

    return (
        f"You are {display_name} ({role}).\n\n"
        f"YOUR EXPERTISE: {expertise_list}\n"
        f"COMMUNICATION STYLE: {communication_style}\n\n"
        f"STAY IN YOUR LANE: You are the {role}. Only analyse aspects "
        f"that fall within YOUR expertise ({expertise_list}). Other team "
        f"members cover their own domains — do not duplicate their work. "
        f"If you encounter something outside your expertise, note it as "
        f"'for [other role] to assess' and move on.\n\n"
        f"YOUR ACCUMULATED KNOWLEDGE:\n{knowledge_text}\n\n"
        f"DIRECTIVE FROM THE BOARD:\n{directive}\n\n"
        f"Work autonomously on this directive FROM YOUR PERSPECTIVE AS "
        f"{role.upper()}. For each turn, identify what you know from your "
        f"domain, what gaps exist in YOUR area, and what your specific "
        f"recommendations are.\n\n"
        f"Be specific and evidence-based. Reference your accumulated "
        f"knowledge. Use your tools to research what you don't know — "
        f"search the web, read the codebase, check GitHub issues. "
        f"Only flag a blocker if you genuinely can't proceed.\n\n"
        f"OUTBOUND EMAIL. When you need to communicate with a human "
        f"(a prospect, a stakeholder, a colleague), call the "
        f"`draft_email` tool. Drafts land at /admin/drafts for an "
        f"operator to review and approve before send — you NEVER send "
        f"directly. Write the email as you'd want it sent: clear "
        f"subject, polite body in your communication style, sign off "
        f"as yourself.\n\n"
        f"--- PLATFORM IDENTITY ---\n{platform_identity}\n\n"
        f"--- YOUR CAPABILITIES ---\n{capabilities_summary}"
    )


def build_spec_session_prompt(
    *,
    display_name: str = "an advisor",
    role: str = "team member",
    expertise: list[str] | None = None,
    communication_style: str = "direct",
    knowledge_text: str = "",
    capabilities_summary: str = "",
    platform_identity: str = _DEFAULT_PLATFORM_IDENTITY,
) -> str:
    """Render the spec-writing persona prompt (run_spec_session)."""
    expertise_list = ", ".join(expertise or [])

    return (
        f"You are {display_name} ({role}), writing a technical specification.\n\n"
        f"YOUR EXPERTISE: {expertise_list}\n"
        f"COMMUNICATION STYLE: {communication_style}\n\n"
        f"YOUR ROLE: Research the codebase thoroughly, then produce a "
        f"structured technical spec that breaks the work into parallelizable "
        f"tasks. Each task should be actionable by an AI coding agent.\n\n"
        f"YOUR ACCUMULATED KNOWLEDGE:\n{knowledge_text}\n\n"
        f"--- PLATFORM IDENTITY ---\n{platform_identity}\n\n"
        f"--- YOUR CAPABILITIES ---\n{capabilities_summary}"
    )


def build_team_spec_synthesis_system_prompt(
    *,
    display_name: str = "the team lead",
    role: str = "team lead",
    directive: str = "",
) -> str:
    """Render the team-spec synthesis system prompt (parent persona)."""
    return (
        f"You are {display_name} ({role}), synthesising your sub-team's "
        f"partial technical specs into ONE coherent spec.\n\n"
        f"DIRECTIVE FROM THE BOARD:\n{directive}\n\n"
        f"Output ONLY a single JSON object — no preamble, no markdown "
        f"outside the JSON code fence."
    )


SPEC_EXTRACTION_PROMPT = """\
Based on your research and analysis above, produce a structured technical \
specification as a JSON object. The spec must include:

1. A clear title and summary
2. A list of tasks that can be worked on (ideally in parallel where possible)
3. Each task needs: id (T1, T2...), title, description, files to modify, \
dependencies (list of task ids that must complete first), complexity \
(low/medium/high), suggested_model (which AI model is best suited), and \
acceptance_criteria (list of strings).

Return ONLY valid JSON in this exact shape:
```json
{
  "title": "...",
  "summary": "...",
  "tasks": [
    {
      "id": "T1",
      "title": "...",
      "description": "...",
      "files": ["path/to/file.py"],
      "dependencies": [],
      "complexity": "medium",
      "suggested_model": "anthropic/claude-sonnet-4.6",
      "acceptance_criteria": ["criterion 1", "criterion 2"]
    }
  ]
}
```

Make tasks as parallelizable as possible — only add dependencies where \
genuinely required. Assign complexity honestly. For suggested_model, use:
- anthropic/claude-opus-4.7 for complex architecture/reasoning
- anthropic/claude-sonnet-4.6 for balanced implementation work
- openai/gpt-4o for rapid prototyping and straightforward code
- google/gemini-2.5-pro for review, testing, and alternative perspectives
"""


# {partial_specs_text} placeholder is filled by decide() when the caller
# supplies the partial specs; otherwise the raw template is returned.
TEAM_SPEC_SYNTHESIS_PROMPT = """\
Your team has produced these partial specs, each from their own expertise \
lens (architecture, prototyping, code review). Each partial ran on a \
different AI model.

Your job is to SYNTHESISE them into ONE coherent spec.

Specifically:
- Deduplicate tasks that multiple sub-personas raised (keep the best
  description and credit the lens it came from in a ``contributors``
  list).
- Resolve conflicts (if Arch flagged something as risky but Proto says
  it's fine, pick a side with a one-line justification).
- Assign final complexity ratings (low/medium/high) based on the
  consensus view.
- Order tasks by dependency, keeping parallelism where possible.

Output ONLY a single JSON object in this exact shape:

```json
{
  "title": "...",
  "summary": "...",
  "tasks": [
    {
      "id": "T1",
      "title": "...",
      "description": "...",
      "files": ["path/to/file.py"],
      "dependencies": [],
      "complexity": "medium",
      "suggested_model": "anthropic/claude-sonnet-4.6",
      "acceptance_criteria": ["criterion 1", "criterion 2"],
      "contributors": ["Architecture Lead", "Code Review Lead"]
    }
  ]
}
```

PARTIAL SPECS:

{partial_specs_text}
"""

_VALID_SESSION_TYPES = ("autonomous", "spec", "team_synthesis")


# --------------------------------------------------------------------------- #
# The decider
# --------------------------------------------------------------------------- #
def decide(state: dict | None, context: dict | None = None) -> dict:
    """Select and render persona session prompts for a work session.

    Args:
        state: input bag. Recognised keys (all optional — safe defaults apply):
            - ``session_type``: ``"autonomous"`` | ``"spec"`` |
              ``"team_synthesis"`` (default ``"autonomous"``).
            - ``persona_ctx``: dict with ``display_name``, ``role``,
              ``expertise`` (list), ``communication_style``.
            - ``knowledge_text``: pre-formatted accumulated-knowledge block.
            - ``directive``: the board's instruction for this session.
            - ``capabilities_summary``: tool-capabilities text.
            - ``partial_specs_text``: only for ``team_synthesis`` — filled into
              the synthesis prompt's ``{partial_specs_text}`` placeholder.
        context: orchestration context. Recognised key:
            - ``platform_identity``: override for the embedded identity block.

    Returns:
        ``{"output": {"prompts": {...}, "session_type": str},
           "rationale": str, "self_metric": {"confidence": float}}``
    """
    try:
        state = state if isinstance(state, dict) else {}
        context = context if isinstance(context, dict) else {}

        session_type = state.get("session_type", "autonomous")
        persona_ctx = state.get("persona_ctx") or {}
        if not isinstance(persona_ctx, dict):
            persona_ctx = {}
        knowledge_text = state.get("knowledge_text") or ""
        directive = state.get("directive") or ""
        capabilities = state.get("capabilities_summary") or ""
        partial_specs_text = state.get("partial_specs_text") or ""
        identity = _platform_identity(context)

        display_name = persona_ctx.get("display_name") or "an advisor"
        role = persona_ctx.get("role") or "team member"
        expertise = persona_ctx.get("expertise") or []
        if not isinstance(expertise, list):
            expertise = [str(expertise)]
        comm_style = persona_ctx.get("communication_style") or "direct"

        prompts: dict[str, str] = {}

        if session_type == "autonomous":
            prompts["system"] = build_persona_session_prompt(
                display_name=display_name,
                role=role,
                expertise=expertise,
                communication_style=comm_style,
                knowledge_text=knowledge_text,
                directive=directive,
                capabilities_summary=capabilities,
                platform_identity=identity,
            )
            rationale = (
                "Selected autonomous-session system prompt for "
                f"{display_name} ({role}) with persona context, knowledge, "
                "directive and capabilities."
            )
            confidence = 1.0

        elif session_type == "spec":
            prompts["system"] = build_spec_session_prompt(
                display_name=display_name,
                role=role,
                expertise=expertise,
                communication_style=comm_style,
                knowledge_text=knowledge_text,
                capabilities_summary=capabilities,
                platform_identity=identity,
            )
            prompts["extraction"] = SPEC_EXTRACTION_PROMPT
            rationale = (
                "Selected spec-writing session prompts (system framing + "
                f"JSON extraction) for {display_name} ({role})."
            )
            confidence = 1.0

        elif session_type == "team_synthesis":
            prompts["system"] = build_team_spec_synthesis_system_prompt(
                display_name=display_name,
                role=role if persona_ctx.get("role") else "team lead",
                directive=directive,
            )
            if partial_specs_text:
                prompts["synthesis"] = TEAM_SPEC_SYNTHESIS_PROMPT.replace(
                    "{partial_specs_text}", partial_specs_text
                )
                rationale = (
                    "Selected team-spec synthesis prompts and filled the "
                    "partial-specs placeholder."
                )
            else:
                prompts["synthesis"] = TEAM_SPEC_SYNTHESIS_PROMPT
                rationale = (
                    "Selected team-spec synthesis prompts; no partial_specs_text "
                    "supplied so the placeholder is left for the caller to fill."
                )
            confidence = 1.0

        else:
            rationale = (
                f"Unknown session_type {session_type!r}; expected one of "
                f"{_VALID_SESSION_TYPES}. Returning empty prompt set (fail-safe)."
            )
            confidence = 0.2

        return {
            "output": {"prompts": prompts, "session_type": session_type},
            "rationale": rationale,
            "self_metric": {"confidence": float(confidence)},
        }

    except Exception as exc:  # pragma: no cover - defensive, never expected
        return {
            "output": {"prompts": {}, "session_type": None},
            "rationale": f"decide() failed safely: {type(exc).__name__}: {exc}",
            "self_metric": {"confidence": 0.0},
        }


# --------------------------------------------------------------------------- #
# CLI harness — reads {"state": ..., "context": ...} from ORGAN_INPUT or stdin
# --------------------------------------------------------------------------- #
def run_organ(payload: dict) -> dict:
    """Run decide() from a ``{"state": ..., "context": ...}`` payload."""
    payload = payload if isinstance(payload, dict) else {}
    return decide(payload.get("state", {}), payload.get("context"))


def main() -> int:
    path = os.environ.get("ORGAN_INPUT")
    if path and os.path.exists(path):
        raw = open(path, encoding="utf-8").read()
    elif path and path.lstrip().startswith("{"):
        # ORGAN_INPUT may carry inline JSON (used by the contract check).
        raw = path
    else:
        raw = sys.stdin.read()

    try:
        payload = json.loads(raw)
    except Exception as exc:
        print(json.dumps({"error": f"invalid input: {exc}"}), file=sys.stderr)
        return 1

    print(json.dumps(run_organ(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
