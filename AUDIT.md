# Corpus + OSS audit — 2026-06-11

Freshness stamped in `ports.json` `_checked` block
(`corpus_checked` / `oss_checked` = `2026-06-11`). Convention:
`discovery-engine/docs/architecture/corpus-oss-sweep.md`.

## (A) Corpus check — faithful mirror, but a DUPLICATE repo exists

**Source:** `discovery-engine/app/prompts/autonomous_session.py`.

- `organ.py` faithfully mirrors the source: all three builders
  (`build_persona_session_prompt`, `build_spec_session_prompt`,
  `build_team_spec_synthesis_system_prompt`) and both prompt constants
  (`SPEC_EXTRACTION_PROMPT`, `TEAM_SPEC_SYNTHESIS_PROMPT`) match the source
  literals **byte-for-byte** (verified via AST extraction + compare).
- `check_contract.py` ✓ on every sample + empty state; `pytest` 26 passed.
- **No drift** against the live corpus.

**DUPLICATE FOUND.** This repo (`organ-app-prompts-autonomous-session-v2`) is a
clean fork of `organ-app-prompts-autonomous-session` (v1) — the same organ,
same source module, same `decide()` contract. v2 was created at 2026-06-11
00:25Z *only* to dodge v1's then-RED CI (v1's workflow didn't install `pytest`
and its `.py` samples couldn't import `organ`). That condition is now resolved:

- v1's CI is **green on `main`** since the 03:53Z `fix(ci)` push.
- v1 has an active, **green** ports-manifest PR (`feat/ports-manifest`) — the
  canonical ports treatment the rest of the corpus is getting.
- v1 carries the original un-suffixed name; the `-v2` suffix is a workaround
  artifact.

Neither repo is wired into the orchestrator `types.json` vocab or referenced
from discovery-engine, so retiring one is low-risk.

**Recommendation:** consolidate to ONE organ. Keep v1
(`organ-app-prompts-autonomous-session`) as canonical (original name, green CI,
ports work in flight); **archive/retire this v2 fork** once v1's
`feat/ports-manifest` PR lands. Flagged in a tracking issue.

## (B) OSS check — KEEP (no adopt-candidate)

Surveyed the prompt-template OSS market (`prompt-template` by Goldziher,
`prompt-templates` on the HF Hub, OpenPrompt, PromptLayer). **Verdict: keep.**

- This organ's value is the **verbatim DataFlow Advisory domain prompt content**
  (persona / spec / team-synthesis prompts + the platform-identity block), not
  the trivial selection logic. No OSS library carries that content.
- The selection + render layer is ~30 LOC of stdlib (`str.format` / f-strings).
  Adopting a templating library would add a third-party dependency to do what
  the stdlib already does, for **zero functional gain**.
- The whole organ corpus is **stdlib-only by conformance design** — pulling in a
  third-party prompt lib would violate that gate.

## Verdict

| Dimension | Verdict | Ref |
|-----------|---------|-----|
| Corpus    | **DUPLICATE** of `organ-app-prompts-autonomous-session` (v1) — consolidate to v1 | see tracking issue |
| OSS       | **KEEP** — domain prompt content + trivial stdlib render; no supersede candidate | — |
