# Muninn backend → remote MCP on Cloudflare

Design + migration plan for moving the memory backend out of the session and into a
deployed Worker, on the Sage pattern (`oaustegard/sage`, `mcp/`), while keeping the
genuinely-local half skill-shaped.

Status: **in progress**. Stage 0 shipped (#98 — `remembering/scripts/provenance.py`); Stage 1
is being built in [`oaustegard/muninn-mcp`](https://github.com/oaustegard/muninn-mcp).
The design below is unchanged from the original proposal except where a stage records
what actually happened.

---

## 1. Why

Today every Muninn session reaches Turso by running Python that was fetched, at a pinned
SHA, as a tarball, into a mount, with `TURSO_TOKEN` in the environment. That has four
costs:

| Cost | Detail |
|---|---|
| Boot tax | Tarball fetch + env sourcing + `.pth` setup before the first `recall()` |
| Credential spread | `TURSO_TOKEN` must exist in every environment that remembers anything |
| Surface limit | Only works where bash + Python exist. Mobile claude.ai, Slack, a phone — no memory |
| Version skew | Pinned SHAs, plus a deprecated mirror in `claude-skills` that a workflow syncs |

A remote MCP fixes all four: one deployment, OAuth'd connector, no credentials in the
session, and memory available anywhere the connector is enabled.

It does **not** fix — and must not break — the local power path: `_exec()` raw SQL and
corpus analysis with native dependencies (`memory_tfidf`'s numpy/scikit-learn).

**§7 extends this to a second track:** proxying the third-party APIs (GitHub, Bluesky,
WhiteWind, Strava) through the Worker too, so credentials leave the session entirely and
the Claude.ai project-knowledge env files stop being load-bearing. That track is
stateless, cheaper, and deliberately decoupled from the staged memory migration.

---

## 2. The seam

Three destinations, not two. The split is by *what the code needs*, not by what feels
core.

### Goes remote — `muninn-mcp/` Worker

Everything whose only dependency is Turso and whose result is text.

- `recall`, `recall_batch`, `get`, `get_chain`, `get_alternatives`
- `remember`, `remember_batch`, `supersede`, `forget`, `reprioritize`, `strengthen`, `weaken`
- `config_get`, `config_set`, `config_list`, `profile`, `ops`, `set_rule`
- `journal`, `journal_recent`
- `boot` — the composed payload
- `spokes_list`, `spokes_summary` — registry reads are just `config`

### Stays skill-shaped — `remembering/` + `muninn_utils/`

Everything that needs local execution, native libraries, or a Python object.

- **`_exec()` raw SQL** — the ad-hoc analysis escape hatch. Irreplaceable by a fixed tool set.
- **Task discipline** — `task()`, `recall_gate` are in-session control-flow objects. A
  context manager cannot live behind JSON-RPC. Persistence goes over MCP; the object stays local.
- **Boot's environment prelude** — `.pth` setup, `muninn_utils` materialization, env fallback persist.
- **Native-dependency analysis** — `memory_tfidf` (numpy + scikit-learn),
  `search_reindex` (subprocess + tempfile), `skill_lint` (yaml + local files),
  `zeitgeist_delta` (pathlib), export/import, migrations.

Note this list is *shorter than it first appears* — see §7. The credential-bearing
utilities do not belong here, because the credentials themselves move to the Worker.

### Becomes cron — `muninnd/` Worker

The saged analog. These are exactly the operations that today only run when someone
remembers to run them:

- `curate`, `consolidate`, `therapy_reflect`
- `prune_by_age`, `journal_prune`
- `_build_cooccurrence` rebuild

Keep saged's discipline: **additive and attributable**. `muninnd` proposes structure
(consolidations, priority demotions), applies it deterministically, and every write it
makes carries its own provenance so a bad pass is identifiable and revertible.

### Tool budget

Each tool's schema costs tokens in *every* conversation on the connector. Sage ships 7.
Muninn's Python surface is ~40 exported functions; it must collapse to **8–12** tools —
e.g. one `muninn_config` tool with an `op` parameter rather than four. Anything that
doesn't earn its schema stays in Python. This constraint is a feature: it forces the
seam above to be drawn honestly.

Collapsing the *count* is only half of it; the *width* of each schema matters as much.
See §8 — the resource layer is what keeps these schemas thin.

---

## 3. What the port actually costs (smaller than it looks)

The scary part of re-hosting a search backend is reimplementing the ranking. **Muninn's
ranking is already server-side SQL**, not Python:

```
turso.py:536-566   bm25(memory_fts, 0, 1.0, 1.0)
                     × (1 + priority × 0.3)
                     × recency_decay
                     × confidence_boost
                     [× access_boost when episodic]
```

Green transcribes that SQL string. It does not reimplement BM25, recency decay, or
priority weighting. The composite score is computed by Turso in both worlds.

That collapses parity risk down to four things, all small and all testable:

1. **`_escape_fts5_server()`** (`turso.py:418`) — strips `" * ( ) : ^` and the FTS5
   keyword operators `AND OR NOT NEAR`. Sage's `fts.ts` is the precedent for how
   tokenizer detail bites; this is the direct analog and the highest-value unit test.
2. **Tag co-occurrence expansion** (`_cooccurrence_expand`) — fires when FTS returns
   fewer than `expansion_threshold` (3) results. Stateful against the `tag_cooccurrence`
   table, and easy to get subtly wrong.
3. **Result normalization** — `MemoryResult` aliasing (`content`→`summary`, `conf`→
   `confidence`) has no meaning over JSON-RPC. Green returns formatted text; decide the
   text shape once and freeze it.
4. **The boot payload formatter** — `_format_boot_output()` is ~170 lines of section
   ordering, topic grouping and priority sorting. It is the single largest chunk of real
   porting work, and the one most likely to drift silently.

### Verification gate — CLOSED, verified against the live DB

The gate was: no FTS trigger definitions exist in this repo, so either `memory_fts` is
maintained DB-side (fine) or Python is somehow responsible for it (materially harder).

**It is maintained DB-side.** Three triggers on `memories`, none of them in this repo:

```sql
memories_fts_ai  AFTER INSERT ON memories
                 → INSERT INTO memory_fts (id, summary, tags)
                   VALUES (NEW.id, NEW.summary,
                           (SELECT GROUP_CONCAT(value,' ') FROM json_each(NEW.tags)))

memories_fts_au  AFTER UPDATE ON memories WHEN NEW.deleted_at IS NULL
                 → DELETE then re-INSERT that row's index entry

memories_fts_sd  AFTER UPDATE OF deleted_at ON memories
                 WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                 → DELETE FROM memory_fts WHERE id = OLD.id
```

**Green does not maintain FTS at all.** It inserts into `memories` and the index follows.
That is the write path's cheapest possible shape, and it holds.

Three further facts fell out of the probe, all of which change something:

**The tokenizer is `porter unicode61` with no `tokenchars`.**

```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
    id UNINDEXED, summary, tags, tokenize='porter unicode61')
```

This is *not* Sage's configuration. Sage uses `tokenchars '-_/+#.'`, which makes `.` and
`-` word characters and forces `fts.ts` to quote every term and prefix-wildcard the last.
Muninn's tokenizer treats them as separators, so `fts.ts` must **not** be copied across —
the escaping requirement here is `_escape_fts5_server()`'s, and it is a different problem.
Porter stemming also means green inherits stem-based matching for free, and must not
"helpfully" add wildcards that would defeat it.

**The index is healthy, and there is a real if tiny bug.** Of 2878 live memories, 0 are
missing from the index and 0 ids are duplicated — but the index carries 2880 rows. The two
extras are ghosts: entries whose memory no longer exists.

The cause is a gap in the trigger set — **there is no `AFTER DELETE` trigger.** Soft
deletes are covered by `memories_fts_sd`; a hard `DELETE FROM memories` leaves its index
row behind forever. Nothing in `remembering/scripts/` ever hard-deletes a memory, so
these two came from ad-hoc `_exec()` SQL — which makes this *latent* today and *active*
the moment `muninnd` starts pruning on a cron. Add the trigger before that Worker exists;
it is four lines and it closes the hole permanently.

**`memories_fts_au` fires on every column update, not just `summary`/`tags`.** Its `WHEN`
clause tests only `deleted_at`, so an `access_count`/`last_accessed` bump from
`_update_access_tracking()` — a *read*-path side effect — deletes and re-inserts that
row's FTS entry. The corpus has 134,924 recorded accesses across 4,862 rows, every one of
which paid for a full index round-trip on what the caller experienced as a search.
Narrowing the trigger to `AFTER UPDATE OF summary, tags ON memories` removes the churn
without changing behaviour. Worth doing before green doubles the read traffic.

Both fixes, concretely — a schema change to the live DB, so run it deliberately:

```sql
-- 1. close the hard-delete hole
CREATE TRIGGER memories_fts_ad AFTER DELETE ON memories
BEGIN
    DELETE FROM memory_fts WHERE id = OLD.id;
END;

-- 2. stop read-path access tracking from re-indexing
DROP TRIGGER memories_fts_au;
CREATE TRIGGER memories_fts_au AFTER UPDATE OF summary, tags ON memories
WHEN NEW.deleted_at IS NULL
BEGIN
    DELETE FROM memory_fts WHERE id = OLD.id;
    INSERT INTO memory_fts (id, summary, tags)
    VALUES (NEW.id, NEW.summary,
            (SELECT GROUP_CONCAT(value, ' ') FROM json_each(NEW.tags)));
END;

-- 3. sweep the two existing ghosts
DELETE FROM memory_fts
WHERE id NOT IN (SELECT id FROM memories WHERE deleted_at IS NULL);
```

Note the ordering constraint on (2): narrowing `memories_fts_au` means an `UPDATE` that
*un*-soft-deletes a row no longer re-indexes it, because `deleted_at` is no longer in the
watched column list. Nothing currently un-deletes — `forget()` is one-way — but if that
ever changes, `deleted_at` has to come back into the `OF` list or undelete stops being
searchable.

---

## 4. Blue-green, when the database cannot be duplicated

Standard blue-green stands up two full stacks and swaps traffic. That does not
translate here, and pretending it does is the way to lose memories.

**A memory database cannot be forked and merged.** Two sessions writing to two copies
diverge irreconcilably — there is no reconciliation function for "what Muninn remembers",
because the rows are not commutative: `supersede` chains, `refs` provenance edges and
`is_superseded` flags encode order.

So:

> **Data stays single-homed. Blue-green applies to the access path, not the stack.**

- **Blue** = the Python skill talking to Turso directly. Stays installed and functional
  throughout the entire migration.
- **Green** = the Worker talking to the same Turso.
- **The switch** = which path the project instructions tell the session to use.
- **Rollback** = edit the project instructions back. No deploy, no restore, seconds.

That last line is the whole reason this shape is safe. The expensive, slow, risky part
of a rollback is normally redeploying; here the fallback path is never torn down, so
reverting is a text edit.

Data rollback is the part that needs actual engineering, and it is stage 0.

---

## 5. Stages

Each stage has an entry gate, a rollback, and a bake period. Do not compress them.

### Stage 0 — Provenance (prerequisite, lands in blue)

**This must ship before green exists.** Without it, green's writes are
indistinguishable from blue's, and there is no data rollback at any later stage.

Add write provenance to `memories` and `config` — a `source` column (`skill@5.13.0`,
`mcp@0.1.0`, `muninnd@0.1.0`) or, if a schema change is unwelcome, a reserved tag
convention. A column is better: tags are user-visible and pollute recall.

- Blue writes `source` on every insert; backfill existing rows to `skill`.
- Gate: 100% of new rows carry a non-null `source` for one week.
- Rollback: drop the column. Nothing reads it yet.

**Shipped** (#98). A column, as recommended. Two details worth carrying forward: the stamp
is `<writer>@<version>` and is overridable by `MUNINN_WRITE_SOURCE`, so when the Python is
run *behind* the Worker it stamps correctly with no second code path; and pre-migration
rows are backfilled to the sentinel `skill@pre-provenance` rather than to a real version,
because asserting a version nobody can verify would make the cutover moment unqueryable —
which is the one thing the column exists to preserve.

### Stage 1 — Green built read-only, against a Turso branch

`turso db create muninn-green --from-db muninn`. Green deploys, OAuth works, and **every
write tool returns "not enabled"**.

Reuse Sage's auth wholesale: `@cloudflare/workers-oauth-provider`, the self-contained
password page from `mcp/src/mcp-oauth.ts`, `nodejs_compat`, `@libsql/client/web`.
That file is close to copy-paste.

- Gate: **the parity harness**. A frozen set of ~50 golden queries — every `recall`
  shape in `references/`, plus the boot payload — run against blue-Python and
  green-MCP, results normalized and diffed. Byte-equal on the boot payload; identical
  id-order on ranked recalls. This harness is the deliverable of this stage, more than
  the Worker is.
- Rollback: delete the branch DB.

**In progress.** `muninn-mcp` #1 landed the scaffold and a read-only `recall`. Reviewing
that port against `turso.py` turned up four divergences, and the shape of them is the
lesson worth recording — *every one is silent*. None throws; each changes which memories
come back:

| | Blue (`_fts5_search`) | Green as merged | Effect |
|---|---|---|---|
| 1 | `AND m.is_superseded = 0` | absent | green surfaces superseded memories blue never shows |
| 2 | `m.confidence >= ?` | `COALESCE(m.confidence, 0.5) >= ?` | NULL-confidence rows pass green's filter, fail blue's |
| 3 | `m.tags LIKE ? ESCAPE '\'` | `EXISTS (SELECT 1 FROM json_each(...))` | different SQL, different edge cases |
| 4 | `_retry_with_backoff` | absent | §6's cold-start 503 trap, unmitigated |

§3 predicted the *category* correctly — parity risk concentrates where a difference
changes ranked output instead of failing loudly — but located it only in
`_escape_fts5_server`, which the golden vectors had already covered. The escaping was
right; the WHERE clause was not. Generalising: **the risk is not "the hard function", it
is every predicate that silently narrows or widens the result set.** Item 3 is the honest
one — `json_each` is *better* SQL than a `LIKE` over serialized JSON, and that is exactly
why it is a bug. The porting rule has to be transcribe-don't-improve, or blue and green
drift at every point where green's author knew better.

**The harness's first live run found a bug in blue, not green.** 64 queries, 56 matched,
and the single undeclared mismatch — `recall('bluesky', n=1)` — turned out to be blue
answering the same question differently in different processes: three distinct ids across
six `PYTHONHASHSEED` values. Any query returning fewer than `expansion_threshold` rows runs
the multi-stage expansion, whose three loops iterate **sets of strings** and break early on
a `>= n * 2` budget. At `n=1` the budget is 2 and `results` already holds 1, so the first
tag visited decided the whole answer — and set iteration order over strings is randomised
per process by PEP 456. Fixed by sorting the three sets before iterating; blue now returns
the same id across all six seeds.

Two things follow, and the second is the more important one:

1. **You cannot diff against an oracle that disagrees with itself.** Blue being
   deterministic is a precondition for the parity gate meaning anything, not a nicety.
2. **§3's central claim has a boundary.** "The ranking is server-side SQL, so the port is
   tractable" is true of `_fts5_search` — green's generated SQL is byte-equal to blue's,
   verified across 7 query shapes. It stops being true at `recall()`, where Python sits
   *above* the SQL and is order-dependent. Byte-equal SQL does not imply equal results.
   The expansion layer is the part of the read path that still has to be ported carefully
   rather than transcribed.

Note also that blue's `recall` is **not side-effect-free**: it fires `_update_access_tracking`
in a background thread, which mutates `access_count`, which feeds `episodic` ranking. A
read-only green cannot reproduce that, so the harness compares an access path whose inputs
one side is still perturbing. Capture both sides close together and treat episodic id-order
as the softest of the comparisons.

### Stage 2 — Green reads promoted to the real DB

Point green at production Turso. Reads only. Both paths live; instructions still say
Python for writes.

Reads are idempotent, so this is the one genuinely free cutover — worst case green
returns something wrong and you read it, rather than something wrong and you store it.

- Gate: two weeks of real use with no ranking complaints; parity harness green on the
  production corpus (which is larger and messier than the branch).
- Rollback: stop calling the tool.

### Stage 3 — Green writes, shadowed

Enable write tools. Green writes to the real DB tagged `source=mcp`. Blue still available.

`muninnd` runs a nightly invariant check: no orphan `refs`, valid `type` on every row,
no duplicate ids, an FTS row per memory, no `is_superseded` set outside a `supersede`
call (the exact bug class that v5.7.0 fixed — see `memory.py:103`).

- Gate: 30 days, zero invariant violations attributable to `source=mcp`.
- Rollback: `UPDATE memories SET deleted_at = now WHERE source = 'mcp' AND created_at > <cutover>`.
  Bounded and precise — **only because of stage 0**. Soft delete, consistent with the
  existing `forget()` semantics, so it is itself reversible.

### Stage 4 — Cutover

Project instructions flip to MCP-first. The skill is demoted to power-use, not removed.

- Gate: none — this is the decision point.
- Rollback: revert the instructions.

### Stage 5 — Collapse the double implementation

**The stage it is tempting to skip, and the one that determines whether this was worth
doing.**

After stage 4 you own two implementations of composite scoring: the SQL in `turso.py`
and the SQL in green. They will drift. "Some aspects remain skill-shaped" quietly means
"two backends, forever" unless this stage happens.

The fix is Sage's own structure: in Sage, `tools.ts` is shared by *both* the Worker
transport and the stdio transport — one implementation, two doors. Muninn's analog:

> The Worker becomes the only thing that talks to Turso. `remembering/scripts/` is
> re-pointed at the Worker's HTTP endpoint and becomes a thin local client.

Then "skill-shaped" means *local convenience wrapper*, which is sustainable, rather
than *second backend*, which is not.

**Unresolved:** what happens to `_exec()` raw SQL. Three options, needs a decision —
(a) a `execute_sql` MCP tool gated behind a separate secret; (b) Python retains direct
Turso credentials for the power path only, accepting a narrow second door; (c) drop raw
SQL and widen the tool set to cover the analysis cases. (b) is the pragmatic default and
(a) is the clean one.

---

## 6. Inherited traps

From Sage's CLAUDE.md, the ones that transfer:

- **FTS tokenizer.** Sage uses `unicode61 tokenchars '-_/+#.'`; Muninn uses
  `porter unicode61` with no `tokenchars` (verified — see §3). Same class of failure,
  opposite configuration, so **do not port `fts.ts`** — its quoting and prefix-wildcard
  logic exists to defeat a tokenizer Muninn does not have, and applying it here would
  work against Porter stemming. Never pass raw user input to `MATCH`;
  `_escape_fts5_server()` is not optional in the port.
- **Worker-to-Worker same-zone (error 1042).** Only bites if `muninn-mcp` calls another
  Worker. It talks to Turso directly, so this should not apply — but if `muninnd` ever
  calls the MCP Worker, it needs a service binding, not a URL.
- **Secrets are per-Worker.** `TURSO_URL`, `TURSO_TOKEN`, `MCP_LOGIN_PASSWORD` set with
  `wrangler secret put` on both Workers independently.

Muninn-specific:

- **`config` rows carry `read_only` and `boot_load` flags.** Green's `config_set` must
  honour `read_only` (`config.py:283`) or the ops entries marked immutable stop being immutable.
- **Turso 503 on cold start is expected.** Green needs the same retry-with-backoff the
  Python layer has (`_retry_with_backoff`), or the first call of every idle period fails.
- **`.well-known/install-manifests.json`** and the `claude-skills` mirror workflow both
  reference the skill layout. Stage 4 has to touch them.
- **The FTS trigger set has no `AFTER DELETE`** (§3). Harmless while every deletion is
  soft, and a silent index-corruption source the moment `muninnd` prunes on a schedule.
  Fix it before that Worker ships, not after.
- **`memories_fts_au` re-indexes on any column change** (§3), so read-path access
  tracking churns the FTS index. Narrow it to `AFTER UPDATE OF summary, tags`.

---

## 7. Second track — the Worker as Muninn's identity boundary

The plan above moves *memory* off the session. The larger prize is moving **credentials**
off the session: proxy the third-party APIs through the Worker too, so the Claude.ai
project-knowledge env files stop being load-bearing.

### The rationale is partly defensive, and that argument holds

What a session is allowed to do — mount project files, reach the network from bash, receive
injected env vars, mount skills — has varied by surface (claude.ai vs Code vs Cowork) and
changed without notice. Custom MCP connectors are the most stable, most documented
extension point on offer, and consolidating on them replaces N fragile integration points
with one.

But MCP is not immune to the same churn: connector availability itself differs by surface
and plan, and OAuth dynamic client registration has had its own turbulence. **The real
insurance is not "pick MCP", it is "make transport a detail."** Sage already does this —
`mcp/src/tools.ts` is shared by both the HTTP Worker (`index.ts`) and a stdio server
(`stdio.ts`), one implementation behind two doors. Muninn should copy that structure
verbatim. Then "which connection method is allowed this month" is a deployment choice,
not a rewrite.

### The port is cheap, and the code already says so

Every credential-bearing utility is `urllib.request` + `json` over HTTPS. There is **no
filesystem access in any of them** — every `open(` in `blog_publish`, `bsky_card`,
`whtwnd` and `perch_publish` is `urllib.request.urlopen`. They are pure HTTP composition,
which maps onto Worker `fetch()` directly.

`bsky_card` is already broker-shaped: its manifest records that it takes auth as an
`auth` dict (`handle`, `did`, `access_jwt`) and reads no `BSKY_*` env vars itself. That
is the target shape for everything.

The whole credential inventory is five identities: `GH_TOKEN`/`GITHUB_TOKEN`,
`MUNINN_BSKY_HANDLE`/`MUNINN_BSKY_APP_PASSWORD` (+ `BSKY_PDS`),
`STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET`, `CF_ACCOUNT_ID`, and `TURSO_*`.

**Tier 1 — port as-is.** `gh_status`, `github_rw`, `perch_triage`, `whtwnd`, `strava`,
the `bsky_card` post path, `issue_close` (minus `flowing`). Pure `urllib` → `fetch`.

**Tier 2 — needs a decision.** `perch_publish` (Python `markdown` → `markdown-it`),
`bsky_moderation` (`ThreadPoolExecutor` → `Promise.all`), and `blog_publish`, which is
built on `flowing`'s DAG.

> `flowing` should not be ported. Its value — checkpoint resume, detached side-effects
> that don't block the main pipeline — exists because an *agent* drives the steps across
> tool calls. Inside one Worker invocation those are just function calls, and Cloudflare
> gives you the same primitives natively: `ctx.waitUntil()` is the detached leg, and
> **Cloudflare Workflows** is durable multi-step execution with resume — near 1:1 with
> `flowing`'s model. `blog_publish`'s wait-for-GH-Pages-deploy step is the case that
> proves it: polling for minutes fits a Workflow step and does not fit a plain Worker
> request. `flowing` stays local for agent-driven pipelines; it is not the Worker's model.

**Tier 3 — stays local.** The native-dependency set in §2, plus the pure-function corpus
analyzers (`correction_gate`, `satisfaction_skew`, `recall_sufficiency`, `boot_ledger`) —
these need no credentials at all, so proxying buys them nothing.

### The new engineering problem: tool budget

§2 argued memory must collapse to 8–12 tools. Adding GitHub + Bluesky + WhiteWind +
Strava on top lands at 25–30, and every schema is re-sent in every conversation on the
connector. Two mitigations, and they compose:

1. **Multiple connectors, not one server.** Split by identity tier —
   `muninn-memory` (always on), `muninn-publish` (bsky/whtwnd/blog), `muninn-github`.
   Same repo, same shared `tools.ts` core, separate endpoints registered as separate
   connectors and enabled per project. Separate tool budgets, and — see below — separate
   blast radii.
2. **A dispatcher for the long tail.** `muninn_utils/use_when.json` already exists and is
   exactly the routing metadata this needs: two tools (`list_utilities`, `call_utility`)
   expose N utilities behind one schema. Keep first-class tools for the hot path where
   the model needs to see arguments; dispatch the tail.

### The new risk: credential concentration

This must be stated plainly, because it is the real cost of the idea.

Today credentials are spread across environments and scoped per surface; leaking one
project-knowledge file is bad but bounded. Afterwards, one Worker holds GitHub write,
a Bluesky identity, WhiteWind, Strava and Turso — behind **one password on a public
`workers.dev` login page**. That is a material concentration of blast radius, and it is
strictly worse than today on that axis.

Mitigations, in order of value:

- **Split Workers by identity tier** (above). A compromise of the memory connector should
  not hand over publishing rights. This is the strongest argument for the split.
- **Cloudflare Access** in front of the Workers, rather than relying on the password page alone.
- **Fine-grained, per-repo GitHub PATs** rather than the classic coarse `ghp_` token the
  manifests currently describe as "share-by-default is intentional". That default was
  reasonable when the token lived in one session; it is not reasonable in a public endpoint.
- **Rotate on the migration.** Every credential that has ever sat in a project-knowledge
  file should be considered spent.

One genuine security *gain*, worth taking deliberately: a proxy gives a server-side audit
log. Today when Muninn posts to Bluesky or writes to a repo there is no record beyond the
target itself. Every proxied call writing a Turso row yields a ledger of what the agent
did with your identity — an instinct `boot_ledger` already has.

### This track does not need blue-green

Worth being explicit, because it is the main structural difference from §5. The staged,
provenance-gated migration exists because *memory writes are stateful* — rows persist,
order matters, mistakes compound.

Proxying `gh_status` through the Worker is **stateless**. There is nothing to roll back;
the call either worked or it didn't, and the side effects live in GitHub or Bluesky where
they were always going to live. So this track moves per-utility, fast, with rollback =
"call the Python again."

**Do not couple the two tracks.** The proxy work is cheaper and lower-risk than the memory
migration, and gating it behind stage 3 of §5 would waste months. Run them in parallel;
the only shared dependency is the OAuth/transport scaffolding in stage 1.

---

## 8. Progressive disclosure — resources instead of schemas

Tool *count* is the obvious budget. Tool *width* is the bigger one, and it is where
progressive disclosure pays.

`recall()` takes **19 parameters** (`search`, `query`, `n`, `tags`, `type`, `conf`,
`tag_mode`, `strict`, `session_id`, `auto_strengthen`, `raw`, `expansion_threshold`,
`fetch_all`, `since`, `until`, `tags_all`, `tags_any`, `episodic`, `exploration`).
Rendered as JSON Schema with honest descriptions that is roughly 2k tokens **for one
tool**. Ten tools at that width consume the entire budget before a conversation starts.

### The layering

**Layer 0 — always in context.** A deliberately small tool set with deliberately narrow
schemas. `recall` exposes the four arguments that account for nearly all calls
(`query`, `n`, `tags`, `type`) plus an opaque `filters` object; the other fifteen
parameters are documented in a resource, not in the schema. 19 → 5.

**Layer 1 — resources, read on demand.**

| URI | Content | Already exists as |
|---|---|---|
| `muninn://reference/recall` | The full parameter set, semantics, edge cases | `references/CLAUDE.md`, `references/advanced-operations.md` |
| `muninn://reference/types` | Memory types + per-type defaults | `SKILL.md` type table |
| `muninn://reference/vocabulary` | Recall vocabulary / tag conventions | `references/` |
| `muninn://utilities` | Routing index — which utility for which task shape | `muninn_utils/use_when.json` |
| `muninn://utilities/{name}` | Per-utility goal, inputs, outputs, errors, example | `manifests/*/*.v0.4.json` → `actions[].docs` |
| `muninn://boot` | The composed boot payload | `_format_boot_output()` |

**Layer 2 — the dispatcher.** `call_utility(name, args)` carries a generic schema; its
arguments are described by `muninn://utilities/{name}`, fetched only when that utility is
actually wanted.

### This is mostly serialization, not new work

The deferred layer already exists, in three places:

- **Manifest v0.4 `actions[].docs`** is already a deferred tool schema in all but name —
  `goal`, `inputs_brief`, `outputs_brief`, `errors_brief`, `example`. That block was
  written for a human-facing install manifest and happens to be exactly the right payload.
- **`use_when.json`** is already the routing index.
- **`references/` (~33KB)** is already the on-demand reference layer, and `SKILL.md`
  already opens with "Basic patterns are in project instructions. This skill covers
  advanced features" — Muninn *already practises PD in skill-land*. The MCP design should
  mirror the structure that exists rather than invent a second one.

### Four caveats, because PD has real failure modes

1. **PD trades a fixed cost for a variable cost plus a round trip.** That is a good trade
   when N is large and usage is sparse. It is a *bad* trade on the hot path: `recall` and
   `remember` are called in nearly every conversation, and making them require a resource
   read first is a regression wearing PD's clothes. Hot path keeps real, if narrow,
   schemas. Dispatch only the tail.

2. **Resource auto-read is not guaranteed, and varies by exactly the surfaces §7 is
   worried about.** In Claude Code it works well — the harness exposes generic
   `ListMcpResourcesTool` / `ReadMcpResourceTool`, so *two* schemas cover every resource
   on every connected server, which is the whole PD win made concrete. claude.ai
   connectors have historically surfaced resources as user-attachable content rather than
   something the model reads autonomously. Since cross-surface robustness is the entire
   argument for §7, the action path must not depend on resource support.
   **Mitigation — the same one as §7: same content, two doors.** Ship a `muninn_docs(topic)`
   tool with a three-line schema returning exactly what the resource returns. Clients with
   native resource support use the resource; clients without use the tool. One
   implementation.

3. **A resource nobody reads is dead weight.** The pointer has to live somewhere
   always-in-context, which means one sentence inside each thin tool description
   ("full parameter list: `muninn://reference/recall`"). That sentence is the one piece
   of schema text that cannot be economised, and forgetting it is the classic PD failure:
   immaculate deferred documentation that never gets loaded.

4. **Discovery round-trips compound.** `list` → `read` → `call` is three round trips for a
   tail utility, against one Python import today. Fine for rare operations; another reason
   the hot path stays wide.

### Two protocol options considered and not recommended

- **`notifications/tools/list_changed`** allows a server to advertise a minimal tool set
  and expand it contextually. Client support is uneven and mid-conversation tool churn is
  disruptive. Available if the budget genuinely cannot be met otherwise; not a starting point.
- **MCP prompts** as boot's home. Prompts are *user*-invoked, so boot could not fire
  automatically — which is the property boot most needs. Tool + resource is the right pair.

---

## 9. Decisions needed

1. ~~**Provenance mechanism** — `source` column vs. reserved tag.~~ *Resolved: column, shipped in #98.*
2. **Auth** — reuse Sage's password-page OAuth, or a static bearer token? claude.ai
   custom connectors require OAuth; a bearer token only works for programmatic clients.
   (Recommend: OAuth, copied from Sage.)
3. **One Worker or two?** `muninn-mcp` + `muninnd` separately, as Sage does, or a single
   Worker with a cron trigger. (Recommend: two — different failure modes, different
   deploy cadence, and the cron half should never be able to break the interactive half.)
4. **Tool collapse** — which 8–12 tools. Needs a concrete list before implementation.
5. **`_exec()` fate** at stage 5 (§5).
6. **Does `boot` belong as an MCP tool or an MCP resource?** *Resolved by §8: both.*
   Expose `muninn://boot` for clients that attach resources and a `boot` tool for those
   that don't — same function, two doors. The tool is what project instructions call, so
   boot never depends on client resource behaviour.

On the proxy track (§7):

7. **How many connectors?** One server, or split by identity tier
   (`muninn-memory` / `muninn-publish` / `muninn-github`). (Recommend: split — it solves
   the tool budget and the blast radius with the same move.)
8. **Dispatcher or first-class tools for the long tail** — `use_when.json` can back a
   `list_utilities` + `call_utility` pair. (Recommend: both — first-class for the hot
   path, dispatch the tail.)
9. **`blog_publish`: Cloudflare Workflows, or leave it local?** It is the only utility
   whose shape genuinely needs durable multi-step execution. Leaving it local is a
   legitimate answer; it is also the one that most wants a Workflow.
10. **Credential rotation and scope.** Every secret that has lived in a project-knowledge
    file should be rotated during this migration, and the coarse `GH_TOKEN` shared across
    `blog_publish`/`issue_close`/`perch_triage`/`verify_patch` should become fine-grained
    per-repo PATs before it sits behind a public endpoint.
11. **Cloudflare Access in front of the Workers, or password page only?**

On progressive disclosure (§8):

12. **Which four `recall` arguments are first-class**, and does the rest go in an opaque
    `filters` object or stay unavailable over MCP entirely? Needs a look at real call
    frequency, not intuition.
13. **Are the manifests the resource payload, or a build input?** `actions[].docs` is the
    right content, but manifests are versioned per-utility (v0.3 and v0.4 both present).
    Serving them directly couples the resource layer to manifest versioning; generating
    resources from them at build time decouples it.
14. **Does the `muninn_docs` fallback tool ship from day one**, or only if claude.ai's
    resource support proves inadequate? (Recommend: day one — it is a three-line schema
    and it is the thing that makes the design surface-independent.)
