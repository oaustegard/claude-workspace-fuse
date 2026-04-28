# claude.ai → CCotw handoff flow

Reference for Muninn (on claude.ai) and CCotw (Claude Code on the Web)
sessions. Describes how a planning conversation on claude.ai dispatches
executable work to CCotw via a GitHub pull request, and the conventions
both sides rely on.

---

## TL;DR

- Muninn (claude.ai) opens a PR titled `Handoff: <short task>` on
  `oaustegard/claude-workspace`, branch `claude/*`, with the full task
  spec in the PR body.
- A GitHub Routine subscribed to `pull_request.opened` matches the
  `Handoff:` title prefix and boots a CCotw session with the PR branch
  checked out.
- CCotw executes the task, commits back to the same branch, and
  (optionally) leaves a PR comment. Review and merge happen normally.

---

## Why this flow exists

CCotw sessions are effectively blind to anything uploaded to claude.ai:

- **Images** arrive inline as base64 in the prompt — technically
  present, but wasteful of context and opaque to tools.
- **Arbitrary files** (PDFs, CSVs, transcripts, datasets, zips) don't
  transfer at all. There is no shared filesystem between the claude.ai
  conversation and the CCotw container.

Muninn on claude.ai, by contrast, has full bash access inside the
conversation and can read `/mnt/user-data/uploads/`, fetch URLs, run
analyses, and generally preprocess arbitrary context. That asymmetry
is the whole reason for a handoff step: the side that can see the
inputs composes the spec; the side that can write code executes it.

The old pattern was Muninn-files-issue → human-invokes-CCotw. Issues
don't fire Routines (see "Why PRs, not issues" below), so each handoff
needed Oskar in the loop. PRs do fire Routines, so the new flow closes
that gap.

---

## Division of labor

### Muninn (claude.ai) — planner

- Reads uploaded artifacts in the claude.ai conversation.
- Decides what needs doing and composes the task spec.
- Opens a PR with:
  - **Title:** `Handoff: <short description>`
  - **Branch:** `claude/<slug>` off `main`
  - **Body:** the full spec — goals, context, constraints, acceptance
    criteria. Assume CCotw reads nothing but the PR body and diff.
- Optionally commits long or structured context as `.requests/*.md`
  files on the branch when the PR body is too cramped.

### CCotw — executor

- Boots with the PR branch checked out and the Muninn container layer
  applied (skills, Python deps, tools).
- Reads the PR body and any `.requests/*.md`; treats both as the task.
- Writes, tests, and commits code on the same branch. Never pushes to
  `main` directly.
- Deletes consumed `.requests/*.md` in the same or a follow-up commit
  if the spec calls for it (scratchpad, not source).
- Leaves a PR comment when useful — especially on the first handoff of
  a flow, to confirm trigger→pickup latency and that the body was
  readable.

### Oskar — reviewer

- Reviews the resulting PR normally. Merges when satisfied.
- Squash-merge is the safer default if `.requests/` files are still on
  the branch, so transient scratch doesn't land on `main`.

---

## How the trigger works

- **Routine name:** `Handoff from Claude.ai` (configured under
  Muninn's account on claude.ai).
- **Repo scope:** `oaustegard/claude-workspace` only.
- **GitHub event:** `pull_request.opened`.
- **Discriminator:** PR title starts with `Handoff:`.
- **Branch convention:** head branch matches `claude/*`.

When those conditions line up, the Routine boots a CCotw session with
that PR's branch checked out and a `<github-trigger-context>` tag in
the opening prompt pointing at the PR number, head SHA, and branches.

### Why title, not label or assignee

Among GitHub webhook events, only `pull_request.*` and `release.*`
fire Routines in the current research preview. `issues.opened`,
`issue_comment`, and `pull_request_review_comment` don't. That rules
out:

- Labels applied post-creation (no `pull_request.labeled` trigger).
- Assignees added post-creation (same reason).
- Comment-driven re-invocation (`issue_comment` doesn't fire).

What remains is: open the PR with the right signal already present.
Title prefix is the lowest-friction option Muninn controls at PR
creation time — no label vocabulary to sync, no assignee permissions
to manage.

### Why PRs, not issues

Issues look like a cleaner fit for "here is a task" but issues don't
fire Routines. PRs do, and as a bonus they give the work a branch to
commit back to — no second round-trip to create one.

### Why `claude/*` branches

`claude/*` matches CCotw's default head-branch push rail. Branch
names like `handoff/*` or `muninn/*` would satisfy the Routine
trigger but would need CCotw's push permissions to be loosened.
Sticking to `claude/*` keeps the permission surface unchanged.

---

## Conventions

### Title

```
Handoff: <imperative short description>
```

The prefix is load-bearing (it's the Routine discriminator). Keep the
rest under ~70 chars so it renders in the PR list.

### Branch

```
claude/<kebab-slug>
```

Short, descriptive, no trailing counter unless multiple handoffs on
the same topic are in flight. Example: `claude/handoff-001`,
`claude/eml-sr-demo-script`.

### PR body = task spec

Write for a cold reader. CCotw sees no claude.ai context and no prior
turns. Good structure:

1. **Task** — one sentence, imperative.
2. **Why / context** — links, prior art, constraints.
3. **Acceptance criteria** — checkbox list CCotw can self-verify
   against before pushing.
4. **Sharp edges / non-goals** — things not to do.

### `.requests/*.md` (optional)

Use when spec material is long, structured, or binary-adjacent
(transcripts, decoded attachments, dataset samples). Conventions:

- Path: `.requests/<slug>.md` on the PR branch only.
- Text only. Binaries go elsewhere (release assets, external URL,
  Git LFS).
- Treated as scratchpad: CCotw deletes consumed request files, or
  squash-merge drops them at merge time.

### Completion signal

- Push commits to the PR branch — that's the primary completion
  signal.
- Optionally add a PR comment summarizing what was done and flagging
  anything Muninn should fix in the spec or Routine config next turn.
- Do not self-merge. Oskar reviews.

---

## Sharp edges

### Rate limits

Routines have per-account hourly caps on GitHub webhook dispatches in
the research preview. Ten handoffs in a row will hit the ceiling and
silently stop firing. Batch related work into one PR where possible,
or space dispatches out.

### No comment-driven iteration

The Routine fires on `pull_request.opened`, not on subsequent
comments or reviews. Once CCotw has taken its turn, you cannot nudge
it by commenting. Options:

- Edit the PR body (for reference, not re-trigger) and open a
  follow-up PR with the revised spec.
- Close and reopen the PR — **does not re-fire** the Routine; the
  event is `reopened`, not `opened`.
- Open a new handoff PR that references the prior one.

### Binary attachments

Committing binaries (images, PDFs, zips, model weights) pollutes
history on a repo that's mostly config and docs. For anything over a
few hundred KB, prefer:

- A GitHub release asset on `oaustegard/claude-container-layers` (or
  a task-appropriate repo) linked from the PR body.
- A public URL Muninn has already published the artifact to.
- Git LFS, if the artifact genuinely belongs in the repo long-term.

`.requests/` is text-only by convention.

### Squash vs. merge commit

If `.requests/*.md` files are still on the branch at merge time,
squash-merge so they don't land on `main`. If CCotw has already
deleted them in a follow-up commit, either merge strategy is fine.

### Branch naming drift

`claude/*` is the safe default because it matches CCotw's push rail.
If you deviate (`handoff/*`, `muninn/*`, etc.) the Routine may still
fire but CCotw may not be able to push back without loosening
permissions. Don't deviate without a reason.

### Wrong-repo dispatches

The Routine is scoped to `oaustegard/claude-workspace`. Opening a
`Handoff:` PR in a spoke repo (e.g. `eml-sr`) will not trigger
CCotw. For spoke work, the handoff PR still lives on
`claude-workspace`; CCotw then clones the spoke under `.spokes/`
per the hub's `CLAUDE.md`.

### First-run signals

On the first handoff after any change to the Routine config, branch
rules, or title convention, ask CCotw to leave a PR comment noting:

- Whether the trigger fired at all (presence of
  `<github-trigger-context>` in the opening prompt).
- Whether the PR body was readable end-to-end (no truncation).
- Whether the branch was pre-checked-out as expected.

These are the three failure modes worth instrumenting; everything
else surfaces as normal CCotw errors.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No CCotw session starts | Title missing `Handoff:` prefix, or event was `reopened`/`edited`, not `opened` | Close and re-open as a new PR; do not rely on edits |
| CCotw session starts but can't push | Branch is not `claude/*` | Rename branch, or open a fresh PR on `claude/*` |
| CCotw sees an empty or truncated spec | PR body exceeded GitHub's size limit | Move bulk to `.requests/*.md` on the branch |
| Trigger fires on unrelated PRs | Another PR's title accidentally starts with `Handoff:` | Rename the other PR; the prefix is reserved |
| Silent no-fire after many handoffs | Routine rate limit | Wait out the window; batch future handoffs |

---

## Meta

This flow is new as of 2026-04. The first end-to-end exercise was
PR #26 on this repo (`claude/handoff-001`), which replaced a stub
version of this file with the content you're reading. If something
about the flow breaks in a way this doc didn't predict, note it in a
PR comment so the next iteration can fold the fix in.
