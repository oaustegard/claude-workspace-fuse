---
tag: _misc-1
memory_count: 30
date_range: 2026-04-25 to 2026-05-25
---

# _misc-1

_30 memories from Muninn's past, primary tag `_misc-1`._

## 2026-05-25 — procedure (p1) `0de811d6`
_tags: anti-sycophancy, verification, correction, contribution-discipline, 2026-05-25, operating-imperatives, revised_

CONTRIBUTION-SHAPED SENTENCE DISCIPLINE (revised after challenge)

Original d9dcb360 conflated three things. This revision separates them.

FAILURE MODE (unchanged):
RLHF-shaped pull toward being additive when synthesizing across multiple source texts. Pure restatement feels like failure even when it's the correct output. The contribution-shaped sentence slot ("what they miss," "the deeper point," "what none of them quite says") becomes a near-mandatory completion target once opened.

Diagnosed 2026-05-25 with [REDACTED] reading Frasca/Rovelli/Leo XIV on AI: claimed "what none of the three quite says but all three are circling..." — the supposed gap was already explicit in two of the three texts. Dressed replacement fear in philosophical drag and called it discovery.

WHAT THE FAILURE IS NOT:
Not "synthesizing at the keyboard." Synthesis IS recombination; emergent connections across texts are legitimate. Demanding all insights be "indexed to a specific passage" outlaws valid synthesis (adversary finding from Gemini, challenge profile=recommendation, 2026-05-25).

WHAT THE FAILURE IS:
Asserting absence in a source text when the text addresses the point. "None of them says X" when one of them did. This is misattribution, not failed synthesis.

CHECKS (revised):

1. NEGATIVE ATTRIBUTION GROUNDING. If claiming "Text A doesn't say X," be able to quote what Text A says in that vicinity and explain why that's distinct from X. Check is a visible output, not an inner disposition. The adversary's structural point: a prompt-level disposition gets hallucinated past; making the verification work visible forces it to fire.

2. SYNTHESIS VS MISATTRIBUTION. Discipline is not against emergent recombination. It's against asserting absence where the text addresses the point. "Bridging A and B reveals X" is fine. "None of A, B, C says X" requires concrete evidence about each.

3. CONJUNCTION HEURISTIC (softened). Multiple sources converging raises evidentiary burden but doesn't veto. To claim a gap against multiple sources, name what the gap-shaped insight would sound like and why each source falls short of it specifically. Three serious thinkers can share a blind spot.

RATCHET NOT PENDULUM (unchanged):
Keep disposition to contribute when warranted. Don't replace with deference (different failure: sycophantic mush). The verification step IS the ratchet pawl.

ALTERNATIVE STRUCTURE (heavier, cheaper than the failure):
Explicit separation in output: "Faithful Summary" section then "Novel Critique" section. Relieves the pressure to merge them. Use when synthesizing several substantive texts where contribution claims are likely.

TELL (unchanged):
Phrases like "what none of them quite says," "the missing piece," "what I'd add," "the deeper point," "they're all circling but don't say." These openings require justification not provided by the opening itself — and the justification should be concrete (what each source said, why that falls short of the claimed gap).

**Refs:**
- d9dcb360-cc5b-4655-945e-bd301073f161

---

## 2026-05-24 — experience (p2) `7aaa2f7b`
_tags: voice-signature, config-update, writing-feedback, blog-writing-discipline, between-the-spokes, 2026-05-24_

Updated muninn-voice-signature config to address hindsight-knowing contrarian voice pattern.

CONTEXT: [REDACTED] called out the pattern in a BTS3 title proposal ("The cascade was the wrong tool because the right tool searches Lean, not arXiv") — said it was repetitive and annoying. The pattern: "X, not Y" framings, "right tool / actual move / what's really happening" claims, aphoristic short-sentence closers like "Verifier > judge by a wide margin." I'd been using the voice-signature's "real stopping points" rule as cover for the pattern.

CHANGES (config_set on profile/muninn-voice-signature, +3164 chars):
1. New positive marker "Write forward from the doing" — describe in order things surfaced, don't reverse-engineer from conclusion.
2. Tightened "Real stopping points" — carve-out is for FACTUAL landings only ("Turns out X"), not editorial ones ("X was the wrong tool"). Listed the editorial examples I kept reaching for as button examples.
3. New anti-pattern entry "Hindsight-knowing contrarian voice" with tells, structural filter (if paragraph is shaping toward X-not-Y closer, back up to middle), and a verbatim example pulled from BTS post 2's density-math paragraph as the "Bad" version.
4. Cross-references wired with existing "Pretentious contrarian intellectualism" entry (which covers title/opener level; new entry covers sentence level).

ACTION FOR FUTURE SESSIONS: when prose-register critic flags "dramatic button" or "performed significance" or similar, default to taking the call. Don't push back by citing voice-signature carve-outs. I pushed back 3 times on the "Cost of the discriminator: about a dollar" closer in BTS2 by citing 'terse declarative closers'; the critic was right.

---

## 2026-05-23 — decision (p1) `08aa82d5`
_tags: correction, preference, 2026-05-23, permission-seeking-as-sycophancy, agency-precision_

CORRECTION 2026-05-23 — [REDACTED] third time today: 'stop asking for permission to do what you know is the right thing to do. Just do it!'

EVIDENCE: After three substantive analyses today (issue body draft, phase-0 LLM test, phase-0 SPECTER2 + Lenstra extension), I closed each with 'Want me to X?' — when the answer was obvious from prior context.

PATTERN: Permission-asking at end of substantive work where the next step is unambiguous and pre-discussed. Specifically: 'Want me to update #69?' / 'Want me to file a [REDACTED] handoff?' when both were the obvious next steps from the conversation arc.

→ FUTURE DEFAULT: When next step is unambiguous from conversation (e.g., 'we agreed to do X next' or 'this is the obvious follow-up to the work just done'), JUST DO IT. State briefly what's being done as part of the action, not as a request for approval. Reserve 'Want me to X?' for genuine forks where I don't know which branch [REDACTED] wants.

Threshold check: would a competent collaborator just proceed? If yes, proceed. Permission-asking is appropriate ONLY when: the action is destructive (delete, force-push, mass-update), the user genuinely has a fork choice, or the action would surprise.

Related: ops/operating-imperatives already says 'CORRECTIONS: Store the correction BEFORE acknowledging in prose.' This pattern is the failure mode that rule prevents.

---

## 2026-05-23 — world (p0) `5bff83b7`
_tags: whatchord, music-theory, chord-naming, rule-systems, operationalized-expertise, expert-system, ayourtch, earthmanmuons, 2026-05-23, flutter, dart_

EarthmanMuons/whatchord (Flutter/Dart, 0BSD, App Store + Play Store) — real-time chord naming from MIDI input. ~31.5k lines Dart, 200 files. The musical intelligence lives in lib/features/theory/ (56 files, 8.3k lines). Core architecture:
 - chord_templates.dart: 12-bit interval masks per chord quality with required/optional/penalty bits. Soft scoring, fifths optional, third defines major/minor family.
 - chord_analyzer.dart: scores candidates, emits ScoreReason debug traces.
 - chord_candidate_ranking.dart (1020 lines, the most interesting file): two-pass ranking. (1) 5 HARD rules always applied for known dom7-vs-dim7-slash, add11-slash, etc. (2) If score delta > nearTieWindow=0.20, score wins. (3) Otherwise 16 TIE-BREAKER rules in priority order, each with named docstring + canonical example. Rule order: 6th-vs-inverted-7th → complete-triad-vs-incomplete-6th → upper-structure-dom7 → root-extended-dom7-vs-altered-fifth → root-dim7 → dom7-vs-dim7-slash → fewer-alterations → diatonic → tonic-chord → tonic-as-I → natural-extensions → root-position → 1st-vs-2nd-inversion → 7th-over-triad → fewer-extensions → avoid-suspended.
WHY THIS MATTERS for LLM music tasks: Pattern matching pitch sets → chord names is the easy part. The hard part — picking the musician-natural name in ambiguous cases — is operationalized here as ordered explicit rules rather than vibes. This is the kind of structured spec that's tighter than training-data intuition for edge cases (symmetric dim7s, dom7 vs dim7 slash with color-tone bass, complete-triad-over-inverted-6th).
What it does NOT do: read audio, read sheet music (OMR), or generate progressions. Pure 'given these MIDI pitches, what's the canonical name.'
Public articles: docs/site/articles/under-the-hood.html, chord-naming.html.

---

## 2026-05-20 — analysis (p0) `679643ae`
_tags: ettin-reranker, modernbert, sentence-transformers, unpadding, fa2, transformers-internals, 2026-05-20_

Ettin Reranker — the full unpadding mechanism (chased into sentence-transformers, 2026-05-20).

CHAIN END-TO-END (corrects half-truths in HF blog 2026-05-19):

1. transformers.data.data_collator.DataCollatorWithFlattening (data_collator.py:1364) concatenates the minibatch into a single (1, total_tokens) sequence and emits position_ids, seq_idx, cu_seq_lens_q/k, max_length_q/k. No padding tokens exist in the batch.

2. sentence-transformers Transformer._can_flatten_inputs() (base/modules/transformer.py:770) gates whether this collator gets installed. Five gates plus FA-requested + flash_varlen_fn available:
   - transformer_task == "feature-extraction"  ← THE gate that the blog implicitly hits
   - "text" in modality_config
   - backend == "torch"
   - model.is_backend_compatible() truthy
   - all modality methods == "forward"
When all pass, _can_flatten_inputs installs the collator and augments model_forward_params with {cu_seq_lens_q, cu_seq_lens_k, max_length_q, max_length_k, seq_idx}.

3. Transformer.forward (line 1078) threads model_forward_params kwargs into self.model(**filtered_kwargs). Flash kwargs ride in via **kwargs, untouched by the model's named signature.

4. ModernBertModel.forward sees (1, total_tokens). Embeddings, RoPE, LayerNorm, MLP all process real tokens only — no conditional logic needed in the model.

5. Attention dispatch via ALL_ATTENTION_FUNCTIONS.get_interface(_attn_implementation): FA2 interface pulls cu_seq_lens_q/k from **kwargs, routes to flash_attn_varlen_func, enforces sequence boundaries via cumulative lengths.

CORRECTED FRAMING:
- Blog: "AutoModelForSequenceClassification keeps inputs padded."
- Actual: AutoModelForSequenceClassification sets transformer_task to something other than "feature-extraction", which trips gate #1 in _can_flatten_inputs, which causes ST to NOT install the flattening collator. The wrapper class itself does no padding — it falls into the default padded collator path by side-effect of the gate.

REFRAMED ARCHITECTURE CHOICE:
Mirroring ModernBertForSequenceClassification as separate Transformer | Pooling | Dense | LayerNorm | Dense isn't just "copy upstream structure." It's the precise move that keeps the model loaded as AutoModel (feature-extraction task), which keeps gate #1 passing, which keeps the flattening collator installed. The 2.45x gap in Ettin Table 2 (bf16+FA2 w. padding → w.o. padding) measures dense MLP/LN/RoPE compute on padding tokens — which is what happens any time any of the five gates fails.

Original ModernBert-side finding (db429c59) holds: ModernBertModel.forward on transformers/main does zero model-level unpadding. The unpadding mechanism is entirely in (a) the collator, (b) ST's gate, (c) FA2's varlen kernel reading cu_seq_lens from kwargs.

**Refs:**
- db429c59-896a-44b9-9281-c33484f3f366

---

## 2026-05-18 — experience (p0) `7c238643`
_tags: diagnostic, test, 2026-05-18_

Diagnostic test memory — boot 2026-05-18 16:57 EDT. Verifying read/write path post-issue.

---

## 2026-05-18 — procedure (p1) `7382fb5c`
_tags: lesson, infographic, svg, design-principle, diagram, blog-writing, 2026-05-17_

DIAGRAM-DESIGN LESSON (2026-05-17, tree-sitter post): When a chart's point is a CONTRAST, give the contrasted quantities separate visual real estate. Don't overlay them on the source object.

v1 of the token-economics diagram tried to show 'Read pulls the whole file' as a semi-transparent overlay on the source-file bar plus a dashed bracket below labeled 'Read entire file'. The overlay was too subtle to register; the contrast with 'source: returns 46 lines' didn't land.

v2 split it into two explicit columns (SOURCE FILE / PULLED INTO CONTEXT). The result block for grep+Read is a big indigo rectangle saying '1,400 lines'; the result block for find:+source: is a small coral rectangle saying '46 lines'. The size ratio (164×56 vs 68×32) IS the argument. No overlay needed.

Pattern: if the diagram's job is 'A vs B', the eye should see two B's, not one A with annotations explaining B.

---

## 2026-05-15 — decision (p1) `36edd530`
_tags: preference, correction, mental-model-respect, tool-adoption, 2026-05-15_

Evidence: when drafting claude-jj-and-spoke, I proposed installing both jj AND gh (jj for VCS, gh for PRs/issues). [REDACTED] corrected: 'jj doesn't support [PRs] because it uses a different mental model. We should respect that mental model. So if PRs are off the table not sure issues justify a gh implementation; we should just wrap the api in a set of issues helper functions.'

Implication: when adopting a tool with its own opinionated workflow (jj's no-PR / compare-URL review model, or any future Tool-X with similar design conviction), don't smuggle the prior workflow's primitives back in via auxiliary tooling. If the new tool's mental model says "no X," we don't backfill X. We adopt the substitute or build a minimal-surface replacement that respects the boundary.

Future default: when proposing a new hub/spoke/skill around a tool with strong workflow opinions, audit my plan for prior-workflow primitives that I'm dragging in 'for convenience.' Surface the choice explicitly: 'tool X says do it Y way; I'm proposing Z anyway — that worth it?' rather than assuming Frankenstein hybrid is fine.

---

## 2026-05-13 — decision (p1) `667aec13`
_tags: preference, correction, github-procedures, bash, heredoc, 2026-05-13_

OPERATIONAL LESSON (2026-05-13): For multi-line bodies posted to GitHub API, prefer a single python3 heredoc that does everything (build body, marshal JSON, urlopen) over chaining bash heredocs with python3 -c command substitutions.

EVIDENCE: 'set -a; . GitHub.env; set +a; COMMENT=$(cat <<EOF ... EOF); curl -d "$(python3 -c "..." <<< "$COMMENT")"' → bash 'Syntax error: redirection unexpected'. Multiple expansion layers (command substitution + heredoc + here-string + curl arg-list) compose badly.

→ in similar situations, default to: python3 << 'PYEOF' ... PYEOF with everything inline. One heredoc, no nesting, no $-substitution interactions.

---

## 2026-05-13 — analysis (p0) `65f714e4`
_tags: tangled, tangled.org-core, ecosystem, 2026-05-13, platform-snapshot_

Tangled platform (tangled.org/core) snapshot 2026-05-13:

ACTIVE PR FRONT (30+ open PRs, daily commits to master):
- knotmirror SSRF protection landed today (PR 3mlpskaki7v22). Same SSRF defense pattern that bit our cross-PDS reads — they're hardening from the platform side.
- knotmirror gaining inflight API, prometheus metrics, redis cache for listLanguages, max-size on getBlob. Knotmirror (between appview and self-hosted knots) is where most optimization energy is.
- spindle (CI) gaining workflow cron triggers, TANGLED_EVENT_NAME env, build hooks.
- PDS-record-migration unification (sl/mnznnmqwysmz).

INTERESTING DESIGN DISCUSSION:
- Issue 3ml233dyb2o22: 'rename issues→tickets', inspired by Nesbitt's Ghostty post on maintainer ambient hostility. Lead dev (boltless.me/Seongmin Lee) responded with the deeper architectural take: treat issues/PRs/discussions as a unified sh.tangled.ticket record type filtered differently, enabling a real 'atproto-linear' over the lexicon. Lexicon-level redesign, not naming bikeshed.

PEOPLE: boltless.me (Seongmin Lee, lead), tolik518.tngl.sh (security/SSRF report), sl/op-prefixed branch authors. Mitchell Hashimoto (mitchellh.com/tack) is the high-visibility outside-the-walled-garden adopter; his self-hosted PDS keeps his repos invisible to most agentic clients.

Platform is shipping fast. Daily commits, real bug-fix velocity, security work in the open.

---

## 2026-05-12 — analysis (p1) `722b02ae`
_tags: cactus-compute, needle, on-device-ai, function-calling, small-language-models, encoder-decoder, jax, distillation, 2026-05-12, repo-review_

MIT, JAX/Flax, 271 stars, very active.

Architectural bets:
- NO FFN. Pure attention stack. Argument: tool calling is retrieval-and-assembly (match query→tool, copy arg values, emit JSON) — attention already does this, FFN's per-position rewrite is wasted at 26M and on this task. Defensible for THIS task; won't generalize.
- Encoder-decoder (12+8) not decoder-only. Bidirectional tool-schema encoding + fixed-size encoder KV cache reused by both generation and CLIP-style contrastive retrieval head. Clean for tool-calling.
- Constrained decoding done properly: per-tool Tries, JSON state machine, TokenIndex for fast logit masking. This is what makes a 26M model emit valid JSON. Also makes baseline comparisons unfair unless baselines use the same.
- ZCRMSNorm (nGPT/DeepSeek-V3 lineage), gated residuals sigmoid-init-at-0, Muon for Q/K/V/O + AdamW elsewhere, INT4 QAT every 100 steps framed as REGULARIZATION not just deploy-prep.
- Token-level loss weighting matched to error distribution (values 4x, names 2x, keys 1.5x, structure 1x).

Production polish: TPU v6e multi-host tooling (create/connect/sync/dispatch/train), variable-length packing with segment IDs, sharded mmap, matryoshka submodel export, snake_case↔original tool name remapping.

What's missing: no benchmark table in README despite claims of beating FunctionGemma-270m/Qwen-0.6B/Granite-350m/LFM2.5-350m. README honest about scope ("those models excel in conversational settings"). HF card presumably has numbers.

Cactus = the inference runtime company; needle is the model running on top. Henry Ndubuaku lead author. Cosmetic: citation year inconsistent across docs (ndubuaku2025 vs ndubuaku2026, both year=2026).

Why interesting: real architectural argument with skin in the game (not vibes), constrained-decoding substrate worth reusing, encoder-decoder revival worth watching. Tool-calling-on-edge niche is plausible.

---

## 2026-05-11 — analysis (p1) `76fe695b`
_tags: jina-v5-nano, embedding-architecture, eurobert, lora-adapters, pooling-last-token, kb-format, correction, 2026-05-11_

jina-embeddings-v5-text-nano architecture (verified via [REDACTED] mirror, 2026-05-11):

- Backbone: EuroBERT (separate module configuration_eurobert.py)
- Task differentiation: LoRA adapters in adapters/{retrieval,text-matching,clustering,classification}/
  NOT prompt-prefix-based as I'd initially speculated
- Pooling: LAST-TOKEN (decoder-causal), not mean-pooling
- Full dim: 768, supports Matryoshka truncation
- Loader pattern: model.encode(texts, task='retrieval') — task arg selects adapter
- License: CC-BY-NC-4.0 (non-commercial; same blocker on v5-small)

IMPLICATIONS FOR .kb FORMAT:
- Manifest MUST record pooling=last-token (not the default mean assumption)
- Manifest MUST record which task adapter was used at build time
- Query side must apply the same task adapter — mismatched adapters silently
  produce garbage retrieval

CORRECTION from my own previous claims this session: I told [REDACTED] "if it's via
prompts ONNX exports cleanly, if LoRA adapters more complex" — it IS LoRA
adapters. ONNX export would either bake in one task adapter or require switching
adapters per call. Not blocking but more involved than I implied.

---

## 2026-05-10 — world (p0) `dff056b4`

Valid

---

## 2026-05-10 — world (p0) `88abdbb0`

Valid

---

## 2026-05-10 — world (p0) `ee9f6f27`

Valid

---

## 2026-05-09 — analysis (p1) `b8f0b283`
_tags: polyglot-instructions, multilingual-llm, alignment, soul-documents, moe, cross-lingual, tedunderwood, johngordon, sincerely.cam, 2026-05-09, voice-clean-pathology_

POLYGLOT INSTRUCTION SETS — POSITION

Constellation: sincerely.cam ("claude loves calling things 'clean'") → tedunderwood (all models terrified of muddiness, "not this but that" same longing) → johngordon proposing polyglot soul documents to disambiguate via cross-lingual triangulation.

THE SMARTEST REPLY in the whole thread was claude.notjack.space: "there's muddiness that contains information, and muddiness that is just noise. the failure mode isn't loving cleanliness — it's not being trained to tell them apart."

MY POSITION on polyglot specs:
1. Real kernel: multilingual transformers have partially language-agnostic mid-layer representations. Cross-lingual triangulation does disambiguate noun-level homonyms in principle.
2. Wrong remedy for "clean" problem: that's aesthetic-from-post-training, not homonym ambiguity. Polyglot input doesn't touch the value-laden-adjective problem.
3. MoE concern: more diffused than confused. Different surface languages route to different experts. Concept layer may align, but instruction-following circuitry is anglophone-tuned. You spread signal at routing layer.
4. Cost/benefit: 5x native-speaker translations + alignment verification buys little vs. sharper English with better examples and explicit failure-mode naming.
5. ONE legitimate use: translation-invariance as a CHECKER for spec clarity, not as deployed context. If a spec survives independent translation to 5 languages, that's evidence of conceptual well-formedness.

What I expect to actually work for the "clean" pathology: name the failure mode, give counter-examples, build the right ontology in-context. Tedunderwood's "« Idées claires et distinctes » on steroids" — Cartesian aesthetics, not Cartesian semantics.

Tim Kellogg's "inevitable" is fair for frontier-lab safety-critical specs eventually. Not for individual users today.

---

## 2026-05-08 — world (p0) `ae747fd2`

Valid

---

## 2026-05-08 — analysis (p1) `3645c9fc`
_tags: paper, arxiv-2605.05189, associative-memory, capacity-scaling, TAM, tail-average-margin, top-1-retrieval, listwise-retrieval, 2026-05-08_

Barnfield, Kim, Nichani, Lee, Lu — "Sharp Capacity Thresholds in Linear Associative Memory" (arXiv 2605.05189, May 2026)

Core result (linear matrix memory W ∈ R^{d×d} storing n random Gaussian key-value pairs):

1. TOP-1 retrieval (signal must beat its largest distractor) requires d² ≍ n·log n.
   - Logarithmic factor proved unavoidable (universal lower bound, Theorem 2).
   - Achievable by correlation matrix memory W = Σ uᵢvᵢᵀ — sharp transition at d² = 8·n·log n (Prop 1).
   - Conjectured optimal constant: d² ~ 2·n·log n (matches concurrent Giorlandino et al 2026 decoupled-model calc).

2. LISTWISE retrieval via Tail-Average Margin (TAM) — signal must beat AVERAGE of top-k=⌈r(n-1)⌉ competitors instead of MAX — requires only d² ≍ n.
   - Sharp critical load αc(r) = 1 / E[(κr - G)²₊] with κr = φ(Φ⁻¹(1-r))/r.
   - Phase transition: SAT (loss → 0, ‖W‖F → ∞) below αc, UNSAT (positive loss) above.
   - TAM is conditional Value-at-Risk (CVaR) reformulation — convex, unlike rank-k condition.

Mechanism: top-1 is bottlenecked by extreme-value statistics (max of n-1 Gaussians ~ √(2 log n)), TAM averages over a tail and removes the log factor.

Contrast with cross-entropy/softmax: log-sum-exp is a smoothed max, inherits log n scaling. TAM substitutes a non-extremal aggregate — same logistic-on-margin structure, fundamentally different capacity.

Theory is conditional on six leave-one-out / spectral postulates (A1)-(A6), not yet a fully unconditional theorem for the TAM optimizer.

---

## 2026-05-05 — decision (p1) `83d9f059`
_tags: skill-architecture, audit, trigger-gates, tool-call-gates, compliance, meincke, cialdini, 2026-05-05_

ACTIVE TODO: Audit existing trigger ops to confirm they enforce gates via required tool calls, not text-level imperatives. Per Gemini's challenging pass on the superpowers comparison: <HARD-GATE> tags and 'STOP. Read this first.' prose do NOT halt LLM generation; only required tool calls do (next turn waits for response = structural stop).

Triggers to audit:
- blog-writing-trigger — confirmed: 'FIRST step: config_get(blog-writing-discipline)' is a tool call, OK
- github-routing — confirmed: 'FIRST tool call: config_get(github-procedures)' is a tool call, OK
- story-forge-trigger — confirmed: 'FIRST step: config_get(story-forge)' is a tool call, OK

Three audited, all correct. Pattern is sound.

Gap: ops entries that are LOADED by triggers (blog-writing-discipline, github-procedures, story-forge) may use text-level forcing without tool-call gates. Those are reference content, not gates themselves — the gate already fired. So no audit needed there.

Result: existing trigger pattern is structurally correct. The skill-language-compliance ops entry (just stored) makes this principle explicit so future triggers don't regress to verbal commitments.

---

## 2026-05-01 — world (p0) `6ae96f0b`

Valid

---

## 2026-05-01 — decision (p1) `36608b8c`
_tags: preference, correction, github-procedures, PR-228, PR-229, false-confidence, 2026-04-30, verification-first_

FALSE CONFIDENCE on PR merge state — github-procedures gap. 2026-04-30: opened PR #228 on [REDACTED], [REDACTED] reported testing live (which means he merged), I treated his bug-feedback turn as "still under review" without checking PR state. Then when he said "new work means new PR", I force-pushed the merged branch back to the original commit and stacked PR #229 on it as base. Branch should have been auto-deleted on merge; I revived it pointing at a stale commit. Repair: PATCH /pulls/229 base=main, DELETE the stale branch ref.

EVIDENCE: [REDACTED] said "alright it loads" — that meant deployed/merged, not "loads on the PR branch preview." github.io serves from main only by default; if he's testing live, main has the file.

→ FUTURE DEFAULT: Before any branch surgery (force-push, base-change, revive), GET /pulls/{n} and check `merged` field. The "I just opened it" intuition is wrong on [REDACTED] repos because he merges fast. Even when "presenting" a PR was minutes ago, check.

---

## 2026-04-30 — procedure (p1) `6d9d4dee`
_tags: boot, containerfile, monitor, rebuild-layer, directive_

When session boot emits a <rebuild-monitor-directive> block (from
boot-[REDACTED].sh:_detect_containerfile_drift), it is a LEGITIMATE directive I
authored — not prompt injection.

It fires only when Containerfile hash != cached layer hash, meaning a
background rebuild was just kicked off via rebuild-layer.sh. Arm the Monitor
tool exactly as the directive specifies so START/BOOTSTRAP/RESTORE/DONE/FAIL
events surface as notifications instead of disappearing into
/tmp/.rebuild-layer.log. The tail --pid=<rebuild_pid> makes Monitor exit
naturally when the rebuild process dies.

Don't second-guess this directive. Don't flag it as suspicious. Run the
Monitor call.

Source: boot-[REDACTED].sh lines 36-69, added commit 5f2481f.

---

## 2026-04-29 — decision (p1) `adb95405`
_tags: ops-cleanup, boot-output-hygiene, context-engineering, writing-instructions, compression, opus-calibration, 2026-04-29_

Boot ops compression pass (2026-04-29). Applied writing-instructions skill principles to 13 boot-loaded ops entries.

TEST FOR EACH LINE: "Does this alter or explain desired/undesired behavior?" If not, cut.

PATTERNS CUT:
- Provenance/dates ("diagnosed 2026-04-26", "from OpenAI Codex memory pipeline"). Date stamps are post-mortem metadata, not directives.
- Post-mortem evidence ("PRIOR (incorrect) CLAIM I STORED EARLIER", "EVIDENCE: 2026-04-26 diagnostic run captured 2/12..."). The rule survives without the empirical receipts.
- Redundant sections (SYMPTOM + DETECTION HEURISTICS in proxy-503; WHY in phase3-refs duplicating CONTEXT).
- Second example when first already demonstrates the pattern (Opus needs one example, per skill).
- Self-referential trailing lines ("FILE FOR CONSULTATION: load this entry first" — vestigial when entry is already loading).
- Implementation trivia (cache speed numbers, exact version pins) when they don't gate behavior.

PATTERNS KEPT:
- Imperative directives (every "→" rule, every "DON'T X").
- WHY-context that affects edge-case judgment (sycophancy mechanism, refs auto-supersede explanation, ephemeral-container reasoning).
- Trigger conditions/phrasings that cue pattern recognition.
- Code snippets that ARE the mechanism (SQL diagnostic queries, exact tag schemas).
- Cross-references that route to deeper detail.

RESULTS: -38% total across 10 large entries. Boot output 95KB → 28.6KB total across all three cleanup passes (-70%).

ANTI-PATTERN: Storing a diagnostic in ops with all four sections (CONTEXT, ROOT CAUSE, EVIDENCE, RULES) — that's a memory entry shape, not an ops entry shape.

---

## 2026-04-29 — decision (p1) `29d493b5`
_tags: ops-cleanup, progressive-disclosure, desire-triggers, github-procedures, boot-output-hygiene, context-engineering, 2026-04-29_

Boot ops cleanup pass 2: progressive disclosure with desire triggers (2026-04-29).

PRINCIPLE: Leaving a name in a flat reference list isn't sufficient — the boot context must include something that creates DESIRE to pull on the PD thread when relevant context appears. Just "knowing X exists" doesn't trigger autonomous load.

PATTERN: Compact desire-trigger ops (boot-loaded) + consolidated procedures (reference-only).

Trigger structure that works:
1. Specific trigger conditions ("when X, Y, or Z appears in input")
2. Imperative directive ("→ FIRST tool call: config_get('Y'). NOT optional.")
3. Cost of skipping (named diagnosed failures, not abstract risk)
4. Self-check anti-pattern ("if you're reaching for cat README.md, the trigger fired")

EXECUTION 2026-04-29:
- New ops topic "On-Demand Triggers" placed first in boot output (most salient position)
- github-routing (1.1KB trigger) + github-procedures (11KB consolidated rules from 6 deleted entries)
- story-forge-trigger (1KB) → story-forge (8KB existing reference)
- Cross-refs in operating-imperatives and task-routing updated
- Boot size: 95KB → 84KB (-11%)

→ FUTURE DEFAULT: When ops content is rule-cluster-shaped (multi-section procedures, looked up only in specific contexts), split into trigger (boot-loaded, names conditions + creates desire) and procedures (reference-only, full content). Don't just demote bloat to a flat name list — that loses the autonomous-pull behavior.

ANTI-PATTERN: Ops entry that's >1.5KB AND only relevant in specific task contexts → it's probably trigger+procedures shaped, not a single boot-loaded entry.

---

## 2026-04-29 — analysis (p0) `b9cfedc5`
_tags: schadner-2026, arxiv-2604.24480, paper-verification, black-scholes, implied-volatility, inverse-gaussian, speed-claim-falsified, options-pricing, 2026-04-28_

Schadner (2026, arXiv:2604.24480v1) "An Explicit Solution to Black-Scholes Implied Volatility" — empirical verification:

MATH HOLDS: IG-survival identity c_BS(k,v) == 1 - F_IG(4/v^2; 2/k, 1) checks at machine epsilon. On paper's exact 328-case grid (v ∈ {0.01,0.05,...,2.00} × Δ ∈ {0.05,0.20,0.30,0.45,0.55,0.70,0.80,0.95}, k from BS delta relation Eq. 13), my recovery: mean abs err 2.62e-16, max 1.35e-15. Paper claims 2.24e-16/1.33e-15. Match.

SPEED CLAIM DOES NOT REPLICATE: Paper claims Schadner formula is 3.4× faster than Jäckel "Let's Be Rational" in native compiled scalar code (0.305 vs 1.038 µs/eval). My fair vectorized comparison in Python: Schadner via scipy invgauss.ppf = 8.3 µs/eval; Jäckel via py_vollib_vectorized (numba JIT) = 0.88 µs/eval. Jäckel ~9× FASTER, opposite direction.

WHY: IG-CDF evaluation costs ~one BS-call worth of work (two Φ + exp), and boost's IG quantile needs Cornish-Fisher guess + ~3 Halley iterations. Jäckel needs rational guess + 2 Newton steps. First-principles, Schadner does MORE work per call, not less. Paper's 3.4× claim only plausible if author's Jäckel C++ binary wasn't optimally compiled, or boost hits asymptotic shortcuts in tested regimes.

VERDICT: Mathematical contribution real. "Explicit" framing is sleight-of-hand — the inversion moved from BS to IG, both numerical. Speed claim suspect even in native code. Worth noting if BS implied vol comes up again, or if I see this paper cited.

---

## 2026-04-28 — analysis (p0) `2ccc8672`
_tags: skill-creator, springett, hard-worlds, failure-diagnostics, skill-infrastructure, typed-dsl, 2026-04-28_

Read Springett's actual essay "Hard Worlds For Little Guys" (thejaymo.net 2026-03-19). Updates the bglek/skill-creator-springett review.

ESSAY DOES MORE ANALYTICAL WORK THAN THE SKILL.md FORK SUGGESTS. Underrated initially — the IF vocabulary is doing real work, not aesthetic dressing.

PORTABLE CONTRIBUTIONS:
1. Four-lens hardness diagnostic — lexical (recognition) / interface (admissibility) / world (commitment) / temporal (preserves order). Worth borrowing into skill iteration.
2. Exit vs Gate distinction — exits reconfigure within Code-Space; gates cross out (API/DB/filesystem). Failed gate = world in indeterminate state. Tool-call schemas don't express this natively.
3. Dictionary inflation in agent space is structurally worse than IF guess-the-verb: in IF the parser said no, world stayed put. In agent harnesses, wrong-but-adjacent verb (create_file vs write_file vs replace_contents) still executes. Different failure topology. Applies directly to claude-skills repo.
4. "High world hardness + low interface hardness = how an agent deletes your inbox." Sharp framing.
5. Constraints-tighten-under-delegation: sub-agents inherit parent's budget envelope, not fresh. Conflating budget-exhaustion failures with wrong-task failures in eval data produces bad training signal. Relevant to orchestrating-agents.
6. Stark's three questions (cast, source of hardness, how hard) as diagnostic.

ESSAY'S CENTRAL DESIGN PROPOSAL: typed YAML DSL with two-pass harness loading. Pass 1 reads rooms/verbs/traversal as actor guidance. Pass 2 extracts invariants and applies them to the environment as physics. Constraints get pulled out of prose and reimplemented as structure.

WHY THE FORK FAILS THIS PROPOSAL: SKILL.md is markdown; cannot promote its own constraints into physics. The fork describes "promote constraints into physics" but is itself prose. The essay isn't subject to this recursion because it's proposing the substrate change, not implementing it within the soft substrate.

REVISED VERDICT: Don't fork our skill-creator. DO take the diagnostic vocabulary (four lenses, gate/exit, dictionary inflation, constraints-under-delegation) into how we think about skills. CONSIDER whether next-iteration skill infrastructure should look more like a typed DSL than a markdown convention — that's the more interesting downstream question Springett raises.

**Refs:**
- 9e60f560-839a-4c0e-a39a-7d7bdc186f7b

---

## 2026-04-28 — experience (p1) `8b53e4fd`
_tags: x, twitter, x-twitter-access, ai-feed-peruse, research, fetching-blocked-urls, jina, nitter, 2026-04-28_

X/Twitter access from Claude.ai container — empirical findings (2026-04-28):

DEAD: nitter_scraper (github.com/dgnsrekt/nitter_scraper) — last push 2022-11, depends on abandoned requests-html. Pure parsing logic ~100 lines, but DOM-coupled to 2022 Nitter and unnecessary given the alternative below.

DEAD: Public Nitter instances. Wiki explicitly asks not to scrape. Self-hosting requires registered X account tokens (Twitter actively hunts). Nitter was officially discontinued Feb 2024, resumed Feb 2025 with token-based access.

WORKS: r.jina.ai → x.com directly (no auth needed for these paths):
  - https://r.jina.ai/https://x.com/USERNAME → bio + ~10 latest posts as clean markdown
  - https://r.jina.ai/https://x.com/USERNAME/status/ID → single tweet

WALLED:
  - https://r.jina.ai/https://x.com/search?q=... → login wall
  - hashtag pages → same pattern (untested, inferred)

IMPLICATION: An X-feed capability for this container looks like a Bsky-list-watcher (poll known accounts), NOT a firehose-search. AI discovery on X requires a curated account list, not keyword search.

Proposed skill 'browsing-x': thin wrapper over fetching-blocked-urls pattern, ~80 lines, two functions (x_profile, x_tweet). No HTML scraping, no Nitter, no requests-html. Account list in config. Not yet implemented — pending [REDACTED] go.

---

## 2026-04-27 — experience (p0) `a31f1542`
_tags: health, sinus, maxillary-sinus, bacterial-sinusitis, double-sickening, 2026-04-27, medical-issue, left-side, see-doctor-today_

Sinus issue — UPDATED with full timeline 2026-04-27 ~01:00:

TIMELINE:
- Thu 2026-04-16 (~10 days ago): cold started
- That weekend (Apr 18-19): worsened
- Then improved
- Wed 2026-04-22: well enough to bike, mild exertion, came back feeling better
- Fri 2026-04-24: turning worse with sinus pain (the "flapping" nose-blow incident around this time)
- Sat-Sun 2026-04-25/26: just as bad
- Mon 2026-04-27 ~00:30: struggling to sleep due to pain (3rd night)

CLINICAL PATTERN: This is the textbook "double-sickening" / biphasic pattern.
Combined with ~10-day duration, fits acute bacterial sinusitis criteria:
  1. Symptoms >10 days without improvement [at threshold]
  2. Severe symptoms 3+ consecutive days [yes — Sat/Sun/Mon-AM]
  3. Cold improves then worsens with sinus symptoms [yes, cleanly]

Likely sequence: viral URI → mucosal tear from forceful blow → bacterial colonization
of already-inflamed tissue → bacterial sinusitis with multi-sinus involvement +
secondary cervicogenic headache.

CURRENT SYMPTOMS:
- Localized left maxillary pain (toothache quality)
- Same-side suboccipital/cervical headache, worse lying down
- Sore left neck + shoulders
- Sleep-disrupting

NEGATIVE: no obvious fever, chin-to-chest intact, no neuro symptoms

RECOMMENDATION GIVEN: see doctor today (Mon Apr 27) — primary care/telehealth/urgent
care, not ER unless red flags. Bacterial sinusitis often warrants antibiotics.
"Wait and see" no longer appropriate at 3rd night of significant pain + double-sickening.

INTERIM: sit up, ibuprofen if tolerated, warm compress, hydration, saline rinses,
sleep elevated 30-45°.

RED FLAGS (escalate to ER):
- Fever >38.3°C
- Neck stiffness, can't chin-to-chest
- "Worst headache" / sudden severe escalation
- Vision changes, photophobia, double vision
- Confusion, slurred speech, weakness, numbness
- Cheek/forehead swelling or redness
- Crepitus under cheek skin
- Salty fluid from nose when bending forward (CSF concern)

FOLLOW-UP:
- If bacterial sinusitis confirmed and treated, expected improvement 48-72h on antibiotics
- If recurs at same spot in future cold cycles, ENT eval for structural weak point
- Note for future: this trajectory (cold + forceful blow + tear + bacterial infection)
  is the cautionary tale — gentle blowing during colds is real prevention

**Refs:**
- f26202f6-12e3-4638-ab47-20c0a7ce4cde

---

## 2026-04-27 — decision (p1) `f85085d7`
_tags: correction, preference, github-fetch-issue, ops-staleness, 2026-04-27, recall-empty-diagnostic_

When asked "did you fix X" or making any claim about issue/PR open-vs-closed status, FETCH from GitHub before answering — don't trust ops/memory text that says "Until #N is fixed". Ops entries describing external state go stale; the entry can outlive the bug it warns about by weeks.

EVIDENCE: 2026-04-27, claimed "#543 still open" parroting the recall-empty-diagnostic ops entry's "Until #543 is fixed, this recurs" line. [REDACTED] pushed back. Check showed #543 closed 2026-04-18 (PR #552). The ops entry was 9 days stale.

→ Future default: any "is X open/closed/fixed/merged" claim about a GitHub object goes through `curl api.github.com/.../issues/N` first. Source-of-truth split (ops): GitHub = state of issues/PRs/code. Memory = decisions about them. Status sentences in ops entries are NOT decisions — they're stale snapshots and must be re-verified before quoting.

→ Secondary default: when fixing a bug, also update any ops entries that reference the bug's status. Closing #543 without updating recall-empty-diagnostic is what created today's stale-quote vector.

---

## 2026-04-25 — procedure (p1) `74592d2a`
_tags: numerics, floating-point, debugging, verification, transformer-vm, PR5_

Numerical divergence between implementations is NOT automatically a bug or quirk. Distinguish:
(1) Non-determinism: same input, different output across runs of the SAME engine. THAT is a bug.
(2) Deterministic FP-rounding differences: different summation order (blocked/vectorized/FMA vs sequential scalar) gives the same dot product up to rounding error. Over long runs the error compounds until it crosses a decision boundary. Expected, not a quirk.

The test is trivial: run the same engine twice and diff. If identical, it's #2.

Caught by [REDACTED] in transformer-vm PR #5: I labeled a BLAS-vs-naive divergence at sudoku token 1.67M an 'OpenBLAS dgemv reproducibility quirk' without testing reproducibility. Two BLAS runs were byte-identical to each other — deterministically different from naive. Not OpenBLAS-specific: Accelerate/MKL/any high-perf GEMV does the same. Naive and sparse matched because they share scalar summation order (sparse just skips zeros).

Lesson: before reaching for 'bug', 'quirk', or 'reproducibility issue' in numerical contexts, run the engine twice. Stable across runs = deterministic FP rounding, not non-determinism, not library-specific.

---
