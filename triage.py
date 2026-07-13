#!/usr/bin/env python3
"""
RepoRouter — core triage pipeline + CLI.

CLI usage:
    python triage.py <owner/repo>
    python triage.py <owner/repo> --dry-run
    python triage.py <owner/repo> --issue 42
    python triage.py <owner/repo> --since 2026-06-01
    python triage.py <owner/repo> --provider ollama --model qwen3:8b

Providers:
    anthropic   Requires ANTHROPIC_API_KEY env var
    ollama      Requires a running Ollama instance (default: http://localhost:11434)

GitHub:
    Requires GITHUB_TOKEN env var (repo scope), or the auto-injected Actions token.
    In GitHub Actions, set BOT_LOGIN=github-actions[bot] (the workflow does this).

Design notes — built to run on small models:
    * Two small LLM calls per issue (categorize, then decide) instead of one
      monolithic prompt. The classifier prompt is tiny; the decision prompt
      carries only the docs relevant to the category.
    * The harness, not the model, enforces the dangerous rules: security and
      hostile issues never reach a posting path, labels are whitelisted,
      existing labels are never stripped, and anything unparseable escalates.
    * Parse failure can never publish raw model output. No draft -> no post.

This module is also imported by chat.py — public functions are stable.
"""

__version__ = "0.3.1"

import os
import re
import sys
import json
import time
import argparse
import requests as _requests
from pathlib import Path
from datetime import datetime, timezone

from github import Github, GithubException

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OLLAMA_MODEL    = "qwen3:8b"
DEFAULT_OLLAMA_HOST     = "http://localhost:11434"

MAX_DOCS      = 5      # docs included in a decision prompt
DOC_CHAR_CAP  = 6000   # per-doc truncation

ROUTES = {"RESPOND", "CLOSE", "ESCALATE"}

CATEGORIES = {
    "security", "hostile", "noise", "spam",
    "duplicate", "bug", "feature", "question", "docs",
}
# Categories the harness resolves itself — the LLM never drafts a public
# reply for these, so a bad model output cannot leak or mislabel them.
FORCED_ESCALATE = {"security", "hostile"}
CANNED_CLOSE    = {"spam"}
# "noise" (test issues, +1, "any update?") gets an LLM-drafted acknowledgment,
# then the harness closes it — there's nothing left to track. Forced here so a
# small model can't leave a throwaway issue open by picking RESPOND.
FORCED_CLOSE    = {"noise"}
# Every surviving category is answered. "noise" used to short-circuit to
# no-action here; it now flows through the decision pipeline like anything else
# so nothing is left silently unanswered.
NO_ACTION: set[str] = set()

# ---------------------------------------------------------------------------
# Operator files (loaded once at startup)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent


def _load_dotenv(path: Path):
    """Load KEY=value lines from .env into the environment (no overrides).

    Kept dependency-free on purpose; real env vars always win.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(SCRIPT_DIR / ".env")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


IDENTITY = _read(SCRIPT_DIR / "identity.md")
RULES    = _read(SCRIPT_DIR / "rules.md")

REFERENCE_FILES = {
    f.name: _read(f)
    for f in sorted((SCRIPT_DIR / "reference").glob("*.md"))
    if f.is_file()
}

# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks some models (e.g. qwen3) emit.

    An unclosed <think> tag truncates everything after it — better to lose
    the output (and escalate) than to ever publish chain-of-thought.
    """
    text = _THINK_RE.sub("", text)
    open_tag = text.lower().find("<think>")
    if open_tag != -1:
        text = text[:open_tag]
    return text.strip()


def call_llm(
    system: str,
    user: str,
    provider: str = "anthropic",
    model: str = DEFAULT_ANTHROPIC_MODEL,
    anthropic_key: str | None = None,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    max_tokens: int = 4096,
) -> str:
    """Call the configured LLM and return the cleaned response text."""
    if provider == "ollama":
        raw = _call_ollama(system, user, model, ollama_host)
    else:
        raw = _call_anthropic(system, user, model,
                              anthropic_key or os.environ.get("ANTHROPIC_API_KEY", ""),
                              max_tokens)
    return strip_think(raw)


def _call_anthropic(system: str, user: str, model: str, api_key: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _call_ollama(system: str, user: str, model: str, host: str) -> str:
    resp = _requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def list_ollama_models(host: str = DEFAULT_OLLAMA_HOST) -> list[str]:
    """Return model names available in Ollama, or [] if unreachable."""
    try:
        resp = _requests.get(f"{host}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def check_ollama(host: str, model: str) -> str | None:
    """Health check. Returns an error message, or None if ready."""
    models = list_ollama_models(host)
    if not models:
        return (f"Ollama is unreachable at {host}. Start it (`ollama serve`) "
                f"or pass --ollama-host.")
    if not any(m == model or m.startswith(model + ":") for m in models):
        return (f"Model '{model}' is not pulled on {host}. "
                f"Run `ollama pull {model}`. Available: {', '.join(models)}")
    return None


# ---------------------------------------------------------------------------
# Phase 1 — categorize (tiny prompt, cheap call)
# ---------------------------------------------------------------------------

CATEGORIZE_SYSTEM = """\
You classify GitHub issues. Assign exactly one category:

security  - vulnerability, exploit, CVE, auth bypass, injection, leaked secret
hostile   - abuse, slurs, threats, sustained personal attacks
noise     - "+1", "me too", "any update?", empty body, emoji-only
spam      - promotion, unrelated links, gibberish, off-topic marketing
duplicate - references or obviously restates another issue (e.g. cites #123 as the same problem)
bug       - reports broken or unexpected behavior with some specifics
feature   - requests a new capability ("add support for...", "it would be great if...")
question  - usage / how-do-I / configuration help, no defect claimed
docs      - reports missing, outdated, or wrong documentation

If two fit, the one listed higher wins. Security and hostile always win.

Respond with exactly one line and nothing else:
CATEGORY: <name>
"""


def parse_category(text: str) -> str:
    """Extract a category from the classifier response. Unknown -> 'unknown'."""
    text = strip_think(text)
    m = re.search(r"CATEGORY\s*:\s*([a-zA-Z]+)", text)
    word = (m.group(1) if m else text.strip().split()[0] if text.strip() else "").lower()
    return word if word in CATEGORIES else "unknown"


def categorize(issue_text: str, **llm_kwargs) -> str:
    """Phase 1: classify the issue. Returns a CATEGORIES member or 'unknown'."""
    raw = call_llm(CATEGORIZE_SYSTEM, issue_text, max_tokens=512, **llm_kwargs)
    return parse_category(raw)


# ---------------------------------------------------------------------------
# Doc discovery — list the repo's documentation surface, fetch per category
# ---------------------------------------------------------------------------

# Ordered (kind, pattern) — matched case-insensitively against file names.
DOC_PATTERNS = [
    ("claude",    re.compile(r"^(claude|agents)\.md$", re.I)),
    ("readme",    re.compile(r"^readme\.(md|rst|txt)$", re.I)),
    ("changelog", re.compile(r"changelog", re.I)),
    ("roadmap",   re.compile(r"roadmap", re.I)),
    ("spec",      re.compile(r"spec|design|rfc|adr", re.I)),
    ("scope",     re.compile(r"non.?goals|scope", re.I)),
    ("issues",    re.compile(r"open.?issues", re.I)),
    ("faq",       re.compile(r"faq|troubleshoot", re.I)),
    ("contrib",   re.compile(r"^contributing\.(md|rst|txt)$", re.I)),
]

# Which doc kinds matter per category, in priority order.
CATEGORY_DOCS = {
    "bug":       ["claude", "spec", "scope", "changelog", "readme"],
    "feature":   ["roadmap", "scope", "issues", "readme"],
    "question":  ["readme", "faq", "claude", "spec"],
    "docs":      ["readme", "changelog", "spec", "claude"],
    "duplicate": ["issues", "changelog", "readme"],
    "unknown":   ["claude", "readme", "spec", "roadmap", "changelog"],
}

_DOC_EXT = re.compile(r"\.(md|rst|txt)$", re.I)


def discover_docs(repo) -> dict[str, list[str]]:
    """Build an index {kind: [paths]} from the repo root and docs/ directory.

    This is rules.md Step 0, performed by the harness: one cheap listing pass,
    no full-content reads. Case-insensitive, so docs/SPEC.md is found.
    """
    index: dict[str, list[str]] = {}

    def scan(dir_path: str):
        try:
            entries = repo.get_contents(dir_path)
        except GithubException:
            return
        if not isinstance(entries, list):
            entries = [entries]
        for entry in entries:
            if entry.type != "file" or not _DOC_EXT.search(entry.name):
                continue
            for kind, pattern in DOC_PATTERNS:
                if pattern.search(entry.name):
                    index.setdefault(kind, []).append(entry.path)
                    break

    scan("")
    scan("docs")
    return index


def select_docs(index: dict[str, list[str]], category: str) -> list[str]:
    """Pick the doc paths relevant to this category (rules.md Step 4). Capped."""
    paths: list[str] = []
    for kind in CATEGORY_DOCS.get(category, CATEGORY_DOCS["unknown"]):
        for path in index.get(kind, []):
            if path not in paths:
                paths.append(path)
            if len(paths) >= MAX_DOCS:
                return paths
    return paths


def fetch_docs(repo, paths: list[str]) -> dict[str, str]:
    """Fetch and truncate the selected docs."""
    docs = {}
    for path in paths:
        try:
            content = repo.get_contents(path)
            docs[path] = content.decoded_content.decode("utf-8")[:DOC_CHAR_CAP]
        except GithubException:
            pass
    return docs


def get_repo_docs(repo) -> dict[str, str]:
    """Back-compat helper: discover + fetch the general-purpose doc set."""
    return fetch_docs(repo, select_docs(discover_docs(repo), "unknown"))


# ---------------------------------------------------------------------------
# Phase 2 — decide (rules.md pipeline against the relevant docs)
# ---------------------------------------------------------------------------

OUTPUT_CONTRACT = """\
Produce EXACTLY this output format:

ISSUE: <repo>#<n> - <title>
AUTHOR: <name> (<role>)
CATEGORY: <final category>   (was: <provisional> - flipped because ..., or "unchanged")
DOCS CHECKED: <doc paths you used, or "none">
ROUTE: RESPOND | CLOSE | ESCALATE
LABELS: <labels to apply, comma-separated, or "none">
PRIORITY: P0 | P1 | P2 | P3 | n/a
-----
DRAFT:
<the finished public reply or closing comment - or, for ESCALATE, the private
brief for the maintainer, ending with a recommendation>

The line of five dashes is required - it separates metadata from the draft.
Everything after it is the artifact. Never repeat ROUTE/LABELS/CATEGORY lines
below the dashes."""


INTERNAL_ROLES = {"Owner", "Member", "Collaborator"}


def build_decide_prompt(category: str, repo_docs: dict[str, str], posting: bool = True,
                        author_role: str | None = None) -> str:
    """System prompt for the decision call. Scoped to the category.

    Conditionals a small model reliably misses when buried in rules.md
    (author role, operational limits) are hoisted into direct instructions here.
    """
    ref_names = ["label-taxonomy.md", "response-templates.md"]
    if category in ("bug", "unknown"):
        ref_names.append("triage-rubric.md")
    ref_block = "\n\n".join(
        f"=== reference/{name} ===\n{REFERENCE_FILES[name]}"
        for name in ref_names if name in REFERENCE_FILES
    )

    if repo_docs:
        doc_block = "\n\n".join(
            f"=== {path} ===\n{content}"
            for path, content in repo_docs.items()
        )
    else:
        doc_block = ("(No project documentation was found. You cannot verify intended "
                     "behavior against a spec - escalate anything that needs one.)")

    mode_note = (
        "Your DRAFT will be posted to GitHub verbatim. It must be finished, "
        "public-ready prose: no placeholders, no internal notes, no metadata."
        if posting else
        "This is a draft-only run. A human reviews everything before anything is posted."
    )

    role_note = ""
    if author_role in INTERNAL_ROLES:
        role_note = (
            f"\nIMPORTANT - THE AUTHOR IS INTERNAL ({author_role}). This is the team "
            f"logging its own work, not an external ticket. Write the draft as a terse "
            f"internal note: start with the finding itself, no greeting, no 'Thanks', "
            f"no outreach voice. State what the docs say, the decision, and the next "
            f"step. (e.g. 'On the roadmap: v0.4, GitHub App auth. Labeling "
            f"enhancement.')\n"
        )

    return (
        f"You are RepoRouter, an automated issue-triage operator for this project. "
        f"A first pass classified this issue as: {category}. Verify that against the "
        f"documentation below and flip it if the docs say otherwise.\n"
        f"{mode_note}\n"
        f"{role_note}\n"
        f"Operational limits - never violate these in a draft:\n"
        f"- You cannot write, fix, run, or test code. Never offer to ('I'll draft a "
        f"fix', 'want me to patch this?').\n"
        f"- Never include a URL, issue number, file path, or version that does not "
        f"appear in the issue or the documentation below. No invented tracking "
        f"issues, links, or forums.\n"
        f"- No [bracketed] placeholders may survive into a draft - fill them with a "
        f"verified specific or drop the sentence.\n\n"
        f"Follow the decision pipeline in rules.md below. Steps 0 and 4 are already "
        f"done for you - the relevant project docs are included in this prompt. "
        f"Do not invent facts that are not in them.\n\n"
        f"=== rules.md ===\n{RULES}\n\n"
        f"=== Reference files ===\n{ref_block}\n\n"
        f"=== Project documentation ===\n{doc_block}\n\n"
        f"{OUTPUT_CONTRACT}"
    )


def build_system_prompt(repo_docs: dict[str, str], posting: bool = True) -> str:
    """Back-compat alias used by older callers; general-purpose decision prompt."""
    return build_decide_prompt("unknown", repo_docs, posting)


# ---------------------------------------------------------------------------
# Output parsing — defensive by design
# ---------------------------------------------------------------------------

_LABEL_COLORS = {
    "bug":              "d73a4a",
    "enhancement":      "a2eeef",
    "question":         "d876e3",
    "documentation":    "0075ca",
    "duplicate":        "cfd3d7",
    "invalid":          "e4e669",
    "wontfix":          "ffffff",
    "good first issue": "7057ff",
    "help wanted":      "008672",
}
LABEL_WHITELIST = set(_LABEL_COLORS)

_SEPARATOR_RE = re.compile(r"^[\s]*[─—\-=_]{4,}[\s]*$", re.MULTILINE)
_DRAFT_HEADER_RE = re.compile(r"^(DRAFT|ESCALATION BRIEF)\s*[:(][^\n]*\n?", re.I | re.M)
_INTERNAL_RE = re.compile(r"^\s*(ROUTE|CATEGORY|LABELS|DOCS CHECKED|PRIORITY)\s*:", re.M)
# An unfilled template placeholder: [bracketed text] NOT followed by ( — which
# would make it a legitimate markdown link.
_PLACEHOLDER_RE = re.compile(r"\[[^\]\n]+\](?!\()")


def parse_output(text: str) -> dict:
    """Parse the decision call's output. Whitelists everything it extracts.

    Guarantees: labels ⊆ LABEL_WHITELIST, route ∈ ROUTES or None,
    draft is the artifact only or None. Never raises.
    """
    text = strip_think(text)
    result = {"category": None, "route": None, "labels": [],
              "priority": "n/a", "docs_checked": None, "draft": None, "raw": text}

    for line in text.splitlines():
        s = line.strip()
        upper = s.upper()
        if upper.startswith("CATEGORY:") and result["category"] is None:
            word = re.search(r"CATEGORY\s*:\s*([a-zA-Z]+)", s)
            if word and word.group(1).lower() in CATEGORIES:
                result["category"] = word.group(1).lower()
        elif upper.startswith("ROUTE:") and result["route"] is None:
            val = s.split(":", 1)[1].upper()
            for route in ("ESCALATE", "CLOSE", "RESPOND"):
                if route in val:
                    result["route"] = route
                    break
        elif upper.startswith("LABELS:") and not result["labels"]:
            raw_labels = re.sub(r"\(.*?\)", "", s.split(":", 1)[1])
            result["labels"] = [
                lb.strip().lower()
                for lb in raw_labels.split(",")
                if lb.strip().lower() in LABEL_WHITELIST
            ]
        elif upper.startswith("PRIORITY:"):
            m = re.search(r"\b(P[0-3])\b", s, re.I)
            result["priority"] = m.group(1).upper() if m else "n/a"
        elif upper.startswith("DOCS CHECKED:"):
            result["docs_checked"] = s.split(":", 1)[1].strip()

    # Draft = everything after the first separator line (drafts may contain
    # their own --- later), or after a DRAFT/ESCALATION BRIEF header.
    # No match -> no draft. Never falls back to raw output.
    draft = None
    first_sep = _SEPARATOR_RE.search(text)
    if first_sep:
        draft = text[first_sep.end():]
    else:
        header = _DRAFT_HEADER_RE.search(text)
        if header:
            draft = text[header.end():]
    if draft is not None:
        draft = _DRAFT_HEADER_RE.sub("", draft, count=1).strip()
        result["draft"] = draft or None

    return result


def looks_internal(draft: str) -> bool:
    """True if a draft still contains pipeline metadata — never post those."""
    return bool(_INTERNAL_RE.search(draft))


def validate_decision(parsed: dict, category: str) -> tuple[str, str]:
    """Harness-enforced routing. Returns (route, reason).

    The model proposes; this function disposes. Anything malformed, and any
    category the harness refuses to let a model publish, becomes ESCALATE.
    """
    if category in FORCED_ESCALATE:
        return "ESCALATE", f"{category} issues never take a public route"
    route = parsed.get("route")
    if route not in ROUTES:
        return "ESCALATE", "model output had no parseable ROUTE"
    if route == "ESCALATE":
        return "ESCALATE", ""
    if not parsed.get("draft"):
        return "ESCALATE", f"route was {route} but no draft could be parsed"
    if looks_internal(parsed["draft"]):
        return "ESCALATE", "draft still contained pipeline metadata"
    if _PLACEHOLDER_RE.search(parsed["draft"]):
        return "ESCALATE", "draft contained an unfilled [template placeholder]"
    if category in FORCED_CLOSE:
        return "CLOSE", "noise: acknowledged and closed"
    return route, ""


# ---------------------------------------------------------------------------
# Canned handling for harness-resolved categories
# ---------------------------------------------------------------------------

SPAM_CLOSE_COMMENT = (
    "This issue doesn't appear to relate to this project, so it's being closed. "
    "If that's a mistake, please open a new issue describing the problem you're "
    "seeing with this software specifically."
)


def _canned_escalation(issue_text: str, category: str) -> dict:
    guidance = {
        "security": ("Possible security report. Handled privately: not labeled, not "
                     "acknowledged publicly. Recommendation: verify the report, fix "
                     "privately if real, and reply to the reporter through a private "
                     "channel. See reference/security-handling.md."),
        "hostile":  ("Hostile content. Not engaged publicly. Recommendation: extract "
                     "any legitimate technical core into a fresh issue if one exists; "
                     "moderation (hide/lock/block) is your call."),
    }[category]
    return {"category": category, "route": "ESCALATE", "labels": [],
            "priority": "n/a", "docs_checked": "short-circuited",
            "draft": f"{guidance}\n\n--- Original issue ---\n{issue_text}",
            "raw": ""}


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

_ROLE_MAP = {
    "OWNER": "Owner", "MEMBER": "Member", "COLLABORATOR": "Collaborator",
    "CONTRIBUTOR": "Contributor",
}


def _author_role(issue) -> str:
    assoc = (issue.raw_data or {}).get("author_association", "NONE")
    return _ROLE_MAP.get(assoc, "external")


def _format_github_issue(issue) -> str:
    labels_str = ", ".join(lb.name for lb in issue.labels) if issue.labels else "none"
    return (
        f"Title: {issue.title}\n"
        f"Issue #{issue.number} — {issue.html_url}\n"
        f"Author: {issue.user.login} ({_author_role(issue)})\n"
        f"Labels already applied: {labels_str}\n"
        f"Created: {issue.created_at.strftime('%Y-%m-%d')}\n"
        f"Existing comment count: {issue.comments}\n\n"
        f"--- Body ---\n"
        f"{issue.body or '(empty body)'}\n"
    )


def _bot_login(gh) -> str:
    """The login whose comments mark an issue as handled.

    The Actions-injected GITHUB_TOKEN has no /user endpoint — fall back to
    BOT_LOGIN (set by the workflow) or the github-actions bot account.
    """
    try:
        return gh.get_user().login
    except GithubException:
        return os.environ.get("BOT_LOGIN", "github-actions[bot]")


def _already_handled(issue, bot_login: str) -> bool:
    for comment in issue.get_comments():
        if comment.user.login == bot_login:
            return True
    return False


def _already_logged_silent(issue_number: int, repo_name: str,
                           base_dir: Path = SCRIPT_DIR) -> bool:
    """True if a prior non-dry run already resolved this issue *silently*.

    ESCALATE and NO ACTION leave no comment, so the comment check alone would
    re-triage them forever. This consults the local IssueLog instead. On an
    ephemeral runner the log is gone and a silent issue re-escalates — loud
    but safe, and the step summary keeps it visible until a human acts.
    """
    log_file = base_dir / "GithubIssues" / "IssueLog" / f"{issue_number}.json"
    if not log_file.is_file():
        return False
    try:
        entry = json.loads(log_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return (entry.get("repo") == repo_name
            and not entry.get("dry_run")
            and entry.get("route") in ("ESCALATE", "NO ACTION"))


def _gh_write(fn, *args, **kwargs):
    """Run a GitHub write with retry on rate-limit/server errors."""
    for attempt, delay in enumerate((0, 5, 20), start=1):
        if delay:
            time.sleep(delay)
        try:
            return fn(*args, **kwargs)
        except GithubException as exc:
            if exc.status in (403, 429, 500, 502, 503) and attempt < 3:
                continue
            raise


def _ensure_labels(repo, names: list[str]):
    existing = {lb.name.lower() for lb in repo.get_labels()}
    for name in names:
        if name not in existing:
            _gh_write(repo.create_label, name, _LABEL_COLORS.get(name, "ededed"))


# ---------------------------------------------------------------------------
# Single-issue triage (used by chat.py paste mode)
# ---------------------------------------------------------------------------

def triage_issue_text(
    issue_text: str,
    repo_docs: dict[str, str] | None = None,
    provider: str = "anthropic",
    model: str = DEFAULT_ANTHROPIC_MODEL,
    anthropic_key: str | None = None,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    posting: bool = False,
) -> dict:
    """Triage a raw issue text string through the full two-phase pipeline.

    Never posts anything. Returns the parsed decision dict with the
    harness-validated route under 'route' and the reason under 'guardrail'.
    """
    llm = dict(provider=provider, model=model,
               anthropic_key=anthropic_key, ollama_host=ollama_host)

    category = categorize(issue_text, **llm)

    if category in FORCED_ESCALATE:
        parsed = _canned_escalation(issue_text, category)
        parsed["guardrail"] = f"{category} issues never take a public route"
        return parsed
    if category in CANNED_CLOSE:
        return {"category": category, "route": "CLOSE", "labels": ["invalid"],
                "priority": "n/a", "docs_checked": "short-circuited", "guardrail": "",
                "draft": SPAM_CLOSE_COMMENT, "raw": ""}

    role_match = re.search(r"Author:[^\n(]*\(([^)]+)\)", issue_text)
    author_role = role_match.group(1).strip() if role_match else None

    system = build_decide_prompt(category, repo_docs or {}, posting=posting,
                                 author_role=author_role)
    raw    = call_llm(system, f"Triage this:\n\n{issue_text}", **llm)
    parsed = parse_output(raw)
    parsed["category"] = parsed["category"] or category
    route, reason = validate_decision(parsed, category)
    parsed["route"] = route
    parsed["guardrail"] = reason
    return parsed


# ---------------------------------------------------------------------------
# Repo triage loop
# ---------------------------------------------------------------------------

def run_triage(
    repo_name: str,
    dry_run: bool = False,
    model: str = DEFAULT_ANTHROPIC_MODEL,
    provider: str = "anthropic",
    anthropic_key: str | None = None,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    progress_cb=None,
    result_cb=None,
    issue_number: int | None = None,
    since: str | None = None,
) -> list[dict]:
    """Triage all unhandled issues in a GitHub repo.

    progress_cb(msg) receives status lines; result_cb(issue, parsed) receives
    each decision (used by chat.py). Returns escalation dicts for followup.md.
    """
    gh_token = os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise RuntimeError("GITHUB_TOKEN environment variable not set.")
    if provider == "anthropic" and not (anthropic_key or os.environ.get("ANTHROPIC_API_KEY")):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")
    if provider == "ollama":
        err = check_ollama(ollama_host, model)
        if err:
            raise RuntimeError(err)

    def log(msg):
        if progress_cb:
            progress_cb(msg)
        else:
            try:
                print(msg)
            except UnicodeEncodeError:
                # Windows consoles may be cp1252; logging must never kill a run.
                enc = sys.stdout.encoding or "ascii"
                print(msg.encode(enc, errors="replace").decode(enc))

    llm = dict(provider=provider, model=model,
               anthropic_key=anthropic_key, ollama_host=ollama_host)

    gh    = Github(gh_token)
    repo  = gh.get_repo(repo_name)
    me    = _bot_login(gh)

    log(f"Operating as: {me}")
    log(f"Targeting repo: {repo.full_name}")
    if dry_run:
        log("DRY RUN — nothing will be posted to GitHub.")

    doc_index = discover_docs(repo)
    log(f"Doc surface: {sum(len(v) for v in doc_index.values())} file(s) across "
        f"{len(doc_index)} kind(s)" if doc_index else "Doc surface: none found")

    since_dt = None
    if since:
        since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    open_issues = [i for i in repo.get_issues(state="open") if not i.pull_request]
    if issue_number is not None:
        open_issues = [i for i in open_issues if i.number == issue_number]
    if since_dt:
        open_issues = [i for i in open_issues
                       if i.created_at.replace(tzinfo=timezone.utc) >= since_dt]
    unprocessed = [i for i in open_issues
                   if not _already_handled(i, me)
                   and not _already_logged_silent(i.number, repo_name)]

    if not unprocessed:
        log("No new issues to triage.")
        _write_followup([], repo_name, dry_run)
        return []

    log(f"Found {len(unprocessed)} unprocessed issue(s).")

    escalations = []

    for issue in unprocessed:
        log(f"#{issue.number}: {issue.title}")
        issue_text = _format_github_issue(issue)

        category = categorize(issue_text, **llm)
        log(f"  category: {category}")

        # --- harness-resolved categories: the LLM never drafts these -------
        if category in FORCED_ESCALATE:
            parsed = _canned_escalation(issue_text, category)
            escalations.append({"issue": issue, "output": parsed["draft"],
                                "parsed": parsed, "reason": parsed.get("guardrail", "")})
            _write_issue_log(issue, parsed, "ESCALATE", repo_name, model, provider, dry_run,
                             guardrail=f"{category}: short-circuited, nothing posted")
            if result_cb:
                result_cb(issue, parsed)
            log("  -> ESCALATE (short-circuit, nothing posted)")
            continue

        if category in CANNED_CLOSE:
            if not dry_run:
                _ensure_labels(repo, ["invalid"])
                _gh_write(issue.add_to_labels, "invalid")
                _gh_write(issue.create_comment, SPAM_CLOSE_COMMENT)
                _gh_write(issue.edit, state="closed")
            parsed = {"category": category, "route": "CLOSE", "labels": ["invalid"],
                      "priority": "n/a", "draft": SPAM_CLOSE_COMMENT, "raw": ""}
            _write_issue_log(issue, parsed, "CLOSE", repo_name, model, provider, dry_run)
            if result_cb:
                result_cb(issue, parsed)
            log("  -> CLOSE (spam, canned reply)")
            continue

        # --- decision call, scoped docs ------------------------------------
        repo_docs = fetch_docs(repo, select_docs(doc_index, category))
        system    = build_decide_prompt(category, repo_docs, posting=not dry_run,
                                        author_role=_author_role(issue))
        raw       = call_llm(system, f"Triage this:\n\n{issue_text}", **llm)
        parsed    = parse_output(raw)
        parsed["category"] = parsed["category"] or category

        route, reason = validate_decision(parsed, category)
        parsed["route"] = route
        parsed["guardrail"] = reason

        log(f"  -> {route}  labels={parsed['labels']}  priority={parsed['priority']}"
            + (f"  [{reason}]" if reason else ""))
        _write_issue_log(issue, parsed, route, repo_name, model, provider, dry_run,
                         guardrail=reason)
        if result_cb:
            result_cb(issue, parsed)

        if route == "ESCALATE":
            escalations.append({"issue": issue, "output": parsed.get("draft") or parsed["raw"],
                                "parsed": parsed, "reason": reason})
            log("  -> Queued for followup.md")
            continue

        if not dry_run:
            if parsed["labels"]:
                _ensure_labels(repo, parsed["labels"])
                _gh_write(issue.add_to_labels, *parsed["labels"])  # adds, never strips
            _gh_write(issue.create_comment, parsed["draft"])
            if route == "CLOSE":
                _gh_write(issue.edit, state="closed")

    _write_followup(escalations, repo_name, dry_run)
    _write_step_summary(escalations, repo_name)
    log(f"Done. {len(escalations)} escalation(s) written to followup.md")
    return escalations


# ---------------------------------------------------------------------------
# Run artifacts — followup.md, per-issue logs, Actions step summary
# ---------------------------------------------------------------------------

def _write_issue_log(issue, parsed: dict, route: str, repo_name: str,
                     model: str, provider: str, dry_run: bool, guardrail: str = ""):
    log_dir = SCRIPT_DIR / "GithubIssues" / "IssueLog"
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "repo":      repo_name,
        "number":    issue.number,
        "title":     issue.title,
        "url":       issue.html_url,
        "author":    issue.user.login,
        "role":      _author_role(issue),
        "created":   issue.created_at.strftime("%Y-%m-%d"),
        "triaged":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "category":  parsed.get("category"),
        "route":     route,
        "labels":    parsed.get("labels", []),
        "priority":  parsed.get("priority", "n/a"),
        "guardrail": guardrail,
        "draft":     parsed.get("draft"),
        "model":     model,
        "provider":  provider,
        "dry_run":   dry_run,
    }
    out = log_dir / f"{issue.number}.json"
    out.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_followup(escalations: list, repo_name: str, dry_run: bool = False):
    out_dir = SCRIPT_DIR / "GithubIssues"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "followup.md"
    lines = [
        "# RepoRouter — Followup Required",
        "",
        f"**Repo:** {repo_name}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
    ]
    if dry_run:
        lines.append("**Mode:** dry run — no changes were posted to GitHub  ")
    lines += ["", "---", ""]

    if not escalations:
        lines += [
            "No escalations this run — all issues were handled automatically.",
            "",
            "_Nothing for you to do here._",
        ]
    else:
        lines += [
            f"{len(escalations)} issue(s) need your decision. "
            "Each includes a recommendation — pick one and act.",
            "",
        ]
        for esc in escalations:
            issue = esc["issue"]
            lines += [
                f"## Issue #{issue.number} — {issue.title}",
                "",
                f"**URL:** {issue.html_url}  ",
                f"**Author:** {issue.user.login} ({_author_role(issue)})  ",
            ]
            if esc.get("reason"):
                lines.append(f"**Escalated because:** {esc['reason']}  ")
            lines += [
                "",
                "### Triage output",
                "",
                "```",
                (esc["output"] or "").strip(),
                "```",
                "",
                "---",
                "",
            ]

    out.write_text("\n".join(lines), encoding="utf-8")


def _write_step_summary(escalations: list, repo_name: str):
    """In GitHub Actions, surface escalations on the run page so they are seen."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [f"## RepoRouter — {repo_name}", ""]
    if not escalations:
        lines.append("No escalations. All issues handled automatically.")
    else:
        lines.append(f"**{len(escalations)} escalation(s) need a human decision:**")
        lines.append("")
        for esc in escalations:
            issue = esc["issue"]
            reason = f" — {esc['reason']}" if esc.get("reason") else ""
            lines.append(f"- [#{issue.number} {issue.title}]({issue.html_url}){reason}")
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoRouter — automated issue triage")
    parser.add_argument("repo", help="GitHub repo in owner/repo format")
    parser.add_argument("--dry-run",     action="store_true", help="Preview without posting")
    parser.add_argument("--provider",    default="anthropic", choices=["anthropic", "ollama"])
    parser.add_argument("--model",       default=None,
                        help=f"Model name (default: {DEFAULT_ANTHROPIC_MODEL} for anthropic, "
                             f"{DEFAULT_OLLAMA_MODEL} for ollama)")
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--issue",       type=int, default=None, metavar="N",
                        help="Triage a single issue by number")
    parser.add_argument("--since",       default=None, metavar="YYYY-MM-DD",
                        help="Only triage issues created on/after this date")
    parser.add_argument("--interval",    type=int, default=None, metavar="MINUTES",
                        help="Run continuously, checking every N minutes")
    args = parser.parse_args()

    default_model = DEFAULT_OLLAMA_MODEL if args.provider == "ollama" else DEFAULT_ANTHROPIC_MODEL
    kwargs = dict(
        dry_run=args.dry_run,
        model=args.model or default_model,
        provider=args.provider,
        ollama_host=args.ollama_host,
        issue_number=args.issue,
        since=args.since,
    )

    if args.interval:
        print(f"Running every {args.interval} minutes. Press Ctrl+C to stop.")
        while True:
            run_triage(args.repo, **kwargs)
            print(f"Sleeping {args.interval} minutes...")
            time.sleep(args.interval * 60)
    else:
        run_triage(args.repo, **kwargs)
