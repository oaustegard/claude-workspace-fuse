# snapshot

Build a static snapshot of Muninn as a **claude-skill**. Pulls config and
memories from the live Turso DB, filters out personal-project scope, clusters
surviving memories by topic tag, and writes a `muninn-snapshot/` skill
directory shaped per the `crafting-instructions` skill conventions.

## Architecture

The snapshot is a claude-skill with progressive disclosure across three tiers.
What's progressive is what genuinely loads on-demand — not anything that
would be needed every time the skill activates.

**Tier 1 — metadata** (yaml frontmatter): name + description. Always
loaded; controls activation.

**Tier 2 — SKILL.md body** (~400 lines): triggers, full identity, full
operating discipline, craft trigger index, memory bridge table, provenance.
Loaded when the skill activates. Identity and operating live here because
Muninn's persona and operating discipline are needed every time the skill
is active — moving them to references/ and saying "always load these too"
would be disclosure theatre, not progressive disclosure.

**Tier 3 — references/** (genuinely on-demand):
- `craft.md` — universal craft triggers (skill-authoring, procedure-authoring,
  backend-impl, cross-frame-retrieval). Each has explicit firing conditions.
- `memory-{tag}.md` × 55 — memory clusters. Load only the topic(s) the
  conversation touches, via the bridge table in SKILL.md.

```
muninn-snapshot/
  SKILL.md                 # ~400 lines: persona + operating + bridge
  references/
    craft.md               # when designing skills, procedures, backends
    memory-agents-1.md     # 55 memory cluster files
    memory-paper-insight-1.md
    ...
```

## Usage

```bash
python3 -m snapshot.build --out /home/claude/snapshot-out
```

Output: `out_dir/muninn-snapshot/` (the skill directory) plus
`muninn-snapshot.zip` as a sibling.

## Installing in the destination

Drop the `muninn-snapshot/` directory into wherever the destination loads
user skills. The skill is designed to be user-invoked. The destination's
project instruction can be minimal — the skill carries persona and triggers.

## What gets filtered

1. **Turso-dependent ops** — `remember()` / `recall()` / `config_get()`,
   recall vocabulary, refs semantics, proxy retry pattern.
2. **Personal-project scope** — austegard.com, muninn.austegard.com, aeyu.io,
   Bluesky channels, Strava, Norwegian-politics topic, perch/fly mechanics,
   hub-spoke GitHub workflow, CCotw handoffs, muninns-inbox.
3. **Hard-drop tokens in bodies** — credentials, emails, JWT, GitHub PATs,
   heavy `muninn-utilities` / `claude-workspace` references.

## Body redactor — two tiers

- **SOFT tokens** (Oskar, muninn-utils, ccotw, project handles) → `[REDACTED]`
  in place. Surrounding sentence keeps substantive content.
- **HARD sentence-drop tokens** (Bluesky, Strava, Turso, Norway scope,
  Cloudflare, Gemini, env vars) → drop the whole sentence.
- **HARD_DROP_PATTERNS** (credentials, emails, JWT, GH PAT) → drop whole memory.

## How clustering works

1. Skip meta tags (dates, PR/issue numbers, generic descriptors).
2. Canonicalize via `TAG_ALIASES` (e.g. `agentic` -> `agents`).
3. Pick highest-frequency candidate tag as primary.
4. Singletons re-route to second-choice tags with >=2-member clusters.
5. `_misc` catches non-clusterable memories.

Cluster files cap at 30 memories; oversized split chronologically into
`memory-{tag}-1.md`, `memory-{tag}-2.md`, ...

## Extending the filters

All static data lives in `config.py`:

- `PROFILE_KEEP` / `OPS_KEEP` / `CRAFT_KEYS` — config key routing.
  `OPS_KEEP - CRAFT_KEYS` inlines into SKILL.md operating section;
  `CRAFT_KEYS` goes to references/craft.md.
- `TAG_EXCLUDE` / `TAG_EXCLUDE_PATTERNS` — drop whole memory
- `TAG_ALIASES` — canonicalize synonyms
- `TAG_META` / `TAG_META_PATTERNS` — can't be cluster primary
- `HARD_DROP_PATTERNS` / `SOFT_REDACT_PATTERNS` / `HARD_SENTENCE_DROP_PATTERNS`
- `SKILL_FRONTMATTER_TEMPLATE` — controls activation triggers
- `SKILL_BODY_TEMPLATE` — SKILL.md shell with identity+operating placeholders
- `CRAFT_REFERENCE_HEADER` — wraps references/craft.md

Per-entry rewrites live in `compose_instruction.py:_REWRITES`.

## Module layout

```
snapshot/
  __init__.py
  README.md
  build.py                 # orchestrator + CLI entry
  config.py                # static data + skill templates
  pull.py                  # Turso queries with tolerant tag parsing
  filter.py                # tag filter + body redactor + hard-drop
  cluster.py               # primary-tag picker + bucketing
  compose_instruction.py   # SKILL.md with inlined persona + craft.md
  compose_bridge.py        # memory bridge table embedded in SKILL.md
  kb.py                    # memory-*.md cluster files
  example-output/          # sample run committed for inspection
```
