#!/usr/bin/env python3
"""Tests for the autonomous-session organ. Vanilla pytest, stdlib only."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from organ import (
    decide,
    run_organ,
    build_persona_session_prompt,
    build_spec_session_prompt,
    build_team_spec_synthesis_system_prompt,
    SPEC_EXTRACTION_PROMPT,
    TEAM_SPEC_SYNTHESIS_PROMPT,
    _DEFAULT_PLATFORM_IDENTITY,
)

HERE = Path(__file__).parent


# --------------------------------------------------------------------------- #
# Contract shape
# --------------------------------------------------------------------------- #
def _assert_envelope(r):
    assert isinstance(r, dict)
    assert set(r.keys()) >= {"output", "rationale", "self_metric"}
    assert isinstance(r["output"], dict)
    assert isinstance(r["rationale"], str) and r["rationale"]
    assert isinstance(r["self_metric"], dict)
    c = r["self_metric"]["confidence"]
    assert isinstance(c, float)
    assert 0.0 <= c <= 1.0


def test_contract_shape_on_every_branch():
    for st in ("autonomous", "spec", "team_synthesis", "garbage"):
        _assert_envelope(decide({"session_type": st}))


def test_empty_state_defaults_to_autonomous():
    r = decide({})
    _assert_envelope(r)
    assert r["output"]["session_type"] == "autonomous"
    assert "system" in r["output"]["prompts"]
    assert r["self_metric"]["confidence"] == 1.0


def test_none_state_is_safe():
    r = decide(None)
    _assert_envelope(r)
    assert r["output"]["session_type"] == "autonomous"


# --------------------------------------------------------------------------- #
# autonomous
# --------------------------------------------------------------------------- #
def test_autonomous_minimal():
    r = decide({"session_type": "autonomous"})
    assert r["output"]["session_type"] == "autonomous"
    assert "system" in r["output"]["prompts"]
    assert r["self_metric"]["confidence"] == 1.0
    assert "autonomous" in r["rationale"].lower()


def test_autonomous_full_context_renders_fields():
    r = decide({
        "session_type": "autonomous",
        "persona_ctx": {
            "display_name": "Matt",
            "role": "CTO",
            "expertise": ["architecture", "infrastructure"],
            "communication_style": "direct and evidence-based",
        },
        "knowledge_text": "Prior findings from earlier sessions.",
        "directive": "Design a microservices architecture.",
        "capabilities_summary": "Tools: web search, codebase read, GitHub issues",
    })
    sysp = r["output"]["prompts"]["system"]
    assert "Matt" in sysp
    assert "CTO" in sysp
    assert "architecture" in sysp
    assert "Design a microservices architecture" in sysp
    assert "Tools: web search" in sysp
    assert "draft_email" in sysp
    assert r["self_metric"]["confidence"] == 1.0


def test_autonomous_includes_platform_identity_default():
    sysp = decide({"session_type": "autonomous"})["output"]["prompts"]["system"]
    assert "PLATFORM IDENTITY" in sysp
    assert "DataFlow Advisory" in sysp
    assert "client tenant" in sysp.lower()


def test_platform_identity_override_via_context():
    r = decide(
        {"session_type": "autonomous"},
        {"platform_identity": "CUSTOM-IDENTITY-BLOCK"},
    )
    sysp = r["output"]["prompts"]["system"]
    assert "CUSTOM-IDENTITY-BLOCK" in sysp
    assert "DataFlow Advisory" not in sysp.split("PLATFORM IDENTITY")[1]


def test_blank_identity_override_falls_back_to_default():
    r = decide({"session_type": "autonomous"}, {"platform_identity": "   "})
    assert "DataFlow Advisory" in r["output"]["prompts"]["system"]


# --------------------------------------------------------------------------- #
# spec
# --------------------------------------------------------------------------- #
def test_spec_session_has_system_and_extraction():
    r = decide({
        "session_type": "spec",
        "persona_ctx": {"display_name": "Sam", "role": "Product Lead"},
        "knowledge_text": "User research insights...",
        "capabilities_summary": "Tools available: database, GitHub",
    })
    assert r["output"]["session_type"] == "spec"
    prompts = r["output"]["prompts"]
    assert "system" in prompts and "extraction" in prompts
    assert "Sam" in prompts["system"]
    assert "technical specification" in prompts["system"]
    assert "JSON object" in prompts["extraction"]
    assert "T1" in prompts["extraction"]
    assert r["self_metric"]["confidence"] == 1.0


# --------------------------------------------------------------------------- #
# team_synthesis
# --------------------------------------------------------------------------- #
def test_team_synthesis_system_and_synthesis():
    r = decide({
        "session_type": "team_synthesis",
        "persona_ctx": {"display_name": "Matt", "role": "CTO"},
        "directive": "Merge the sub-team specs into one coherent design.",
    })
    assert r["output"]["session_type"] == "team_synthesis"
    prompts = r["output"]["prompts"]
    assert "Matt" in prompts["system"]
    assert "synthesising" in prompts["system"].lower()
    assert "Merge the sub-team specs" in prompts["system"]
    assert "contributors" in prompts["synthesis"]
    assert "Deduplicate" in prompts["synthesis"]


def test_team_synthesis_fills_partial_specs_placeholder():
    r = decide({
        "session_type": "team_synthesis",
        "persona_ctx": {"display_name": "Matt", "role": "CTO"},
        "partial_specs_text": "ARCH SPEC: do X.\nPROTO SPEC: do Y.",
    })
    synth = r["output"]["prompts"]["synthesis"]
    assert "{partial_specs_text}" not in synth
    assert "ARCH SPEC: do X." in synth
    assert "PROTO SPEC: do Y." in synth


def test_team_synthesis_without_partials_leaves_placeholder():
    r = decide({"session_type": "team_synthesis"})
    synth = r["output"]["prompts"]["synthesis"]
    assert "{partial_specs_text}" in synth


def test_team_synthesis_defaults_role_to_team_lead():
    r = decide({"session_type": "team_synthesis"})
    assert "team lead" in r["output"]["prompts"]["system"].lower()


# --------------------------------------------------------------------------- #
# fail-safe
# --------------------------------------------------------------------------- #
def test_unknown_session_type_fails_safe():
    r = decide({"session_type": "nope"})
    assert r["output"]["session_type"] == "nope"
    assert r["output"]["prompts"] == {}
    assert r["self_metric"]["confidence"] < 0.5
    assert "Unknown session_type" in r["rationale"]


def test_non_dict_persona_ctx_is_tolerated():
    r = decide({"session_type": "autonomous", "persona_ctx": "not-a-dict"})
    _assert_envelope(r)
    assert "an advisor" in r["output"]["prompts"]["system"]


def test_non_list_expertise_is_coerced():
    r = decide({
        "session_type": "autonomous",
        "persona_ctx": {"expertise": "architecture"},
    })
    assert "architecture" in r["output"]["prompts"]["system"]


# --------------------------------------------------------------------------- #
# constants & determinism
# --------------------------------------------------------------------------- #
def test_constants_well_formed():
    assert "JSON" in SPEC_EXTRACTION_PROMPT
    assert "acceptance_criteria" in SPEC_EXTRACTION_PROMPT
    assert "SYNTHESISE" in TEAM_SPEC_SYNTHESIS_PROMPT
    assert "partial_specs_text" in TEAM_SPEC_SYNTHESIS_PROMPT
    assert "DataFlow Advisory" in _DEFAULT_PLATFORM_IDENTITY


def test_builders_are_callable_directly():
    assert "Tim" in build_persona_session_prompt(display_name="Tim", role="Sales")
    assert "spec" in build_spec_session_prompt(display_name="Sam").lower()
    assert "synthesis" in build_team_spec_synthesis_system_prompt(
        display_name="Matt"
    ).lower() or "synthesising" in build_team_spec_synthesis_system_prompt(
        display_name="Matt"
    ).lower()


def test_determinism():
    s = {
        "session_type": "autonomous",
        "persona_ctx": {"display_name": "Jordan", "role": "Finance"},
        "directive": "Audit the API cost ledger.",
    }
    assert decide(dict(s)) == decide(dict(s))


def test_rationale_reflects_decision():
    assert "autonomous" in decide({"session_type": "autonomous"})["rationale"].lower()
    assert "spec" in decide({"session_type": "spec"})["rationale"].lower()
    assert "synthesis" in decide({"session_type": "team_synthesis"})["rationale"].lower()


# --------------------------------------------------------------------------- #
# CLI / run_organ + samples
# --------------------------------------------------------------------------- #
def test_run_organ_wraps_decide():
    r = run_organ({"state": {"session_type": "spec"}, "context": {}})
    assert r["output"]["session_type"] == "spec"


def test_run_organ_tolerates_garbage():
    _assert_envelope(run_organ("not-a-dict"))


@pytest.mark.parametrize("sample", sorted((HERE / "samples").glob("*.json")))
def test_samples_conform(sample):
    payload = json.loads(sample.read_text())
    r = run_organ(payload)
    _assert_envelope(r)


def test_cli_via_organ_input(tmp_path):
    sample = next((HERE / "samples").glob("*.json"))
    env = dict(os.environ, ORGAN_INPUT=str(sample))
    out = subprocess.run(
        ["python3", str(HERE / "organ.py")],
        env=env, capture_output=True, text=True, cwd=str(HERE),
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert "self_metric" in data and "confidence" in data["self_metric"]
