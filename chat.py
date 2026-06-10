#!/usr/bin/env python3
"""
RepoRouter — chat interface.

Usage:
    python chat.py
    python chat.py --port 5050

Then open http://localhost:5000 in your browser.

Two modes available in the UI:
  • Paste an issue  — triage a single issue; returns the decision instantly
  • Triage a repo   — pull all new issues from GitHub and process them live

Provider support: Anthropic (cloud) or Ollama (local).
"""

import json
import queue
import threading
import argparse
from pathlib import Path

from flask import Flask, Response, request, jsonify, stream_with_context

import triage as core

app = Flask(__name__)
SCRIPT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# HTML — single-file, no templates directory required
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RepoRouter</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #f5f5f7;
    --surface:   #ffffff;
    --sidebar:   #1c1c2e;
    --sidebar-t: #c8c8d8;
    --accent:    #4f8ef7;
    --accent-h:  #3a78e8;
    --text:      #1a1a1a;
    --sub:       #666;
    --border:    #e0e0e0;
    --red:       #e53935;
    --green:     #43a047;
    --amber:     #fb8c00;
    --mono:      'SF Mono','Fira Code','Cascadia Code',monospace;
    --radius:    10px;
  }

  html, body { height: 100%; font-family: system-ui, -apple-system, sans-serif; }

  body {
    display: flex;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
  }

  /* ── Sidebar ── */
  #sidebar {
    width: 280px;
    min-width: 280px;
    background: var(--sidebar);
    color: var(--sidebar-t);
    display: flex;
    flex-direction: column;
    padding: 24px 18px;
    gap: 18px;
    overflow-y: auto;
  }
  #sidebar h1 { font-size: 1.1rem; color: #fff; letter-spacing: .03em; }
  #sidebar .tagline { font-size: .78rem; color: #8888aa; line-height: 1.5; }

  .s-section { display: flex; flex-direction: column; gap: 8px; }
  .s-label { font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; color: #7777aa; }

  .toggle-row { display: flex; gap: 6px; }
  .toggle-btn {
    flex: 1; padding: 7px 0; border: none; border-radius: 6px;
    background: #2c2c44; color: var(--sidebar-t);
    cursor: pointer; font-size: .82rem; transition: background .15s;
  }
  .toggle-btn.active { background: var(--accent); color: #fff; }

  #sidebar input[type=text], #sidebar input[type=password] {
    width: 100%; padding: 7px 10px; border-radius: 6px;
    border: 1px solid #3a3a55; background: #23233a; color: #ddd;
    font-size: .82rem; outline: none;
  }
  #sidebar input:focus { border-color: var(--accent); }

  .s-hint { font-size: .72rem; color: #5555aa; line-height: 1.4; }

  #ollama-section, #anthropic-section { display: flex; flex-direction: column; gap: 8px; }

  #fetch-models-btn {
    padding: 5px 10px; border: none; border-radius: 6px;
    background: #2c2c44; color: var(--sidebar-t);
    cursor: pointer; font-size: .78rem;
  }
  #fetch-models-btn:hover { background: #3a3a55; }

  #model-list { display: none; flex-direction: column; gap: 4px; margin-top: 4px; }
  #model-list button {
    text-align: left; padding: 5px 8px; border: none; border-radius: 5px;
    background: #23233a; color: #bbb; cursor: pointer; font-size: .78rem;
    font-family: var(--mono);
  }
  #model-list button:hover { background: #2c2c44; color: #fff; }

  /* ── Main chat area ── */
  #main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .msg { display: flex; flex-direction: column; max-width: 86%; }
  .msg.user { align-self: flex-end; align-items: flex-end; }
  .msg.bot  { align-self: flex-start; align-items: flex-start; }

  .bubble {
    padding: 12px 16px;
    border-radius: var(--radius);
    font-size: .9rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .user .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 2px; }
  .bot  .bubble {
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border);
    border-bottom-left-radius: 2px;
    font-family: var(--mono);
    font-size: .82rem;
  }

  .msg-meta {
    font-size: .7rem; color: var(--sub); margin-top: 4px;
    display: flex; gap: 10px; align-items: center;
  }
  .copy-btn {
    background: none; border: none; cursor: pointer;
    color: var(--accent); font-size: .7rem; padding: 0;
  }
  .copy-btn:hover { text-decoration: underline; }

  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 20px;
    font-size: .7rem; font-weight: 600; letter-spacing: .04em;
  }
  .badge.respond  { background: #e8f5e9; color: var(--green); }
  .badge.close    { background: #ffebee; color: var(--red); }
  .badge.escalate { background: #fff3e0; color: var(--amber); }

  .spinner {
    display: flex; align-items: center; gap: 10px;
    color: var(--sub); font-size: .85rem; padding: 12px 0;
  }
  .spinner::before {
    content: '';
    width: 16px; height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Input bar ── */
  #input-bar {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px 20px;
    border-top: 1px solid var(--border);
    background: var(--surface);
  }
  #input-bar-top { display: flex; gap: 8px; align-items: flex-end; }
  #issue-input {
    flex: 1;
    resize: vertical;
    min-height: 72px;
    max-height: 260px;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: .88rem;
    font-family: inherit;
    outline: none;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  #issue-input:focus { border-color: var(--accent); }
  #issue-input::placeholder { color: #aaa; }

  .btn-primary, .btn-secondary {
    padding: 10px 18px; border: none; border-radius: var(--radius);
    cursor: pointer; font-size: .88rem; font-weight: 600;
    white-space: nowrap; transition: background .15s;
  }
  .btn-primary   { background: var(--accent); color: #fff; }
  .btn-primary:hover   { background: var(--accent-h); }
  .btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
  .btn-secondary:hover { background: var(--border); }

  #repo-row { display: flex; gap: 8px; align-items: center; }
  #repo-input {
    flex: 1; padding: 8px 12px; border: 1px solid var(--border);
    border-radius: var(--radius); font-size: .88rem; background: var(--bg);
    color: var(--text); outline: none;
  }
  #repo-input:focus { border-color: var(--accent); }
  #repo-input::placeholder { color: #aaa; }

  .dry-run-label {
    display: flex; align-items: center; gap: 6px;
    font-size: .8rem; color: var(--sub); cursor: pointer;
  }

  .progress-line {
    font-family: var(--mono); font-size: .8rem;
    color: var(--sub); padding: 2px 0;
  }
  .progress-line.done { color: var(--green); }

  #welcome {
    text-align: center; color: var(--sub);
    margin: auto; max-width: 420px;
    display: flex; flex-direction: column; gap: 12px;
    padding: 40px 20px;
  }
  #welcome h2 { font-size: 1.3rem; color: var(--text); }
  #welcome p  { font-size: .88rem; line-height: 1.6; }
  #welcome code {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 4px; padding: 1px 5px;
    font-family: var(--mono); font-size: .82rem;
  }
</style>
</head>
<body>

<div id="sidebar">
  <div>
    <h1>RepoRouter</h1>
    <p class="tagline">AI issue triage operator</p>
  </div>

  <div class="s-section">
    <div class="s-label">Provider</div>
    <div class="toggle-row">
      <button class="toggle-btn active" id="btn-anthropic" onclick="setProvider('anthropic')">Anthropic</button>
      <button class="toggle-btn"        id="btn-ollama"    onclick="setProvider('ollama')">Ollama</button>
    </div>
  </div>

  <div class="s-section" id="anthropic-section">
    <div class="s-label">Anthropic API key</div>
    <input type="password" id="anthropic-key" placeholder="sk-ant-…" autocomplete="off">
    <div class="s-label" style="margin-top:4px">Model</div>
    <input type="text" id="anthropic-model" value="claude-sonnet-4-6">
  </div>

  <div class="s-section" id="ollama-section" style="display:none">
    <div class="s-label">Ollama host</div>
    <input type="text" id="ollama-host" value="http://localhost:11434">
    <div class="s-label" style="margin-top:4px">Model</div>
    <input type="text" id="ollama-model" value="qwen3:8b">
    <button id="fetch-models-btn" onclick="fetchOllamaModels()">↻ fetch available models</button>
    <div id="model-list"></div>
  </div>

  <div class="s-section">
    <div class="s-label">GitHub token</div>
    <input type="password" id="github-token" placeholder="ghp_… (repo triage only)" autocomplete="off">
    <div class="s-hint">Required for "Triage repo". Needs repo scope.</div>
  </div>
</div>

<div id="main">
  <div id="messages">
    <div id="welcome">
      <h2>Ready to triage</h2>
      <p>Paste a GitHub issue in the box below and click <strong>Triage Issue</strong> for an instant decision.</p>
      <p>Or enter a repo name (<code>owner/repo</code>) and click <strong>Triage Repo</strong> to process all new issues live.</p>
    </div>
  </div>

  <div id="input-bar">
    <div id="input-bar-top">
      <textarea id="issue-input" placeholder="Paste a GitHub issue here — include title, author, body, labels, and activity log…"></textarea>
      <button class="btn-primary" onclick="triageIssue()">Triage Issue</button>
    </div>
    <div id="repo-row">
      <input type="text" id="repo-input" placeholder="owner/repo">
      <label class="dry-run-label">
        <input type="checkbox" id="dry-run-check"> dry run
      </label>
      <button class="btn-secondary" onclick="triageRepo()">Triage Repo</button>
    </div>
  </div>
</div>

<script>
let provider = 'anthropic';

function setProvider(p) {
  provider = p;
  document.getElementById('btn-anthropic').classList.toggle('active', p === 'anthropic');
  document.getElementById('btn-ollama').classList.toggle('active', p === 'ollama');
  document.getElementById('anthropic-section').style.display = p === 'anthropic' ? '' : 'none';
  document.getElementById('ollama-section').style.display    = p === 'ollama'    ? '' : 'none';
}

function getSettings() {
  return {
    provider,
    model:        provider === 'anthropic'
                    ? document.getElementById('anthropic-model').value.trim()
                    : document.getElementById('ollama-model').value.trim(),
    anthropic_key: document.getElementById('anthropic-key').value.trim(),
    ollama_host:   document.getElementById('ollama-host').value.trim(),
    github_token:  document.getElementById('github-token').value.trim(),
  };
}

async function fetchOllamaModels() {
  const host = document.getElementById('ollama-host').value.trim();
  const btn  = document.getElementById('fetch-models-btn');
  btn.textContent = 'fetching…';
  try {
    const r = await fetch(`/api/ollama/models?host=${encodeURIComponent(host)}`);
    const d = await r.json();
    const list = document.getElementById('model-list');
    list.innerHTML = '';
    if (!d.models.length) { list.innerHTML = '<span style="color:#777;font-size:.78rem">No models found</span>'; }
    d.models.forEach(m => {
      const b = document.createElement('button');
      b.textContent = m;
      b.onclick = () => {
        document.getElementById('ollama-model').value = m;
        list.style.display = 'none';
      };
      list.appendChild(b);
    });
    list.style.display = 'flex';
  } catch(e) {
    alert('Could not reach Ollama. Is it running?');
  }
  btn.textContent = '↻ fetch available models';
}

// ── Message rendering ──

function appendUserMsg(text) {
  hideWelcome();
  const preview = text.length > 300 ? text.slice(0, 300) + '…' : text;
  const el = document.createElement('div');
  el.className = 'msg user';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = preview;
  el.appendChild(bubble);
  messages().appendChild(el);
  scrollBottom();
  return el;
}

function appendSpinner(label) {
  const el = document.createElement('div');
  el.className = 'spinner';
  el.textContent = label;
  messages().appendChild(el);
  scrollBottom();
  return el;
}

function appendBotMsg(raw, parsed) {
  const el = document.createElement('div');
  el.className = 'msg bot';
  const route  = (parsed.route || 'ESCALATE').toLowerCase();
  const labels = (parsed.labels || []).map(l => `<code>${escHtml(l)}</code>`).join(' ');
  const header = `<div style="margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <span class="badge ${route}">${route.toUpperCase()}</span>
    ${labels}
    ${parsed.priority && parsed.priority !== 'n/a' ? `<span style="font-size:.72rem;color:var(--sub)">${escHtml(parsed.priority)}</span>` : ''}
  </div>`;
  const pre = document.createElement('pre');
  pre.style.cssText = 'white-space:pre-wrap;word-break:break-word;margin:0';
  pre.textContent = raw;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = header;
  bubble.appendChild(pre);
  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.innerHTML = `<button class="copy-btn" onclick="copyText(this)">copy</button>`;
  meta.querySelector('.copy-btn')._raw = raw;
  el.appendChild(bubble);
  el.appendChild(meta);
  messages().appendChild(el);
  scrollBottom();
}

function appendProgress(text, done = false) {
  const el = document.createElement('div');
  el.className = 'progress-line' + (done ? ' done' : '');
  el.textContent = text;
  messages().appendChild(el);
  scrollBottom();
  return el;
}

function copyText(btn) {
  navigator.clipboard.writeText(btn._raw || btn.closest('.msg').querySelector('pre').textContent);
  btn.textContent = 'copied!';
  setTimeout(() => btn.textContent = 'copy', 1500);
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function messages() { return document.getElementById('messages'); }
function scrollBottom() { const m = messages(); m.scrollTop = m.scrollHeight; }
function hideWelcome() { const w = document.getElementById('welcome'); if (w) w.remove(); }

// ── Triage issue ──

async function triageIssue() {
  const text = document.getElementById('issue-input').value.trim();
  if (!text) { alert('Paste an issue first.'); return; }
  const s = getSettings();
  if (s.provider === 'anthropic' && !s.anthropic_key) { alert('Enter your Anthropic API key in the sidebar.'); return; }

  appendUserMsg(text);
  document.getElementById('issue-input').value = '';
  const spin = appendSpinner('Triaging…');

  try {
    const r = await fetch('/api/triage/issue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ issue_text: text, ...s }),
    });
    const d = await r.json();
    spin.remove();
    if (d.error) { appendProgress('Error: ' + d.error, false); return; }
    appendBotMsg(d.raw, d);
  } catch(e) {
    spin.remove();
    appendProgress('Error: ' + e.message);
  }
}

// ── Triage repo (SSE) ──

function triageRepo() {
  const repo = document.getElementById('repo-input').value.trim();
  if (!repo) { alert('Enter a repo name (owner/repo).'); return; }
  const s        = getSettings();
  const dry_run  = document.getElementById('dry-run-check').checked;
  if (!document.getElementById('github-token').value.trim()) {
    alert('Enter your GitHub token in the sidebar.'); return;
  }
  if (s.provider === 'anthropic' && !s.anthropic_key) { alert('Enter your Anthropic API key in the sidebar.'); return; }

  hideWelcome();
  appendProgress(`Triaging ${repo}${dry_run ? ' (dry run)' : ''}…`);

  const params = new URLSearchParams({
    repo, dry_run: dry_run ? '1' : '0',
    ...s,
    github_token: document.getElementById('github-token').value.trim(),
  });

  const es = new EventSource(`/api/triage/repo?${params}`);

  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.type === 'log') {
      appendProgress(d.msg);
    } else if (d.type === 'result') {
      appendBotMsg(d.raw, d.parsed);
    } else if (d.type === 'done') {
      appendProgress(`✓ Done. ${d.escalations} escalation(s) written to followup.md`, true);
      es.close();
    } else if (d.type === 'error') {
      appendProgress('Error: ' + d.msg);
      es.close();
    }
  };
  es.onerror = () => {
    appendProgress('Connection lost.');
    es.close();
  };
}

// Enter key in textarea = submit (shift+enter for newline)
document.getElementById('issue-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); triageIssue(); }
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return _HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/triage/issue", methods=["POST"])
def api_triage_issue():
    data         = request.get_json(force=True)
    issue_text   = data.get("issue_text", "").strip()
    provider     = data.get("provider", "anthropic")
    model        = data.get("model", "claude-sonnet-4-6")
    anthropic_key = data.get("anthropic_key") or None
    ollama_host  = data.get("ollama_host", "http://localhost:11434")

    if not issue_text:
        return jsonify({"error": "issue_text is required"}), 400

    try:
        result = core.triage_issue_text(
            issue_text,
            repo_docs={},
            provider=provider,
            model=model,
            anthropic_key=anthropic_key,
            ollama_host=ollama_host,
            posting=False,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/triage/repo")
def api_triage_repo_stream():
    repo_name    = request.args.get("repo", "").strip()
    dry_run      = request.args.get("dry_run", "0") == "1"
    provider     = request.args.get("provider", "anthropic")
    model        = request.args.get("model", "claude-sonnet-4-6")
    anthropic_key = request.args.get("anthropic_key") or None
    ollama_host  = request.args.get("ollama_host", "http://localhost:11434")
    github_token = request.args.get("github_token") or None

    if not repo_name:
        return jsonify({"error": "repo is required"}), 400

    q: queue.Queue = queue.Queue()

    def _progress(msg: str):
        q.put({"type": "log", "msg": msg})

    def _worker():
        import os
        # Allow per-request token override
        original_gh  = os.environ.get("GITHUB_TOKEN")
        original_ant = os.environ.get("ANTHROPIC_API_KEY")
        if github_token:
            os.environ["GITHUB_TOKEN"] = github_token
        if anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        try:
            # All triage logic lives in triage.run_triage — this worker only
            # forwards its progress and per-issue results onto the SSE queue.
            def _result(issue, parsed):
                q.put({"type": "result", "raw": parsed.get("raw", ""), "parsed": parsed})

            escalations = core.run_triage(
                repo_name,
                dry_run=dry_run,
                provider=provider,
                model=model,
                anthropic_key=anthropic_key,
                ollama_host=ollama_host,
                progress_cb=_progress,
                result_cb=_result,
            )
            q.put({"type": "done", "escalations": len(escalations)})
        except Exception as exc:
            q.put({"type": "error", "msg": str(exc)})
        finally:
            if original_gh is not None:
                os.environ["GITHUB_TOKEN"] = original_gh
            elif "GITHUB_TOKEN" in os.environ and github_token:
                del os.environ["GITHUB_TOKEN"]
            if original_ant is not None:
                os.environ["ANTHROPIC_API_KEY"] = original_ant
            elif "ANTHROPIC_API_KEY" in os.environ and anthropic_key:
                del os.environ["ANTHROPIC_API_KEY"]

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    @stream_with_context
    def _stream():
        while True:
            try:
                item = q.get(timeout=120)
                yield f"data: {json.dumps(item)}\n\n"
                if item["type"] in ("done", "error"):
                    break
            except queue.Empty:
                yield "data: {\"type\":\"error\",\"msg\":\"Timed out\"}\n\n"
                break

    return Response(_stream(), content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/ollama/models")
def api_ollama_models():
    host   = request.args.get("host", "http://localhost:11434")
    models = core.list_ollama_models(host)
    return jsonify({"models": models})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoRouter — chat interface")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    print(f"RepoRouter chat → http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
