# Grok Build — Context Management + Extensibility Cluster Inventory

## 1. Memory system

**Storage** — `crates/codegen/xai-grok-memory/src/storage.rs`. Two-tier markdown files under `~/.grok/memory/`: global `MEMORY.md` and workspace-scoped `{project-slug}-{hash8}/MEMORY.md` (workspace hash = blake3 8 hex chars, `storage.rs:60`). Session transcripts land as daily append-only logs: `sessions/YYYY-MM-DD-{slug}-{sid8}.md` (`write_daily_log`, `storage.rs:162`, timestamped `---` sections on append). `ephemeral` flag silently no-ops workspace writes for temp-dir CWDs (`storage.rs:35,175`).

**Index** — `schema.rs:23`. SQLite with 3-4 tables: `meta` (kv), `chunks` (text + blake3 `hash`, `access_count`, `last_accessed`), `chunks_fts` (contentless FTS5/BM25), optional `chunks_vec` (sqlite-vec `vec0`, dims from config). `chunker.rs` splits markdown by header level with overlap (`max_chunk_chars=1600`, `chunk_overlap_chars=320` defaults, `xai-grok-config-types/src/memory.rs:14-27`).

**Retrieval** — `search.rs:146` `hybrid_search`: FTS candidates + a supplemental "evergreen" (global/workspace-source) FTS query so session-log volume doesn't crowd out durable facts (`search.rs:157`), optional vector KNN merge, weighted score combine (text_weight/vector_weight), **temporal decay** `e^(-ln2*age_days/half_life)` applied only to session-sourced chunks, never to evergreen sources (`search.rs:108-134`), then MMR diversity re-rank (`mmr.rs:59`).

**Write/load triggers** (config in `xai-grok-config-types/src/memory.rs`, orchestration in xai-grok-shell):
- **Boot load**: `MemoryInitialInjectionConfig` (default `enabled=true`) — searches memory and injects a reminder on turn 1.
- **Mid-session flush**: `MemoryFlushConfig` — pre-compaction flush turn (`soft_threshold_tokens=4000` headroom), optional `idle_timeout_secs` background flush, cosine `semantic_dedup_threshold` (default 0.92) to avoid re-writing near-duplicate facts.
- **Session end**: `MemorySessionConfig.save_on_end=true`.
- **Consolidation ("dream")** — `dream.rs`: gated by enabled → `min_hours` (default 4) since last consolidation → `min_sessions` (default 3) new session logs (`check_dream_gates`, `dream.rs:40`, cheapest-gate-first). An LLM pass (`DREAM_SYSTEM_PROMPT`, `dream.rs:88`) merges/dedupes/resolves-contradictions across session logs into `MEMORY.md`, discarding ephemeral chatter and preserving decisions/architecture/preferences. `NO_REPLY` sentinel means nothing worth persisting (`process_dream_response`, `dream.rs:273`). Capped at 32K input chars (`MAX_DREAM_INPUT_CHARS`); only successfully-processed session stems are deleted after consolidation.
- **External edits**: `watcher.rs` — lock-free `ArcSwap<HashSet<PathBuf>>` notify watcher on `~/.grok/memory/**/*.md`; dirty paths reindexed/deindexed lazily on next `memory_search` call.
- **GC**: `MemoryGcConfig` (default 30 days) prunes orphaned/empty workspace dirs on session init.

## 2. Compaction

Shared crate `xai-grok-compaction` serves **two hosts with two different strategies** (`lib.rs:1-38`):
- **`code_compaction/`** — grok-build's (this CLI's) whole-session **full-replace**: one LLM call summarizes the entire session; used by `intra_compaction::IntraCompactionMode::FullReplace`.
- **`intra_compaction/`** — Grok *chat*'s (the separate web product) tail-keep, per-step partial pass (`StepsOnly`/`HistoryOnly`/`HistoryThenSteps`).
- **`inter_compaction/`** — Grok chat's chunked, between-turn pass (`inter_compaction/compact.rs:81`, `sample_compaction_chunked`).

**Trigger** (`intra_compaction/trigger.rs:117` `should_compact`): pure function, `last_prompt_tokens > context_window * trigger_threshold_percent/100` (default 85%). `FullReplace` mode ignores `min_steps_before_compact` (can fire on step 0 with a huge first prompt); partial modes gate on min steps.

**Selection** (`select.rs:60` `select_turns_to_compact`): walk backward accumulating "keep" tokens vs `target_tokens` (default 50%), then `snap_to_safe_boundary` (`select.rs:128`) forward-advances the split past any `[Assistant-with-tool-requests, Tool, Tool...]` run so tool calls/results are never orphaned (API would 400 on dangling tool_use).

**What's preserved** (`code_compaction/assemble.rs:48`, canonical structure): `[system_message, user_message_prefix, AGENTS_MD_reminder?, last_user_query?, recent_messages_verbatim, compaction_summary, system_reminder?]`. The post-compaction system-reminder (`reminder.rs`) re-injects still-running background tasks, actionable TODOs, and running subagents — pure formatting shared by both hosts, snapshotting/tool-naming stays host-side.

## 3. Codebase graph

`xai-codebase-graph` builds a **per-file ScopeGraph** via tree-sitter (`scope_graph/graph.rs:485` `scope_graph_from_definitions_query`, `:565` `extract_symbols_fast`): nodes = `Symbol`/`LocalDef`/`LocalImport`/`LocalScope`/`Reference` keyed by `SymbolId{namespace_idx, symbol_idx}` (`nodes.rs`), edges via `EdgeKind`. Supports rust/ts/js/python/go (`languages/*.rs`).

`index_manager.rs` (1574 lines, channel-based actor) is the orchestrator: file-watch events (debounced via notify-debouncer-full) → sequential single-writer mutation of a `ScopeGraphIndex`, avoiding `Arc<Mutex>`; dedup via a process-global `ACTIVE_MANAGERS: DashMap<PathBuf, Weak<...>>` (one manager per workspace per process); `MAX_INDEXABLE_FILE_SIZE = 5MB`. Cross-process coordination via file locks with PID+timestamp staleness (`manager/lock.rs`, distinct stale windows per op: load 120s, save 120s, build 600s, bg-refresh 300s). Cache persisted as a serialized `ScopeGraphIndex` blob (`manager/cache.rs:35-38`).

Consumption: `navigation.rs` exposes go-to-definition/go-to-references by `(path, row, col)` → `Location{path, line, symbol}`. Standalone `bin/code_graph.rs` CLI, implying subprocess-backed tool invocation rather than in-process library call from the agent loop.

## 4. Extensibility

**MCP** (`xai-grok-mcp`) — built on the official `rmcp` SDK; stdio and `StreamableHttp` transports (`servers.rs`), OAuth (`oauth.rs:65` dedup'd per-server auth with mutex-guarded `AuthorizationManager`), and a distinctive **ACP-bridged in-process transport** (`acp_transport.rs`): in-process "SDK MCP servers" (analog to Claude Agent SDK's `create_sdk_mcp_server`) run inside the *client* process, and the agent reaches them by round-tripping JSON-RPC over a reverse `x.ai/mcp/sdk_call` ACP request — documented as half-duplex v1 (no server→client notifications/sampling/roots yet). Tool names namespaced `server__tool` (`MCP_TOOL_NAME_DELIMITER`).

**Hooks** (`xai-grok-hooks`) — event set (`event.rs:13`): `SessionStart/End`, `Stop`, `StopFailure`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionDenied`, `UserPromptSubmit`, `Notification`, `SubagentStart/Stop`, `PreCompact`, `PostCompact` — a superset of Claude Code's hook events, with a compat-parsing layer accepting Cursor-style names (`beforeShellExecution`, `afterFileEdit`, etc., `event.rs:60-76`) mapped onto generic Pre/PostToolUse. Config format is **directly wire-compatible with `~/.claude/settings.json`** (`config.rs:10-13`): `{"hooks": {"<Event>": [{"matcher": "...", "hooks": [{"type": "command"|"http", "command"/"url", "timeout", "env"}]}]}}`. Reserved env vars stripped from user `env` (`GROK_HOOK_EVENT`, `GROK_SESSION_ID`, `CLAUDE_PROJECT_DIR`, etc., `config.rs:87-89`). Runners: `runner/command.rs` (subprocess) and `runner/http.rs` (webhook). Dispatch (`dispatcher.rs:31`) is explicitly **fail-open**: hook timeout/crash/malformed-output surfaces in the UI but never blocks the tool call — rustdoc states this is a deliberate deviation from fail-closed because Grok "runs in protected environments." Global per-hook enable/disable persisted via `trust.rs`.

**Config** (`xai-grok-config` + `-config-types`) — layered TOML: system-managed → user-managed → project → env-var expansion, `deep_merge_toml` (`loader.rs:416`). Notable: **signed policy** verification (`signed_policy.rs`) — Ed25519-style signature envelopes over managed config with trusted-key embedding, sidecar signature files, compromise/staleness detection (MDM/enterprise policy tamper-protection). **Campaigns** (`campaigns.rs`) — a dismissible, patch-based in-app announcement/config-override system layered like feature flags. `signed_policy.rs` + `macos_managed.rs` + `validation.rs` form an MDM-grade managed-config story beyond Claude Code's settings model.

**Plugin marketplace** (`xai-grok-plugin-marketplace`) — reads `.grok-plugin/plugin-index.json`, **falling back to `.claude-plugin/plugin-index.json`** (`catalog.rs:1-9`) — directly interoperable with Claude Code's plugin marketplace format/schema. Git-cache-backed sources (`git.rs`, `sync_source_cache_with_mode`), path-traversal-hardened relative paths (`types.rs` `MarketplaceRelativePath::parse` rejects `..`, absolute, prefix components), transactional update path (`installer.rs:201`).

**Sampler config schema highlights**: `xai-grok-sampling-types` conversation/messages/responses abstractions cover 3 wire protocols (chat-completions, Anthropic-style `messages`, OpenAI `responses`) behind one `ConversationItem` model, with `repair_dangling_tool_calls`/`dedup_duplicate_tool_results` self-healing utilities (`conversation.rs:2784,2911`).

## 5. Oddballs

**Sampler / doom-loop**: opt-in server-side repetition detector (`x-grok-doom-loop-check` header) — the inference API emits mid-stream SSE events (`response.doom_loop_check`) and a terminal field carrying opaque trigger labels like `tail_repetition:4@response` or `low_logprob@channel` when it detects the model looping; the client (`doom_loop.rs`) collects these per-attempt and can abort-and-retry with a confidence policy (`DoomLoopRecoveryPolicy.max_threshold`) that disarms once the retry budget is spent so the final attempt is always accepted. Server-assisted anti-repetition safety net layered on client-side retry.

**Voice**: mic → streaming STT → pager events (`pipeline.rs`), driven by explicit `PttPress`/`PttRelease`/`Shutdown` commands supporting both a toggle (`/voice`, Ctrl+Shift+M) and true push-to-talk (F12 hold) — the pager owns capture lifecycle. Platform-specific capture (`capture.rs` vs `capture_linux.rs`) and a standalone streaming probe/diagnostic mode.

**Computer-hub** (`-core`, `-mcp-adapter`, `-sdk`, ~185 public symbols in sdk): a full custom RPC substrate — not MCP, though `-mcp-adapter` bridges it to MCP. One WebSocket per `(url, principal)` multiplexed via a demux + refcounted bound-session pool, transparent reconnect/replay state machine, `ToolServer`/`ToolHarness` builder pattern, admission control (global semaphore, `overloaded_response`), local-shadows-remote tool resolution (`CompoundResolver`). Likely xAI's remote-sandbox/computer-use execution plane — heavier infrastructure than Claude Code's local tool dispatch, built for a hosted multi-tenant "computer" backend.

**Interjection-core**: lets the user send a new message *while the agent is still mid-turn*, without cancelling. Buffered interjections get formatted as a synthetic user message wrapped in `<user_query>` with a "The user sent a message while you were working:" preamble (`format.rs:16`, truncated at 25,000 chars) and the model decides how/whether to defer to it.

**Circuit breaker**: standard sliding-window error-rate breaker (`window/min_samples/error_rate_threshold/open_duration/half_open_max_probes`), two named presets — `server()` (strict: 10 samples, 50% error rate, 10s open, trips on 429/500/502/503/504) vs `client()` (looser, longer cooldown, trips only on 401). Env-overridable via `CB_*` vars.

## 6. Techniques worth borrowing (Turso-backed boot memory + hooks/skills)

- **Hybrid FTS+vector with a source-weighted "evergreen" carve-out** (`search.rs:157`): run a second unfiltered query restricted to durable sources (global/workspace facts) so high-volume ephemeral rows (session logs) never drown out core facts in top-K. Directly portable to a Turso schema: tag rows with a `source` column and always union in a bounded evergreen slice.
- **Temporal decay applied only to non-evergreen rows** (`search.rs:108`): half-life exponential decay keyed off `created_at`, explicitly *not* applied to curated/global facts — avoids decaying hand-curated memory alongside auto-logged chatter.
- **Gate-cheapest-first consolidation** (`dream.rs:40`): check `enabled` → time-since-last → session-count-since-last, in that order, each cheap and short-circuiting, before any expensive I/O or LLM call.
- **Explicit ephemeral/temp-dir short-circuit** (`storage.rs:35,66,175`): detect throwaway/temp CWDs and silently no-op workspace writes — worth replicating for a boot-loaded memory system running in ephemeral containers.
- **Two-speed memory write path**: cheap append-only session logs at every turn vs. expensive curated `MEMORY.md` only rewritten by the dream LLM pass. Hot write path stays allocation-free and durable; curated file stays small and high-signal.
- **Semantic dedup threshold on flush** (cosine 0.92 default): before writing a mid-session flush note, check similarity against existing memory to avoid restating the same fact across a long session.
- **Tool-pair-safe compaction boundary** (`select.rs:128` `snap_to_safe_boundary`): a generic algorithm to never split between an assistant tool-request and its tool-result — reusable for any transcript-compaction logic.
- **Settings.json wire-compatibility for hooks and plugin marketplace**: Grok Build deliberately reads Claude Code's `settings.json` hook schema and `.claude-plugin/plugin-index.json` marketplace format as fallbacks — useful as a compatibility reference documenting exactly which fields/matchers/env-vars third-party tools already expect.
- **Fail-open vs fail-closed hook dispatch is a real design fork** (`dispatcher.rs:17-27`): Grok chose fail-open with an explicit threat-model justification; Claude Code is closer to fail-closed for `PreToolUse` deny hooks. Pick consciously.
- **Doom-loop-style server-assisted anomaly signaling**: a lightweight side-channel template (header opt-in → SSE annotations → client policy) that could carry other soft signals without a new API surface.
