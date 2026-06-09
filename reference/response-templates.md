# reference/response-templates.md

Drafting templates for each route. These are **scaffolds, not scripts** — the operator
fills the brackets with specifics from the issue and the docs, and matches the
maintainer's voice (warm, brief, technical, no corporate filler, no over-apologizing).
Every reply names a *specific* fact (a spec section, a version, an issue number) so the
reporter can tell a human actually read it.

Drafts are for the maintainer to review and post. The operator posts nothing.

---

## Confirmed bug (external reporter)

> Thanks for the detailed report — this lines up with a real problem. The behavior you're
> seeing contradicts [spec/doc §X], which says [expected behavior]. Labeling this `bug`
> [and `good first issue` if applicable]. [If P0/P1: We'll prioritize a fix. / If P2/P3:
> It's on the list.]
>
> [If repro is strong:] Your repro is enough to work from — thank you.

Internal note (do not post): `PRIORITY: Px — reasons`. Never write the P-level publicly.

## Needs more info (no/insufficient repro)

> Thanks for flagging this. I want to dig in but can't reproduce it from here yet. Could
> you add:
> - [the specific missing thing — version, OS, exact command, full error/stack trace]
> - [a minimal sample input that triggers it, if relevant]
>
> Labeling `question` for now; I'll pick it up as soon as we can reproduce it. If we don't
> hear back in ~2 weeks I'll close it, but reopen anytime with the details.

## Works as designed

> Good question, and a reasonable thing to expect. This is actually intended behavior —
> [spec/doc §X] covers it: [why it works this way]. [If there's a setting/workaround:] You
> can get the behavior you want by [setting/flag/approach]. Closing as `invalid` (GitHub's
> label for "not a defect"), but happy to keep talking if that doesn't fit your case.

If the expectation was reasonable, add internally: *recommend a `documentation` follow-up
so the next person doesn't hit this.*

## Already fixed in a newer version

> This should be resolved as of [vX.Y] — see the changelog entry for [item]. You're on
> [their version]; could you upgrade and confirm? If it still happens on [vX.Y]+, reopen
> and I'll take another look. Labeling `question` until we confirm.

## Feature — on the roadmap

> Thanks — this is already planned. It's tracked for [vX / milestone] (see [roadmap/#issue]).
> I'll keep this labeled `enhancement` and link it to the tracking issue. Following along
> there will get you the updates.

## Feature — declined (out of scope)

> Appreciate the suggestion. This one sits outside what the project is trying to be —
> [non-goal §X] spells out why [scope rationale]. I'm going to close it as `wontfix`, but
> [if applicable:] you could get there with [plugin/extension/fork path]. Not a no to your
> use case, just a no to it living in core.

## Usage question (answer in docs)

> [Direct answer.] This is covered in [doc §X / link]. [One-line elaboration if the doc is
> terse.] Labeling `question`; closing once that's sorted — shout if it doesn't work.

## Docs gap (confirmed)

> You're right, the docs are off here. [Doc] still says [stale claim], but per
> [spec/changelog] it should be [correct claim]. Labeling `documentation` and queuing a
> fix to: [specific lines/sections to change].

## Owner-filed internal note (NOT an external reply — do not "thank" the owner)

> Internal — README diff against current spec/changelog. Likely-stale spots:
> - [README line/section] — says [X], but [spec §/changelog] now says [Y].
> - [README line/section] — references [removed/renamed thing].
> Keeping `documentation`. Confirm the list and I'll draft the patch. Not closing.

## Duplicate (no new info)

> This is the same as [#X] — closing in favor of it as `duplicate` so the discussion stays
> in one place. Follow [#X] for updates.

## Duplicate (carries NEW info)

> Closing as `duplicate` of [#X], but you added something the original didn't: [new repro/
> detail]. I've copied that over to [#X] so it isn't lost — thank you, that's useful.

(Operator also drafts the migration comment to paste on the canonical issue.)

## Spam

> [No individualized reply.] Close, label `invalid`.

## Escalation brief (private — to the maintainer, never posted)

> **ESCALATE — [security / hostile / roadmap call / spec-silent]**
> Issue: [#X — title], author [name/role].
> Why it's yours: [one line].
> What I found: [docs checked + relevant facts].
> **My recommendation: [concrete recommendation].**
> Drafts ready for each path: [Option A reply … / Option B reply …] — pick one and I'll
> finalize.

The brief always ends with a recommendation. Never escalate with an open "what do you
want to do?"
