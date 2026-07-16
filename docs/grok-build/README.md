# grok-build inventory — xAI's terminal coding agent

Inventory of [xai-org/grok-build](https://github.com/xai-org/grok-build)
(snapshot 2026-07-16, `main`, 2,734 files / ~12.5k symbols excluding vendored
`third_party/`). Grok Build is SpaceXAI's Rust CLI/TUI coding agent — their
Claude Code analog — synced periodically from their monorepo. This directory
holds the synthesis plus four cluster deep-dives with file/line references:

| Report | Cluster | Crates |
|---|---|---|
| [runtime.md](runtime.md) | Agent runtime | xai-grok-shell, -agent, xai-acp-lib, xai-chat-state, tool-protocol/runtime |
| [tools.md](tools.md) | Tools + workspace | xai-grok-tools, -workspace, xai-fast-worktree, xai-hunk-tracker, -sandbox, ptyctl |
| [tui.md](tui.md) | TUI | xai-grok-pager(+render/minimal), ratatui forks, -markdown, -mermaid |
| [context.md](context.md) | Context + extensibility | xai-grok-memory, -compaction, xai-codebase-graph, -mcp, -hooks, -config, -plugin-marketplace |

## The headline finding: Claude Code compatibility is a design goal

Grok Build deliberately ingests Claude Code's configuration surface so a repo
set up for Claude Code "just works" under `grok`:

- **Reads `.claude/settings.json` directly** — permission mode, env, and the
  same allow/deny/ask rule grammar (`xai-grok-workspace/src/permission/claude_settings.rs`, `rules.rs`)
- **Hook config is wire-compatible with Claude Code's** hooks schema, with a
  superset event list (`SessionStart/End`, `Pre/PostToolUse`, `PreCompact`,
  `SubagentStart/Stop`, ...) plus Cursor-name compat parsing (`xai-grok-hooks/src/{config,event}.rs`)
- **Plugin marketplace falls back to `.claude-plugin/plugin-index.json`**
  (`xai-grok-plugin-marketplace/src/catalog.rs`), and skills support
  `${CLAUDE_PLUGIN_ROOT}`-style plugin vars
- **Tool-name aliasing** maps Claude's `Read`/`Edit`/`Bash`/`Grep` onto Grok's
  native tools so Claude-authored skills with `allowed-tools:` frontmatter
  resolve (`xai-grok-tools/src/types/claude_alias.rs`)
- A `/import-claude` command and `import_claude_modal` in the TUI

Implication for this workspace: skills/hooks written for Claude Code are —
by a competitor's deliberate choice — a portable format. Worth tracking as
the de-facto interop surface.

## Top borrowable ideas, ranked for this workspace

### For Muninn (Turso-backed memory)

1. **Evergreen carve-out in hybrid retrieval** (`xai-grok-memory/src/search.rs:157`):
   alongside the main FTS+vector query, always union a bounded slice restricted
   to durable sources so session-log volume can't crowd curated facts out of
   top-K. Portable to Turso as a `source` column + second query.
2. **Temporal decay only on non-evergreen rows** (`search.rs:108-134`):
   half-life decay on auto-captured chatter, never on curated memories.
3. **Two-speed write path + "dream" consolidation** (`storage.rs`, `dream.rs`):
   cheap append-only session logs every turn; an LLM consolidation pass gated
   cheapest-first (enabled → ≥4h elapsed → ≥3 new sessions) merges them into
   the curated store, with a `NO_REPLY` sentinel for "nothing worth keeping."
   Muninn's satisfaction-skew and zeitgeist-delta utilities are adjacent; the
   gating pattern and sentinel are directly liftable.
4. **Semantic dedup on flush** (cosine 0.92 default) before writing — Muninn
   has `is_semantically_duplicate` analogs in zeitgeist_delta; generalize it
   to all `remember()` writes from auto paths.
5. **Ephemeral-cwd short-circuit** (`storage.rs:35`): no-op workspace memory
   writes when running from a temp dir — relevant to throwaway CCotw sessions.

### For hooks / skills / orchestration

6. **Persistent-skeptic verification** (`xai-grok-shell/src/session/goal_classifier.rs:1949`):
   a gatekeeper verifier that is *resumed* across fix attempts (accumulating
   rejection memory) before fanning out a parallel skeptic panel on ambiguous
   verdicts. Maps directly onto the Agent tool's resume-by-name; a `/verify`
   loop that resumes one skeptic beats spawning amnesiac reviewers.
7. **Confidence + budget-gated nudging** (`laziness_classifier.rs`): a
   classifier fires corrective reminders only above a per-model confidence
   threshold and under a per-session nudge cap — an anti-fatigue pattern for
   any Stop/PostToolUse steering hook.
8. **Conditional skill surfacing** (`xai-grok-tools/src/implementations/skills/`):
   skills carry `paths:` globs and stay hidden until the agent *touches* a
   matching file; discovery walks upward from the touched file checking
   `.grok`/`.agents`/`.claude` dirs at each level. Lazy, navigation-triggered
   disclosure — contrast with our always-listed `<available_skills>` boot dump.
9. **Per-segment bash permission evaluation** (`permission/bash_command_splitting.rs`):
   tree-sitter-bash parses compound commands; each segment is evaluated
   separately, wrappers (`sudo`, `env`) unwrapped, heredocs excluded. Far more
   precise than prefix matching; also a nice validation of the tree-sitting
   skill's approach applied to security.
10. **Fail-open orchestration plumbing**: every verifier spawn, diff capture,
    and hook dispatch has an explicit fail-open branch (`record_fail_open`,
    hooks `dispatcher.rs`) so infra flakiness degrades to "skip check," never
    to blocked work. Their hooks are deliberately fail-open where Claude Code's
    PreToolUse-deny is fail-closed — a fork to choose consciously.

### Engineering patterns (general)

11. **Hashline anchor-hash editing** (`grok_build_hashline/`): file edits
    addressed by `LINE:HASH` anchors with self-healing shifted-anchor search on
    mismatch; three anchoring schemes shipped behind a trait plus a corpus
    benchmark harness to pick empirically. They also ship *four* competing edit
    tools (hashline, literal search/replace, Codex apply_patch, OpenCode edit)
    — evidence of live A/B on edit-format robustness.
12. **Compaction that can't orphan tool calls** (`xai-grok-compaction/src/intra_compaction/select.rs:128`
    `snap_to_safe_boundary`) — split-point snapping past assistant-tool/tool-result
    runs. Reusable in any transcript summarizer (e.g. transcript archiving here).
13. **Worktree pooling with btrfs/overlay/copy fallback** (`xai-fast-worktree`):
    pre-warmed, GC-tracked worktrees adopted by subagents; CoW snapshots where
    the filesystem allows, with metadata-verified safe-delete.
14. **Checkpoint-frozen streaming markdown** (`xai-grok-markdown/src/checkpoint.rs`):
    only re-render past the last provably-stable top-level block — O(new
    content) per token instead of O(total).
15. **Interjection queueing** (`xai-interjection-core`): user messages sent
    mid-turn are buffered and injected as a formatted synthetic user message
    the model may defer — no cancellation required.
16. **Doom-loop side-channel** (`xai-grok-sampler/src/doom_loop.rs`): opt-in
    header → server emits SSE repetition-detection events → client
    abort-and-retry policy that disarms on the final attempt.

## Architecture in one paragraph

A per-machine **leader daemon** owns the agent and all sessions (persisted to
`~/.grok/`, JSONL transcripts + search index); TUI/IDE/headless clients attach
over a Unix socket speaking framed **ACP** (Zed's Agent Client Protocol), with
newer clients evicting older leaders. Each session is a Tokio actor whose
`select!` loop multiplexes prompts, streamed turns, memory-flush/"dream"
timers, and stall-classification. Tools are trait-uniform across local
implementations, MCP servers, and a remote "computer hub" plane; subagents get
pooled git worktrees. An autonomous "goal harness" runs
planner → implementer → skeptic-panel → strategist role loops. The TUI is an
Elm-style reducer (`Action → dispatch → Effect`) over a virtual-scroll
scrollback with streaming-checkpointed markdown, terminal graphics (Kitty/
iTerm2), themes, ~65 slash commands — and a Doom raycaster easter egg.

## Method note

Repo fetched through the `muninn-fetch` Cloudflare Worker (CCotw agent proxy
scopes GitHub to session repos; the worker fetches codeload server-side —
memory `0c5159f0`). Structural scan via the tree-sitting skill; per-directory
symbol inventories from featuring's `gather.py`, sliced per cluster and handed
to four Sonnet Explore agents along with the treesit invocation recipe and
anti-crawl instructions (the context-handoff pattern now encoded in
exploring-codebases 2.4.0 / agent-routing 1.2.0, claude-skills PR #733).
