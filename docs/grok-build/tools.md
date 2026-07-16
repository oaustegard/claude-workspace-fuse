# Grok Build — Tools + Workspace Cluster Inventory

## 1. Tool Inventory (model-exposed tools)

**Primary toolset** — `xai-grok-tools/src/implementations/grok_build/` (registered via `register_all()`, mod.rs:8): `ask_user_question`, `bash`, `deploy_app`, `enter_plan_mode`, `exit_plan_mode`, `grep`, `image_edit`, `image_gen`, `kill_task`, `list_dir`, `lsp`, `monitor`, `read_file`, `scheduler`, `search_replace`, `task`, `task_output`, `todo`, `update_goal`, `video_gen`, `web_fetch`, `web_search`.

| Tool | Purpose | Source |
|---|---|---|
| `bash`/`run_terminal_cmd` | Persistent shell exec, fg/bg, streaming | `.../grok_build/bash/mod.rs` (4775 lines) |
| `read_file` | File/image/PDF/PPTX reader | `.../grok_build/read_file/mod.rs`, `implementations/read_file/{image,pdf,pptx,metadata}.rs` |
| `search_replace` | String-anchored find/replace edit | `.../grok_build/search_replace/mod.rs` |
| `grep` | ripgrep-backed search w/ content/files/count modes | `.../grok_build/grep/mod.rs` + `ripgrep.rs` |
| `list_dir` | Directory listing (has legacy render mode) | `.../grok_build/list_dir/` |
| `task` / `task_output` | Spawn & poll subagents/background bash | `.../grok_build/task/{mod,backend,types}.rs`, `task_output/mod.rs` |
| `kill_task` | Kill background task | `.../grok_build/kill_task/mod.rs` |
| `monitor` | Attach to a running bg task, stream filtered events | `.../grok_build/monitor/{tool,event,mod}.rs` |
| `scheduler` | Cron-like recurring/interval prompts | `.../grok_build/scheduler/{actor,create,delete,list,interval}.rs` |
| `todo` | Structured todo-list state (replace/merge) | `.../grok_build/todo/mod.rs` |
| `update_goal` | Plan/goal tracking ack envelope | `.../grok_build/update_goal/mod.rs` |
| `ask_user_question` | Structured interview / clarifying-question UI | `.../grok_build/ask_user_question/{mod,format}.rs` |
| `enter_plan_mode`/`exit_plan_mode` | Plan-mode toggle | `.../grok_build/{enter,exit}_plan_mode/` |
| `web_fetch` | URL fetch w/ SSRF guard, domain allowlist, overflow budget | `.../grok_build/web_fetch/{mod,domain,ssrf,overflow}.rs` |
| `web_search` | Web search | `.../implementations/web_search/mod.rs` |
| `image_gen`/`image_edit`/`video_gen` | Media generation (xAI-specific) | `.../grok_build/{image_gen,image_edit,video_gen}/` |
| `deploy_app` | App deploy (stub in this checkout) | `.../grok_build/deploy_app_stub.rs` |
| `lsp` | LSP client: hover/defs/symbols/diagnostics, multi-server config | `implementations/lsp/{config,format,manager,mod,restart}.rs` |
| **Skill** | Skill discovery/execution tool | `implementations/skills/{skill,discovery,types}.rs` |
| **use_tool** | Generic MCP tool dispatcher | `implementations/use_tool/mod.rs` — `dispatch_mcp_tool()` |
| **search_tool** | Tool-search / progressive tool disclosure across MCP servers | `implementations/search_tool/mod.rs` |
| `memory.get`/`memory.search` | Cross-session memory backend | `implementations/memory/{get_tool,mod}.rs` |
| **apply_patch** | Codex-style unified-diff patch applier (alt edit tool) | `implementations/codex/apply_patch/{apply,parser,seek_sequence}.rs` |
| Codex-variant `read_file`/`grep_files`/`list_dir` | Alternate (Codex-compatible) tool surface | `implementations/codex/{read_file,grep_files,list_dir}/` |
| **hashline** `_read`/`_edit`/`_grep` | Anchor-hash based read/edit toolset (see §2) | `implementations/grok_build_hashline/{read_file,edit,grep}.rs` |
| `opencode` bash/edit/glob/grep/read/skill/todowrite/write | OpenCode-format compat tool surface | `implementations/opencode/mod.rs` |
| `grok_build_concise` bash/read_file/search_replace | Token-lean tool variants | `implementations/grok_build_concise/mod.rs` |

Registry: `xai-grok-tools/src/registry/types.rs::register_tool_pack` (types.rs:49); Claude↔Grok name aliasing at `xai-grok-tools/src/types/claude_alias.rs` — `kind_for`, `grok_names_for`, `claude_names_for` map Claude's `Read`/`Edit`/`Bash`/`Grep` tool names onto Grok's native tool set (claude_alias.rs:83-117) — a **Claude Code tool-name compatibility shim** so Claude-authored skills/subagents that hardcode `allowed-tools: Read, Bash` still resolve.

## 2. File Editing, Shell Execution, Permissions

### Hashline format (`grok_build_hashline`)
Anchor-hash addressed editing instead of line numbers or literal-string search/replace. `scheme.rs` (1-18) defines a pluggable `AnchorScheme` trait with 3 candidate implementations:
- **A `ContentOnly`**: pure content-hash of the line (weak — doesn't detect edits above).
- **B `ChunkFingerprint`**: local line hash + fixed-size chunk fingerprint (recommended default).
- **C `CheckpointChain`**: local hash + hash chained from nearest checkpoint (strongest freshness, most anchor churn).

Anchor string format: `"LINE:LOCAL"` or `"LINE:LOCAL:CONTEXT"` (`anchor.rs`/`scheme.rs` `ParsedAnchor::parse`, e.g. `"22:abc:rst"`). Edits (`edit/types.rs` `HashlineOp`) are `replace{anchor,end_anchor?,content}` (empty content = delete), `insert_after{anchor|"0:"|"EOF", content}`, `write{content}` (full overwrite) — applied bottom-up as a batch. On mismatch, error payload (`HashlineEditError`) includes `shifted_to`/`shifted_anchor` (bounded-radius search for a moved anchor — `anchor::find_shifted_in_content`) and `ambiguous_candidates` — self-healing against stale anchors instead of hard-failing. `benchmark.rs` runs a corpus-driven comparison harness across schemes for read-amplification/anchor-churn. `edit/apply.rs` is 2237 lines — the actual patcher. Coexists with three *other* edit tools (`search_replace` literal-match, Codex `apply_patch` unified-diff, `opencode` `edit`) — an internal experiment to find the most robust anchoring against model drift.

### Shell execution (`bash`)
`implementations/grok_build/bash/mod.rs` (4775 lines) — persistent shell session per workspace, fg (blocking) or bg (`is_background`→task_id). Timeouts: `DEFAULT_TIMEOUT` 120s soft default, `DEFAULT_MAX_TIMEOUT_MS` 300_000 (5 min) ceiling, both overridable; commands exceeding default timeout **auto-background** rather than being killed when `auto_background_on_timeout` is set (mod.rs:1428). Output streams as `bash_output_chunk` (raw terminal projection) capped at `MAX_PROGRESS_DELTA_BYTES`=16KiB/tick (mod.rs:67-81). Execution goes through `TerminalBackend` trait (`computer/types.rs:261-341`): `run`/`run_background`/`get_task`/`kill_task`/`kill_foreground_commands[_by_owner]`/`kill_all_background_tasks[_by_owner]`/`wait_for_completion`/`list_tasks`/`get_shell_cwd`/`reparent_notifications` (subagent → parent handle re-homing on subagent teardown) /`background_foreground_command` (mid-flight fg→bg promotion). Local impl: `computer/local/terminal.rs` (`LocalTerminalBackend`), `shell_state.rs` (persistent shell state dump/restore over a pipe FD, `ShellKind`). Optional `find`→`bfs`/`grep`→`ugrep` shadow injection (`computer/local/embedded_search_tools.rs`).

**PTY control** is a separate subsystem: `ptyctl`/`ptyctl-cli` — "headless PTY controller built on `alacritty_terminal`" (ptyctl/src/lib.rs:1-5), exposes an HTTP server (`server.rs::build_router`) plus a CLI (`send`/`screen`/`cursor`/`status`/`resize`/`wait`/`stop`) for scripted keystroke injection and styled/HTML screen scraping (`styled.rs`) — TUI automation distinct from the bash tool's stdout capture, with a session registry (`registry.rs`) for multiplexed named PTY sessions.

**Sandboxing** (`xai-grok-sandbox`): bubblewrap (`bwrap`)-based. `lib.rs` — `is_inside_bwrap`, `bwrap_reexec_command`/`bwrap_reexec_for_profile` re-exec the process under bwrap with deny lists; `is_active`/`profile_name`/`should_restrict_child_network` (child network namespace filter, `child_net.rs`)/`should_auto_allow_bash`. `deny/glob.rs` + `deny/mod.rs`: glob and exact-path deny lists mapped onto a `CapabilitySet` (`apply_deny_paths_to_capability_set`, `apply_deny_globs_to_capability_set`), bounded expansion (`expand_deny_globs` w/ max_depth/max_matches/max_entries guards). `paths.rs`: `essential_writable_paths`/`temp_writable_paths`/`grok_home`. `profiles.rs`: `load_sandbox_config`/`sandbox_profile_conflicts`.

### Permission model (`xai-grok-workspace/src/permission/`)
- `manager.rs`: `spawn_permission_manager[_with_hub]` — actor per session, evaluates bash commands via `evaluate_bash_segments` against `PermissionState`.
- `types.rs::AccessKind`: `Read(path)`, `Grep{path,glob}`, `Edit(path)`, `Bash(cmd)`, `MCPTool{name,input}` (args carried for classifier judgment), `WebFetch(url)`, `WebSearch(query)`.
- `rules.rs`: parses allow/deny/ask rule strings (`parse_permission_rule`) with escape handling and domain/bash-colon-wildcard stripping — same textual rule DSL as Claude Code settings.
- `bash_command_splitting.rs`: tree-sitter-bash parses scripts into `PlainCommand` sequences (`try_parse_word_only_commands_sequence`), detects wrapper commands (`sudo`, `env` — `is_wrapper_command`/`unwrap_wrappers`), setup commands, heredoc payload ranges (excluded from splitting), soft-break points — permission evaluation is per-*segment* of a compound shell command.
- `shell_access.rs`: static analysis of a parsed bash AST for write-target paths and redirect targets (`command_write_paths_in_tree`, `shell_redirect_targets`) to auto-classify a command's filesystem blast radius.
- **`auto_mode.rs`**: an LLM-based auto-approval classifier — `build_classifier_messages`/`default_auto_mode_classifier`/`parse_classifier_model_text` — a small model judges whether an access should be auto-approved in "auto mode" (with `access_requires_user_interaction` fast-path allowlists to skip the classifier call for known-safe kinds).
- **`claude_settings.rs`**: directly parses `.claude/settings.json` (`load_claude_settings`, `find_claude_settings_paths`, `extract_default_mode`) — Grok Build **reads real Claude Code settings files** for permission-mode/env compat (`has_claude_compat`, `load_claude_env_with_project`).
- `hub_permission.rs`: routes permission prompts through an external "hub" transport (`request_permission_via_hub`) with `PromptOutcome`, for host/IDE-integrated approval UIs.
- `resolution.rs`: merges project/user/managed-policy permission configs, `ManagedSettings` (org policy), `yolo_disabled_by_policy` (org can force-disable full-auto).
- `state.rs`: persists per-project permission decisions to disk keyed by client identifier, with staleness cleanup.

## 3. Checkpoint / Undo

Three independent layers compose for undo, described in `session/checkpoint.rs` (workspace crate):
1. **File-level rewind** — `RewindPoint` (workspace-types `types/session.rs:61-74`) + `FileStateTracker` snapshots (before/after per file per prompt). `rewind_files()` (`session/file_state.rs:922`) reverts by finding the earliest before-snapshot per touched file at/after `target_prompt_index`, detects external modification/deletion conflicts (`ConflictType::{DeletedExternally,CreatedExternally,ModifiedExternally}`), truncates rewind history from that point.
2. **Hunk-tracker delta** (`xai-hunk-tracker`) — `Hunk{id,path,line_info,source,old_text,new_text,patch,created_at,selected}` (`types.rs:157-177`) tracked per-actor, diffed via `diff.rs` (`compute_hunks`, `generate_unified_patch`, hunk move/overlap detection `hunks_match_content`/`hunk_moved`/`find_overlapping_hunks` — survives edits shifting line numbers). `HunkTurnDelta{prompt_index, file_states, hunk_ids}` bundles a turn's hunks; gated behind `GROK_WORKSPACE_REWIND_HUNKS` env flag (checkpoint.rs:102). `is_lfs_pointer`/`is_binary`/`classify_bytes` guard against tracking large/binary content.
3. **`RewindCheckpoint`** (checkpoint.rs:90-100) — bundles `fs: RewindPoint` + optional `hunks: HunkTurnDelta` per `prompt_index`; keyed at turn boundaries via `WorkspaceHandle::on_turn_boundary` → `TurnBoundary::{Start,End}`. Durable persistence gated behind `GROK_WORKSPACE_REWIND_DURABLE` (in-memory-only by default).

**xai-fast-worktree** — worktree lifecycle for subagent/task isolation, layered strategies:
- **btrfs** (`btrfs/snapshot.rs`): `create_snapshot`/`create_snapshot_with_symlink` (91-221) — CoW subvolume snapshot; when source is bind-mounted, the real snapshot subvolume is created *inside* the btrfs mount and `dest` becomes a symlink to it. Metadata sidecar (`write_btrfs_metadata`/`snapshot_meta_state`) proves snapshot ownership before any reclaim/delete (`is_safe_snapshot_delete_target`).
- **overlay** fallback (`overlay/{detect,snapshot}.rs`): fuse-overlay-based worktree when btrfs isn't available.
- **plain copy** fallback (`copy/{engine,worker,shard,cow,gitdir}.rs`): parallel sharded copy with reflink/CoW (`copy/cow.rs::clone_file`), `.gitignore`-aware skip set (`skip.rs::collect_unignored_paths`), worker pool.
- Registered in a local db (`WorktreeDb`, `queries.rs`: register/unregister/mark_dead/touch/list/stats/sweep_dead) with `gc_worktrees` and orphan-snapshot cleanup — a garbage-collected worktree pool, not naive `git worktree`.
- `git/checkout.rs`: `snapshot_worktree_to_ref`/`rehydrate_worktree_from_ref`/`transfer_snapshot_to_repo` — commits a worktree's state to a ref for cross-worktree/session handoff (`worktree/mod.rs::rehydrate_subagent_worktree`).
- `xai-grok-workspace/src/worktree/mod.rs`: creation-mode selection, label derivation/collision handling, jj (Jujutsu) workspace support alongside git (`create_jj_workspace`), background ignored-file copy.

## 4. Notable techniques worth borrowing

- **Skills system vs Anthropic's**: `SkillInfo` (`implementations/skills/types.rs:41-123`) is a superset of Claude's SKILL.md frontmatter, adding: (a) `paths: Option<Vec<String>>` — gitignore-style glob-gated skills held back from the listing until a matching file is *touched* by a tool call (`ConditionalSkills`) — skills conditionally surfaced by file-type/directory activity, not always-listed; (b) `when_to_use` as a distinct field from `description`; (c) `disable_model_invocation` (slash-command-only skills) vs `user_invocable`; (d) plugin fields (`plugin_root`/`plugin_data`/`plugin_version`) mapping directly onto Claude Code's `${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PLUGIN_DATA}` conventions — deliberate plugin-format compatibility. Discovery (`discovery.rs::discover_skills_for_paths`, 845-922) is **directory-proximity-triggered**: on touching a file, walks upward from that file's directory to cwd/git-root, checking `.grok`/`.agents`/(optionally `.claude`, vendor-compat flag) at each level for skill/command files — dynamic, lazy discovery keyed off the model's actual navigation. `SkillManager` (`skill_discovery_tracker/mod.rs:84-144`) tracks `startup_skills` vs `discovered_skills` separately, dedups by canonical path, renders budget-capped announcements (`DEFAULT_CHAR_BUDGET`, `SKILL_BUDGET_CONTEXT_PERCENT`) as XML or markdown system-reminders, with `real_cwd_prefix`/`display_cwd` rewriting so forked/overlay sessions never leak real host paths to the model.
- **Claude Code compatibility as a first-class design goal**: tool name aliasing, reads `.claude/settings.json` directly, same allow/deny/ask rule grammar, plugin-var compatibility — Grok Build deliberately ingests Claude Code project config so a repo configured for Claude Code "just works" under Grok Build. A competitor targeting Claude Code's config surface as their compatibility target.
- **LLM-based auto-approval classifier** (`permission/auto_mode.rs`) with a fast-path allowlist in front of it — cheap-model gate before a model call for ambiguous auto-mode approvals, plus org-level `yolo_disabled_by_policy` override.
- **Anchor-hash editing with self-healing shift search** (hashline) — a different bet than literal-string or line-number editing for surviving model staleness/drift; they ship 3 competing schemes plus a corpus benchmark harness (`benchmark.rs`) to pick one empirically.
- **Hunk-tracker's move/overlap detection** (`diff.rs::hunk_moved`/`hunks_overlap`/`find_matching_old_hunk`) tracks logical hunks across shifting line numbers between snapshots.
- **btrfs symlink-indirection trick** for bind-mounted sources, with metadata-verified safe-delete to avoid cross-session subvolume clobbering.
- **Per-segment bash permission evaluation** via tree-sitter-bash parsing rather than whole-string pattern matching — handles compound commands, wrapper-command unwrapping, heredoc-exclusion; more precise than prefix/regex allowlisting.
- **PTY control as a separate HTTP-driven daemon** (`ptyctl`) — scripted TUI interaction (screen scraping with styled/HTML render, wait-for-text/regex) that a plain output-capturing bash tool can't do.
