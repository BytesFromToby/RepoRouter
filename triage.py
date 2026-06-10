#!/usr/bin/env python3
"""
The Maintainer — core triage logic + CLI.

CLI usage:
    python triage.py <owner/repo>
    python triage.py <owner/repo> --dry-run
    python triage.py <owner/repo> --provider ollama --model llama3.2

Providers:
    anthropic   Requires ANTHROPIC_API_KEY env var
    ollama      Requires a running Ollama instance (default: http://localhost:11434)

GitHub:
    Requires GITHUB_TOKEN env var (repo scope)

This module is also imported by chat.py — all public functions are stable.
"""

import os
import re
import sys
import json
import argparse
import requests as _requests
from pathlib import Path
from datetime import datetime

from github import Github, GithubException

# ---------------------------------------------------------------------------
# Load operator files once at startup
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent


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

def call_llm(
    system: str,
    user: str,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    anthropic_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
) -> str:
    """Call the configured LLM and return the response text."""
    if provider == "ollama":
        return _call_ollama(system, user, model, ollama_host)
    return _call_anthropic(system, user, model, anthropic_key or os.environ.get("ANTHROPIC_API_KEY", ""))


def _call_anthropic(system: str, user: str, model: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
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
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def list_ollama_models(host: str = "http://localhost:11434") -> list[str]:
    """Return model names available in Ollama, or [] if unreachable."""
    try:
        resp = _requests.get(f"{host}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_system_prompt(repo_docs: dict[str, str], posting: bool = True) -> str:
    ref_block = "\n\n".join(
        f"=== reference/{name} ===\n{content}"
        for name, content in REFERENCE_FILES.items()
    )
    if repo_docs:
        doc_block = "\n\n".join(
            f"=== {path} ===\n{content[:4000]}"
            for path, content in repo_docs.items()
        )
    else:
        doc_block = "(No project documentation found — escalate anything that requires a spec check.)"

    mode_note = (
        "For this run you ARE posting to GitHub, so your DRAFT must be polished prose ready for public display."
        if posting else
        "This is a draft-only preview run. Produce the same output format but note it is for review only."
    )

    return (
        f"You are The Maintainer, an automated issue-triage operator. "
        f"Follow the pipeline in rules.md exactly. {mode_note}\n\n"
        f"=== identity.md ===\n{IDENTITY}\n\n"
        f"=== rules.md ===\n{RULES}\n\n"
        f"=== Reference files ===\n{ref_block}\n\n"
        f"=== Project documentation (target repo) ===\n{doc_block}\n\n"
        f"Produce the output format from rules.md STEP 7 exactly. "
        f"Every response must include ROUTE, LABELS, PRIORITY, and a DRAFT or ESCALATION BRIEF."
    )


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def parse_output(text: str) -> dict:
    result = {"route": None, "labels": [], "priority": "n/a", "draft": None, "raw": text}

    for line in text.splitlines():
        s = line.strip()
        upper = s.upper()
        if upper.startswith("ROUTE:"):
            val = s.split(":", 1)[1].strip().upper()
            if "ESCALATE" in val:
                result["route"] = "ESCALATE"
            elif "CLOSE" in val:
                result["route"] = "CLOSE"
            else:
                result["route"] = "RESPOND"
        elif upper.startswith("LABELS:"):
            raw = re.sub(r'\(.*?\)', '', s.split(":", 1)[1])
            result["labels"] = [
                lb.strip().lower()
                for lb in raw.split(",")
                if lb.strip() and lb.strip().lower() not in ("none", "n/a")
            ]
        elif upper.startswith("PRIORITY:"):
            result["priority"] = s.split(":", 1)[1].strip()

    sep_match = re.search(r'─{5,}', text)
    if sep_match:
        after = text[sep_match.end():].strip()
        after = re.sub(r'^(DRAFT|ESCALATION BRIEF)\s*[:\(][^\n]*\n?', '', after, flags=re.IGNORECASE).strip()
        result["draft"] = after

    return result


# ---------------------------------------------------------------------------
# Single-issue triage (used by both CLI and chat.py)
# ---------------------------------------------------------------------------

def triage_issue_text(
    issue_text: str,
    repo_docs: dict[str, str] | None = None,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    anthropic_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    posting: bool = False,
) -> dict:
    """Triage a raw issue text string. Returns parse_output dict."""
    system = build_system_prompt(repo_docs or {}, posting=posting)
    raw = call_llm(system, f"Triage this:\n\n{issue_text}",
                   provider=provider, model=model,
                   anthropic_key=anthropic_key, ollama_host=ollama_host)
    return parse_output(raw)


# ---------------------------------------------------------------------------
# GitHub helpers
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


def _ensure_labels(repo, names: list[str]):
    existing = {lb.name.lower() for lb in repo.get_labels()}
    for name in names:
        if name not in existing:
            repo.create_label(name, _LABEL_COLORS.get(name, "ededed"))


def get_repo_docs(repo) -> dict[str, str]:
    candidates = [
        "CLAUDE.md", "README.md", "CHANGELOG.md", "ROADMAP.md",
        "docs/README.md", "docs/index.md", "docs/spec.md", "docs/roadmap.md",
        "open-issues.md",
    ]
    docs = {}
    for path in candidates:
        try:
            content = repo.get_contents(path)
            docs[path] = content.decoded_content.decode("utf-8")
        except GithubException:
            pass
    return docs


def _format_github_issue(issue) -> str:
    labels_str = ", ".join(lb.name for lb in issue.labels) if issue.labels else "none"
    return (
        f"Title: {issue.title}\n"
        f"Issue #{issue.number} — {issue.html_url}\n"
        f"Author: {issue.user.login} (external)\n"
        f"Labels already applied: {labels_str}\n"
        f"Created: {issue.created_at.strftime('%Y-%m-%d')}\n"
        f"Existing comment count: {issue.comments}\n\n"
        f"--- Body ---\n"
        f"{issue.body or '(empty body)'}\n"
    )


def _already_handled(issue, bot_login: str) -> bool:
    for comment in issue.get_comments():
        if comment.user.login == bot_login:
            return True
    return False


# ---------------------------------------------------------------------------
# Repo triage loop
# ---------------------------------------------------------------------------

def run_triage(
    repo_name: str,
    dry_run: bool = False,
    model: str = "claude-sonnet-4-6",
    provider: str = "anthropic",
    anthropic_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    progress_cb=None,
) -> list[dict]:
    """
    Triage all unhandled issues in a GitHub repo.

    progress_cb(msg: str) is called for each status update (used by chat.py SSE).
    Returns list of escalation dicts for followup.md.
    """
    gh_token = os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise RuntimeError("GITHUB_TOKEN environment variable not set.")
    if provider == "anthropic" and not (anthropic_key or os.environ.get("ANTHROPIC_API_KEY")):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

    def log(msg):
        if progress_cb:
            progress_cb(msg)
        else:
            print(msg)

    gh   = Github(gh_token)
    repo = gh.get_repo(repo_name)
    me   = gh.get_user().login

    log(f"Authenticated as: {me}")
    log(f"Targeting repo:   {repo.full_name}")
    if dry_run:
        log("DRY RUN — nothing will be posted to GitHub.")

    repo_docs     = get_repo_docs(repo)
    system_prompt = build_system_prompt(repo_docs, posting=not dry_run)

    open_issues = [i for i in repo.get_issues(state="open") if not i.pull_request]
    unprocessed = [i for i in open_issues if not _already_handled(i, me)]

    if not unprocessed:
        log("No new issues to triage.")
        _write_followup([], repo_name, dry_run)
        return []

    log(f"Found {len(unprocessed)} unprocessed issue(s).")

    escalations = []

    for issue in unprocessed:
        log(f"#{issue.number}: {issue.title}")
        raw    = call_llm(system_prompt, f"Triage this:\n\n{_format_github_issue(issue)}",
                          provider=provider, model=model,
                          anthropic_key=anthropic_key, ollama_host=ollama_host)
        parsed = parse_output(raw)

        route  = parsed["route"] or "ESCALATE"
        labels = parsed["labels"]
        draft  = parsed["draft"] or raw

        log(f"  → {route}  labels={labels}  priority={parsed['priority']}")
        _write_issue_log(issue, parsed, route, repo_name, model, provider, dry_run)

        if route == "ESCALATE":
            escalations.append({"issue": issue, "output": raw, "parsed": parsed})
            log("  → Queued for followup.md")
            continue

        if not dry_run:
            if labels:
                _ensure_labels(repo, labels)
                issue.set_labels(*labels)
            if draft:
                issue.create_comment(draft)
            if route == "CLOSE":
                issue.edit(state="closed")

    _write_followup(escalations, repo_name, dry_run)
    log(f"Done. {len(escalations)} escalation(s) written to followup.md")
    return escalations


# ---------------------------------------------------------------------------
# followup.md writer
# ---------------------------------------------------------------------------

def _write_issue_log(issue, parsed: dict, route: str, repo_name: str, model: str, provider: str, dry_run: bool):
    log_dir = SCRIPT_DIR / "GithubIssues" / "IssueLog"
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "repo":      repo_name,
        "number":    issue.number,
        "title":     issue.title,
        "url":       issue.html_url,
        "author":    issue.user.login,
        "created":   issue.created_at.strftime("%Y-%m-%d"),
        "triaged":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "category":  parsed.get("category") or parsed.get("raw", "")[:60],
        "route":     route,
        "labels":    parsed["labels"],
        "priority":  parsed["priority"],
        "draft":     parsed["draft"],
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
        "# The Maintainer — Followup Required",
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
                f"**Author:** {issue.user.login}  ",
                "",
                "### Triage output",
                "",
                "```",
                esc["output"].strip(),
                "```",
                "",
                "---",
                "",
            ]

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"followup.md written → {out}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time

    parser = argparse.ArgumentParser(description="RepoRouter — automated issue triage")
    parser.add_argument("repo", help="GitHub repo in owner/repo format")
    parser.add_argument("--dry-run",     action="store_true", help="Preview without posting")
    parser.add_argument("--provider",    default="anthropic", choices=["anthropic", "ollama"])
    parser.add_argument("--model",       default=None,
                        help="Model name (default: claude-sonnet-4-6 for anthropic, llama3.2 for ollama)")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--interval",    type=int, default=None, metavar="MINUTES",
                        help="Run continuously, checking every N minutes")
    args = parser.parse_args()

    default_model = "llama3.2" if args.provider == "ollama" else "claude-sonnet-4-6"
    kwargs = dict(
        dry_run=args.dry_run,
        model=args.model or default_model,
        provider=args.provider,
        ollama_host=args.ollama_host,
    )

    if args.interval:
        print(f"Running every {args.interval} minutes. Press Ctrl+C to stop.")
        while True:
            run_triage(args.repo, **kwargs)
            print(f"Sleeping {args.interval} minutes...")
            time.sleep(args.interval * 60)
    else:
        run_triage(args.repo, **kwargs)
