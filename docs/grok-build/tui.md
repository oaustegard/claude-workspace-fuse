# Grok Build — TUI Cluster Inventory

## 1. Architecture

**Model**: Elm-style unidirectional data flow, single-threaded (Tokio async I/O, sync render).
- `Action` enum (`app/actions.rs:38`) — user/system intents (`Quit`, `SendPrompt`, `PickSession`, ...)
- `dispatch(action: Action, app: &mut AppView) -> Vec<Effect>` (`app/dispatch/router.rs:129`) — pure reducer, no I/O. Delegates to ~30 per-domain handler modules (`dispatch/{auth,billing,dashboard,prompt,queue,rewind,session/*,settings/*,turn,...}.rs`, 245 symbols).
- `Effect` enum (`app/actions.rs:1318`) — async work requests (`CreateSession`, `FetchSessionList`, `ScanForeignSessions`, ...), executed off-reducer by `process_effects` (`app/event_loop.rs:3201`) which spawns into a `tokio::task::JoinSet`.
- `AppView` (`app/app_view.rs:534-1079`) — the God-object state root: per-agent `IndexMap<AgentId, AgentView>`, models, settings registry, welcome/dashboard/session-picker state, cursor/scroll/appearance, notification service, minimal-mode substate. Single-threaded by design (thread-local caches, `Rc<RefCell<>>` for shared MRU).

**Event loop** (`app/event_loop.rs:1482` main loop, `1674` `tokio::select!`, biased):
1. leader-disconnect cancel
2. quit-notify (SIGTERM)
3. `acp_rx.recv()` **gated `if input_rx.is_empty()`** — batches up to `ACP_DRAIN_BATCH_MAX` streamed messages before drawing, but yields immediately if terminal input arrives (starvation-avoidance rationale documented inline).
4. `tasks.join_next()` (spawned effect results)
5. `progress_rx` (session-restore progress)
6. bg-update-check
7. terminal/keyboard input
8. voice STT deliberately **last** (hot mic streams at 5–20Hz and would starve everything else if higher).
Draw calls are rate-limited via `min_draw_interval`/`draw_scheduled_at` coalescing so a token firehose doesn't redraw every message.

**Streaming render path**: ACP message → `acp_handler::handle` mutates `AppView`/`ScrollbackEntry` → `app.draw(terminal)` re-renders dirty region only, inside `xai_ratatui_inline::common::with_synchronized_output` (DEC 2026 sync-update wrapping, `xai-ratatui-inline/src/common.rs:76`).

**Scrollback model** (`scrollback/`, 121 symbols, 55 files):
- `ScrollbackState` (`scrollback/state/mod.rs:42`) — `IndexMap<EntryId, ScrollbackEntry>` + incremental-update tracking sets: `running` (O(running) tick), `flashing` (finish-flash animation), `dirty_heights` (only recompute layout for changed entries), `committed`/`commit_scan_cursor`/`commit_expand_ring` (minimal-mode native-scrollback bookkeeping). `scroll_offset`/`total_height` are `usize` (long sessions exceed `u16::MAX` rows — a real bug they fixed).
- `RenderBlock` enum (`scrollback/block.rs:363`) — `UserPrompt`, `AgentMessage`, `ToolCall`, `Thinking`, `System`, `SessionEvent`, `BgTask`, `Subagent`, `Btw`, `ContextInfo`, `CreditLimit`; dispatched via a `delegate_block!` macro instead of dyn-trait objects.
- `groups.rs`/`verb_group.rs` — collapses runs of tool calls into `GroupSpan`s ("Ran 5 tools ▸") with `show_thinking` gating.
- `render.rs:223` `render_scrolled_entries_with_scratch` — the paint routine; takes a `layout_cache: &[EntryLayoutInfo]` and only touches the visible virtual-scroll window (`state/layout.rs:1648` `compute_paint_window`).

**Inline vs fullscreen**: two independent presentation modes sharing `AppView`/dispatch:
- **Fullscreen** (alt-screen, default): interactive `ScrollbackPane` (scroll/fold/mouse selection) owns the buffer.
- **Minimal** (`xai-grok-pager-minimal` crate, `--minimal`): prints finalized blocks once into the terminal's *native* scrollback via `xai_ratatui_inline::Terminal::insert_before`/`emit_to_scrollback` (`xai-ratatui-inline/src/scrollback.rs:15`), with only a small pinned "live region" redrawn each frame. Wired via an **inversion-of-control function-pointer seam** (`xai_grok_pager::minimal_hook`) to avoid a Cargo dependency cycle — the binary installs the `draw` fn pointer at startup.
- Runtime switch: `/minimal`, `/fullscreen` slash commands trigger `Action::RelaunchInScreenMode` → process re-exec (`app/screen_mode_relaunch.rs`).

## 2. Feature inventory

**Slash commands** (`slash/commands/mod.rs:75` `builtin_commands()`, ~65 registered): exit/quit, help, docs, home, new, fork, compact, copy, find, history, export, transcript, expand, context, minimal/fullscreen switch, model, effort, always-approve, auto, multiline, compact-mode, vim-mode, hooks, plugins, marketplace, skills, share, session-info, rename, dashboard, cd, theme, feedback, announcements, remember, plan, view-plan, resume, mcps, btw, recap, terminal-setup, voice, loop (gated on `scheduler_create` tool availability — commands can be conditionally hidden per-session), imagine, imagine-video, timestamps, timeline, toggle-mouse-reporting, settings, privacy, rewind, jump, login, logout, import-claude, usage, queue, tasks, release-notes, config-agents, personas, gboom (easter egg), scroll-debug, debug. Aliases (`/m`→model, `/welcome`→home) resolved through `CommandRegistry`.

**Modals/panels/widgets** (`views/`, 534 symbols, 72 files): `agents_modal`, `announcements`, `btw_overlay`, `completion_dropdown`, `context_bar`, `credit_bar`, **`dashboard/`** (Agent Dashboard: multi-session fleet overview, grouped rows, peek panel), `extensions_modal`, `file_search/` (fuzzy file picker + line viewer), `goal_detail`, `import_claude_modal`, `jump` (jump-to-message), `mcps_modal`, `memory_modal`, `modal`/`modal_window` (shared chrome), `new_worktree_dialog`, `permission_view`, `persona_detail`, `picker.rs` (unified picker: 3 render paths), `plan_approval_view`, `progress_bar`, `question_view`, `queue_pane`, `rewind` (time-travel/undo), `session_picker`, `settings_modal`, `shortcuts_bar`/`shortcuts_help`, `slash_dropdown`, `tasks_pane`, `timeline`, `turn_status`, `welcome/`. Plus `/gboom` — a full Doom-style raycasting FPS (`xai-grok-pager-render/src/gboom/{engine,assets}.rs`, Lodev-DDA grid raycaster, textured walls/floor/ceiling, sprite billboards) rendered to an RGB8 framebuffer and PNG-encoded through the Kitty graphics protocol.

**Diff view**: `xai-grok-pager/src/diff.rs` — `build_diff_hunks`, hunk stitching/overlap-merging for edit tool rendering.

**Images/terminal graphics** (`xai-grok-pager-render/src/terminal/image.rs`): `GraphicsProtocol` enum — `Kitty` (also Ghostty/WezTerm), `ITerm2`, `None`; `detect_graphics_protocol()`, Kitty transmit/place/crop/clear, iTerm2 inline image protocol, `fit_image_to_cells`.

**Clipboard**: `xai-grok-pager-render/src/clipboard/` — `SystemClipboard` (arboard) plus multi-fire strategy (native OS / tmux passthrough / OSC 52) gated by remote-session and containerized-no-display detection; `trust.rs` handles paste trust/fallback UX.

**Themes**: `xai-grok-pager-render/src/theme/` (165 symbols) — GrokNight (default), GrokDay, Oscura, RosePine, terminal-default variants; all colors truecolor `Color::Rgb`, quantized at startup to detected terminal capability (`color_support::quantize`); OSC 11 background-color probe (`osc11.rs`) for startup dark/light detection plus a live `SystemAppearanceWatcher` (`dark-light` crate) for hot-reload.

## 3. Markdown + Mermaid rendering pipeline

**`xai-grok-markdown`** — streaming markdown renderer purpose-built for LLM token-by-token output (`lib.rs:1`):
- **Checkpoint-based freezing** (`checkpoint.rs`): a `Checkpoint{source_bytes, output_lines, kind}` marks stable **top-level** (depth-0) block boundaries (heading, closed paragraph, code block, closed blockquote/list, thematic break, table, HTML block). Content nested inside lists/blockquotes/tables can never checkpoint since the container might still extend. `StreamingMarkdownRenderer::push_and_render` only re-parses/re-renders the "tail" after the last checkpoint — turns O(total output) redraw-per-token into effectively O(new content).
- LaTeX math (`latex/{commands,environments,symbols}.rs`) converted to Unicode approximation inline (`$E=mc^2$` → `E=mc²`), not images.
- Syntax highlighting via `syntect`; per-terminal color downgrading for 256/16-color terminals.
- **Mermaid, two independent renderers**:
  1. `xai-grok-markdown/src/mermaid.rs` — pure Unicode box-drawing ASCII-art diagram renderer (flowchart/sequence/state) rendered *inline in the markdown flow* (no raster image), capped (`MAX_NODES=128`, `MAX_EDGES=512`, `MAX_CANVAS_CELLS=1<<21`) with hard limits against pathological LLM-generated diagrams.
  2. `xai-grok-mermaid` crate — real PNG rasterization for click-to-view, via a swappable `MermaidEngine` trait (`engine.rs:100` `render_checked`, panic-isolated). Default `PureRustEngine` (`pure.rs`) uses **vendored** `third_party/mermaid-to-svg` (MIT, dagre-layout port, built on `third_party/{graphlib_rust,dagre_rust,ordered_hashmap}`) → SVG → `resvg`/`tiny-skia` raster. An alternate `MmdcEngine` shells to system Node `mmdc` but is never auto-selected.
  - Rendering is **lazy** (only on click "Open"/"Copy path") and runs **out-of-process**: the pager re-execs itself as `xai-grok-pager __mermaid-render` (`app/mermaid_worker.rs`) because the shipped binary is `panic = "abort"` so in-process `catch_unwind` is a no-op — a malformed diagram could otherwise abort the whole TUI. Child killed on wall-clock timeout, writes PNG atomically, parent polls via `mpsc`/`try_recv` each tick.
  - Per-session on-disk PNG cache with size-bounded sweep (`sweep_session_cache`).

## 4. Notable techniques worth borrowing

- **Checkpoint/freeze incremental markdown**: cheap, general pattern for any streaming-token render surface — only re-render past the last "provably stable" block boundary.
- **Sans-IO reducer + effect list**: `dispatch(Action, &mut State) -> Vec<Effect>` keeps all state mutation synchronous/testable; async work is data, executed by the event loop, not embedded in handlers.
- **Biased `tokio::select!` with input-gated arms**: `if input_rx.is_empty()` guard on the high-volume stream arm prevents a token firehose from starving keyboard input, while keeping cancel/quit strictly prioritized.
- **Draw-rate decoupling from state-change rate**: `min_draw_interval`/`draw_scheduled_at` coalesce redraws under heavy streaming without dropping the final frame.
- **Out-of-process untrusted-render isolation** under `panic=abort`: re-exec self as a subcommand + wall-clock-killed child, when in-process `catch_unwind` isn't available in the release profile.
- **IoC seam via function pointers to break a crate cycle**: cleaner than a trait-object plugin system when only one implementation will ever exist.
- **`IndexMap` + auxiliary id-sets (`running`/`dirty_heights`/`flashing`) instead of per-entry dirty flags**: keeps animation/layout ticks O(changed) instead of O(entries) on long sessions.
- **Dual-tier diagram rendering** (cheap inline ASCII-art always + expensive lazy raster on demand) — a template for any "preview cheap, materialize expensive on interaction" terminal feature.
- **Vendoring a whole layout engine (dagre) as pure Rust** instead of shelling to Node/mermaid-cli by default — worth it when a system dependency would gate a core feature.
