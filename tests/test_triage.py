"""Tests for RepoRouter's parsing, validation, and guardrails.

No network, no LLM, no GitHub — these pin the deterministic layer:
the parts that decide whether model output is safe to act on.

Run: python -m pytest tests/ -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import triage  # noqa: E402


# ---------------------------------------------------------------------------
# strip_think — chain-of-thought must never survive
# ---------------------------------------------------------------------------

def test_strip_think_removes_closed_block():
    text = "<think>secret reasoning</think>ROUTE: CLOSE"
    assert triage.strip_think(text) == "ROUTE: CLOSE"


def test_strip_think_removes_multiline_block():
    text = "before\n<think>\nline1\nline2\n</think>\nafter"
    out = triage.strip_think(text)
    assert "line1" not in out and "before" in out and "after" in out


def test_strip_think_truncates_unclosed_block():
    text = "ROUTE: RESPOND\n<think>never closed reasoning leaking"
    out = triage.strip_think(text)
    assert "reasoning" not in out
    assert "ROUTE: RESPOND" in out


def test_strip_think_case_insensitive():
    assert "hidden" not in triage.strip_think("<THINK>hidden</THINK>ok")


# ---------------------------------------------------------------------------
# parse_category
# ---------------------------------------------------------------------------

def test_parse_category_standard():
    assert triage.parse_category("CATEGORY: bug") == "bug"


def test_parse_category_with_think_block():
    assert triage.parse_category("<think>hmm</think>\nCATEGORY: Security") == "security"


def test_parse_category_bare_word():
    assert triage.parse_category("spam") == "spam"


def test_parse_category_garbage_is_unknown():
    assert triage.parse_category("I think this could be several things") == "unknown"
    assert triage.parse_category("") == "unknown"
    assert triage.parse_category("CATEGORY: bananas") == "unknown"


# ---------------------------------------------------------------------------
# parse_output
# ---------------------------------------------------------------------------

FULL_OUTPUT = """\
ISSUE: owner/repo#7 - Crash on empty config
AUTHOR: someuser (external)
CATEGORY: bug   (was: bug - unchanged)
DOCS CHECKED: docs/SPEC.md, CHANGELOG.md
ROUTE: RESPOND
LABELS: bug, nonsense-label (KEEP: none)
PRIORITY: P1
-----
DRAFT:
Thanks for the report. The spec (section 3) says the config loader must
default missing keys, so this is a confirmed defect.
"""


def test_parse_full_output():
    p = triage.parse_output(FULL_OUTPUT)
    assert p["route"] == "RESPOND"
    assert p["category"] == "bug"
    assert p["priority"] == "P1"
    assert p["docs_checked"] == "docs/SPEC.md, CHANGELOG.md"
    assert p["draft"].startswith("Thanks for the report.")
    assert "ROUTE" not in p["draft"]


def test_parse_labels_are_whitelisted():
    p = triage.parse_output(FULL_OUTPUT)
    assert p["labels"] == ["bug"]  # nonsense-label dropped, never created


def test_parse_unicode_separator():
    text = FULL_OUTPUT.replace("-----", "─────────────")
    p = triage.parse_output(text)
    assert p["draft"].startswith("Thanks for the report.")


def test_parse_no_separator_no_draft():
    text = "ROUTE: RESPOND\nLABELS: bug\nThanks for reporting!"
    p = triage.parse_output(text)
    assert p["route"] == "RESPOND"
    assert p["draft"] is None  # must never fall back to raw text


def test_parse_draft_header_without_separator():
    text = "ROUTE: CLOSE\nDRAFT:\nClosing as works-as-designed, see the spec."
    p = triage.parse_output(text)
    assert p["draft"] == "Closing as works-as-designed, see the spec."


def test_parse_escalation_brief_header():
    text = "ROUTE: ESCALATE\nESCALATION BRIEF:\nSpec is silent. Recommend accepting."
    p = triage.parse_output(text)
    assert p["route"] == "ESCALATE"
    assert p["draft"] == "Spec is silent. Recommend accepting."


def test_parse_route_variants():
    assert triage.parse_output("ROUTE: RESPOND + LABEL\n-----\nx")["route"] == "RESPOND"
    assert triage.parse_output("route: close\n-----\nx")["route"] == "CLOSE"
    assert triage.parse_output("ROUTE: escalate to human\n-----\nx")["route"] == "ESCALATE"


def test_parse_priority_fuzzy():
    assert triage.parse_output("PRIORITY: P2 (regression bump)\n-----\nx")["priority"] == "P2"
    assert triage.parse_output("PRIORITY: high\n-----\nx")["priority"] == "n/a"


def test_parse_think_block_stripped_before_parsing():
    text = "<think>ROUTE: CLOSE no wait</think>ROUTE: ESCALATE\n-----\nbrief"
    p = triage.parse_output(text)
    assert p["route"] == "ESCALATE"


def test_parse_never_raises_on_garbage():
    for garbage in ("", "????", "ROUTE:", "-----", "<think>only thoughts"):
        p = triage.parse_output(garbage)
        assert p["draft"] is None or isinstance(p["draft"], str)


# ---------------------------------------------------------------------------
# validate_decision — the harness disposes
# ---------------------------------------------------------------------------

def _parsed(route=None, draft=None):
    return {"route": route, "draft": draft, "labels": [], "priority": "n/a"}


def test_validate_security_always_escalates():
    route, reason = triage.validate_decision(
        _parsed("RESPOND", "Looks exploitable, here is how..."), "security")
    assert route == "ESCALATE"
    assert "security" in reason


def test_validate_hostile_always_escalates():
    route, _ = triage.validate_decision(_parsed("CLOSE", "draft"), "hostile")
    assert route == "ESCALATE"


def test_validate_missing_route_escalates():
    route, reason = triage.validate_decision(_parsed(None, "a draft"), "bug")
    assert route == "ESCALATE" and "ROUTE" in reason


def test_validate_post_without_draft_escalates():
    route, reason = triage.validate_decision(_parsed("RESPOND", None), "bug")
    assert route == "ESCALATE" and "draft" in reason


def test_validate_internal_metadata_in_draft_escalates():
    bad_draft = "Thanks!\nROUTE: CLOSE\nLABELS: bug"
    route, reason = triage.validate_decision(_parsed("RESPOND", bad_draft), "bug")
    assert route == "ESCALATE" and "metadata" in reason


def test_validate_clean_decision_passes():
    route, reason = triage.validate_decision(
        _parsed("RESPOND", "Thanks for the report — confirmed against the spec."), "bug")
    assert route == "RESPOND" and reason == ""


def test_validate_escalate_passes_through():
    route, _ = triage.validate_decision(_parsed("ESCALATE", None), "feature")
    assert route == "ESCALATE"


# ---------------------------------------------------------------------------
# looks_internal
# ---------------------------------------------------------------------------

def test_looks_internal_detects_metadata():
    assert triage.looks_internal("ROUTE: CLOSE\nsome text")
    assert triage.looks_internal("text\nLABELS: bug")
    assert not triage.looks_internal("A normal reply mentioning a route through the parser.")


# ---------------------------------------------------------------------------
# Doc selection
# ---------------------------------------------------------------------------

SAMPLE_INDEX = {
    "readme":    ["README.md"],
    "changelog": ["docs/CHANGELOG.md"],
    "roadmap":   ["docs/ROADMAP.md"],
    "spec":      ["docs/SPEC.md", "docs/DESIGN.md"],
    "claude":    ["CLAUDE.md"],
    "scope":     ["docs/non-goals.md"],
}


def test_select_docs_bug_prefers_spec_and_changelog():
    paths = triage.select_docs(SAMPLE_INDEX, "bug")
    assert "docs/SPEC.md" in paths and "docs/CHANGELOG.md" in paths
    assert "docs/ROADMAP.md" not in paths


def test_select_docs_feature_prefers_roadmap_and_scope():
    paths = triage.select_docs(SAMPLE_INDEX, "feature")
    assert paths[0] == "docs/ROADMAP.md"
    assert "docs/non-goals.md" in paths


def test_select_docs_caps_at_max():
    big = {k: [f"{k}{i}.md" for i in range(10)] for k in ("claude", "readme", "spec")}
    assert len(triage.select_docs(big, "unknown")) <= triage.MAX_DOCS


def test_select_docs_unknown_category_uses_fallback():
    assert triage.select_docs(SAMPLE_INDEX, "not-a-category") == \
        triage.select_docs(SAMPLE_INDEX, "unknown")


def test_doc_patterns_match_uppercase_names():
    """The bug that motivated this: docs/SPEC.md must be discoverable."""
    spec_pattern = dict(
        (k, p) for k, p in triage.DOC_PATTERNS
    )["spec"]
    assert spec_pattern.search("SPEC.md")
    assert spec_pattern.search("spec-overview.md")


# ---------------------------------------------------------------------------
# Decision prompt scoping
# ---------------------------------------------------------------------------

def test_decide_prompt_includes_rubric_only_for_bugs():
    bug_prompt     = triage.build_decide_prompt("bug", {})
    feature_prompt = triage.build_decide_prompt("feature", {})
    assert "=== reference/triage-rubric.md ===" in bug_prompt
    assert "=== reference/triage-rubric.md ===" not in feature_prompt


def test_decide_prompt_handles_no_docs():
    prompt = triage.build_decide_prompt("question", {})
    assert "No project documentation" in prompt


def test_decide_prompt_posting_mode_note():
    posting = triage.build_decide_prompt("bug", {}, posting=True)
    drafting = triage.build_decide_prompt("bug", {}, posting=False)
    assert "posted to GitHub verbatim" in posting
    assert "draft-only" in drafting


def test_decide_prompt_hoists_internal_role():
    owner = triage.build_decide_prompt("bug", {}, author_role="Owner")
    external = triage.build_decide_prompt("bug", {}, author_role="external")
    nobody = triage.build_decide_prompt("bug", {})
    assert "AUTHOR IS INTERNAL" in owner
    assert "AUTHOR IS INTERNAL" not in external
    assert "AUTHOR IS INTERNAL" not in nobody


def test_decide_prompt_states_operational_limits():
    prompt = triage.build_decide_prompt("feature", {})
    assert "cannot write, fix, run, or test code" in prompt
    assert "invented tracking" in prompt


def test_author_role_extracted_from_pasted_issue():
    import re
    text = "Title: x\nIssue #1 — url\nAuthor: someone (Owner)\n\n--- Body ---\nhello"
    m = re.search(r"Author:[^\n(]*\(([^)]+)\)", text)
    assert m and m.group(1) == "Owner"
