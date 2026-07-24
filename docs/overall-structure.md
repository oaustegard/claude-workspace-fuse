# muninn-utilities — documentation structure

## Audiences

**Primary:** An engineer building their own persistent agent
A developer who has read about or seen Muninn and wants to build a similar
long-lived agent of their own. They are studying this codebase to understand
and adapt its patterns — persistent memory over an HTTP database, graph-based
task orchestration, distributing accumulated memory as a skill. They read for
*why* a thing is built the way it is, so they can reproduce the idea in their
own stack, not to call this exact API.

> Design constraint for this audience: muninn-utilities is Muninn-specific
> (hardcoded handles, hub-spoke assumptions, Turso credentials). The docs must
> abstract the transferable pattern from Muninn's plumbing, and mark explicitly
> what generalizes versus what is Muninn-only. The borrower should never have to
> guess which lines are essential to the idea and which are local wiring.

**Secondary:**
- Maintainer — extends or modifies the toolkit. Tie-breaker: when the borrower's pattern-level "why" leaves "but how would I change this?" unclear, show the extension seam.
- Workflow author — composes the utilities into routines and tasks. Tie-breaker: keeps Reference carrying real call-contracts, not only architecture.

## Primary use case (Getting Started)

**Building a minimal persistent-memory loop.** Stand up `remember` → `recall`
→ `supersede` over Turso: store typed, tagged memories; retrieve them by text
and tag; revise them without destroying history. This is the irreducible core
the rest of the system assumes, and the single most transferable idea for a
borrower. A reader who works through it can stop there and still hold a usable
mental model of how the agent remembers.

## Getting Started outline

Steps named by the reader's action. Each lists the components it touches.

1. **Connecting to a memory store over HTTP** — the Turso HTTP layer and the
   minimal config needed to reach it; why the store is a remote DB an ephemeral
   process talks to, not a local file. *(turso.py, config connection)*
2. **Storing your first memory** — `remember`: the required type, plus tags and
   priority; the write-then-confirm return shape. *(memory.remember, the
   type/tag/priority model)*
3. **Recalling memories by text and tag** — `recall`: full-text query vs. tag
   filters, `tag_mode`, result shape. *(memory.recall, MemoryResult)*
4. **Revising what you know without deleting it** — `supersede`: why an update
   is a new memory that points back, not an in-place edit; soft-delete via
   `forget`. *(memory.supersede, memory.forget)*
5. **Reading a memory's history** — `get_chain`: following the supersession
   trail, and why preserving it matters for an agent that reasons over its own
   past. *(memory.get_chain)*

## Diving Deeper topics

Candidates with intent and coverage. The author selects which get written; not
every candidate must be.

- **Surviving cold starts by booting from stored state** — *mental-model +
  auxiliary-use-case.* How a fresh, empty process reconstructs working context
  (profile, operating instructions, reminders, open tasks) from the store. The
  borrower's central problem; flag the Muninn-specific path-wiring as local.
  *(boot.py, config, memory, task)*
- **Orchestrating a utility as a flowing graph** — *mental-model +
  alternative-path.* Why each task utility is a dependency graph, not a linear
  script — parallel legs, structural validation, clean skips. Uses one real
  utility as the worked example. *(flowing, e.g. bsky_card as exemplar)*
- **Shaping retrieval with search, tags, and FTS** — *customization +
  mental-model.* Tuning what comes back: FTS query vs. tag retrieval, batched
  recall, time-bounded recall, proactive hints. Storage's harder other half.
  *(recall, recall_batch, recall_since/between, recall_hints)*
- **Curating a growing memory store** — *customization + mental-model.* The
  lifecycle that prevents rot: consolidation, duplicate/staleness curation,
  age- and priority-based pruning, strengthen/weaken. What you reach for once
  the loop runs for weeks. *(consolidate, curate, prune_*, strengthen, weaken)*
- **Storing operating instructions as editable config** — *mental-model +
  customization.* How the agent's own behavior lives as queryable config (ops
  vs. profile, boot-load, rule drift classification) — behavior as data.
  *(config.config_get/set, set_rule)*
- **Enforcing multi-step work with tracked tasks** — *customization +
  mental-model.* Structural discipline for long jobs: the task checklist and
  the recall gate that blocks analysis before retrieval. *(task.py: task, Task,
  recall_gate)*
- **Distributing accumulated memory as a shareable skill** — *auxiliary-use-case
  + mental-model.* The snapshot pipeline (pull → filter/redact → cluster →
  compose → build) that turns a live memory store into a portable claude-skill.
  Advanced; presupposes the loop exists. *(snapshot/ package)*
- **Managing a hub of spoke repositories** — *auxiliary-use-case.* The
  hub-spoke registry an agent uses to track its own repos. Heavily
  Muninn-shaped; lowest borrower priority — author may cut or demote to Ref.
  *(spokes.py)*

## Reference modules

Pure API spec (signature + 1–2 sentence purpose; promote on the kickback rule).
Scoped to the reusable subsystems the borrower would lift — not one file per
Muninn-specific utility.

- `remembering/scripts/memory` — remember, recall (+ since/between/batch),
  supersede, forget, strengthen/weaken, get_chain, consolidate, curate, prune_*
- `remembering/scripts/config` — config_get/set, set_rule, config_list,
  boot_load/priority setters, delete
- `remembering/scripts/boot` — boot, journal, sessions, handoff, export/import
- `remembering/scripts/task` — task, Task, task_resume, recall_gate
- `remembering/scripts/result` — MemoryResult, MemoryResultList
- `remembering/scripts/spokes` — spokes_list/status/add/remove/discover
- `remembering/scripts/hints` — recall_hints
- `snapshot/` — pull, filter, cluster, compose_instruction, kb, build
  (one section; the pipeline is the unit)
- **Example applications (catalog):** the 13 `muninn_utils` orchestrators
  (blog_publish, bsky_card, perch_*, whtwnd, remind, verify_patch,
  zeitgeist_delta, …) listed as a single catalog with one-line purposes — they
  are Muninn-specific *instances* of the flowing pattern, not core API for a
  borrower. One is documented in full in the flowing Diving Deeper topic.
