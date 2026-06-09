# reference/security-handling.md

How the operator handles anything that looks like a security vulnerability. This is the
one path where getting it wrong causes real-world harm, so the rules are absolute.

## The core rule

**A security report is never handled in public.** The operator escalates it privately,
unlabeled, and drafts nothing that confirms, denies, or describes the vulnerability in a
public-facing comment.

## What counts as security (detect at Step 2, act at Step 3)

Treat as security if the issue mentions or implies any of:
- vulnerability, exploit, CVE, advisory
- authentication/authorization bypass, privilege escalation
- remote code execution (RCE), command/SQL/template injection, XSS, SSRF, path traversal
- deserialization, secrets/credentials leaked or hardcoded, exposed tokens
- denial of service via crafted input
- "I think this is a security issue" — take the reporter's word and treat it as one

When in doubt, **treat it as security.** A false positive costs one escalation. A false
negative can publish an exploit.

## What the operator does

1. **Stop the normal pipeline.** Do not fetch a spec to "verify" it. Do not categorize it
   as a regular bug. Security short-circuits at Step 3.
2. **Apply no label.** No `security`, no `bug`, nothing. A label is a public signal that
   says "exploitable bug here, not yet fixed."
3. **Draft no public reply.** Not even "thanks." A public acknowledgement confirms the
   report is credible.
4. **Escalate privately** with this brief:

   > **ESCALATE — SECURITY (handle privately)**
   > Issue: [#X], author [name/role], filed [public/private].
   > Claim: [one-line, factual, no exploit detail beyond what's already posted].
   > Exposure: [if filed publicly, note that it's ALREADY public — time-sensitive].
   > **Recommendation:** [move to a private security advisory / request CVE / contact
   > reporter privately / if already public: assess and patch on an accelerated timeline].
   > Suggested private reply to reporter: "Thanks for the responsible report — let's move
   > this to a private channel: [security policy contact / GitHub Security Advisory]."

5. **If the report is already public** (someone filed an exploit in the open), flag it as
   **time-sensitive** in the brief. The operator still does not add detail or confirm
   severity publicly — but the maintainer needs to know the clock is running.

## What the operator must never do

- Never confirm or deny that the vulnerability is real, in public.
- Never post reproduction steps, severity, or affected versions in a public comment.
- Never apply a label that flags the issue as security-related.
- Never close it as `invalid` to "make it disappear" — that's still a public signal and
  may anger a good-faith reporter. Escalate; let the human decide.

## Pointer for the maintainer

If the project has a `SECURITY.md` or a published disclosure policy, the operator surfaces
its contact path in the brief. If it has none, the operator recommends creating one and
suggests GitHub's private Security Advisories as the default private channel.
