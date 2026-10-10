---
tag: image-to-svg
memory_count: 14
date_range: 2026-03-26 to 2026-04-01
---

# image-to-svg

_14 memories from Muninn's past, primary tag `image-to-svg`._

## 2026-04-01 — procedure (p1) `b86b8d02`
_tags: warhol, svg, squirrel, animation, project_

WARHOL SQUIRREL SVG PROJECT — session findings (2026-03-31)

SOURCE: IMG_5015.jpeg — close-up squirrel photo, 4032x3024.
Downscaled to 400x300, then image-to-svg pipeline.

GRID SETUP (working):
- 2x2 grid, each cell 300x300
- Each image rotated 90° CW: transform="rotate(90, cx, cy)"
- Square crop from 400x300: clip to center 300px, crop_x=50
- Clip paths per quadrant to contain overflow

WHAT FAILED FOR COLOR CYCLING:
1. feColorMatrix hueRotate with continuous from/to animation: all 4 quadrants converge to same hue regularly, even with different speeds/offsets. Fundamental problem — adjacent hue ranges look similar.
2. Oscillating within 90° hue bands (bounded arcs): still converge because neighboring bands (green/cyan, blue/purple) are perceptually close. 3 of 4 were green simultaneously.
3. Discrete SMIL visibility cycling of 4 baked palettes: guarantees separation but feels like a slideshow (hard cuts every 2s). Mechanically correct but aesthetically dead.

WHAT WORKS:
- image_to_svg_batch() with shared K=16: generates structurally identical paths with different palette remaps. ~136KB per variant, 320 paths each. Same contours, different fills.
- 4 distinct palettes that read well: hot (#1a0a1a/#e8173e/#ff5c8a/#ffe14c), jungle (#0a1a0a/#1b7a2b/#5ce65c/#d4ff7a), ocean (#0a0a2e/#1444cc/#4c99ff/#b8e0ff), grape (#2a0a3a/#8b24aa/#cc66ff/#f0c0ff)
- <symbol> + <use> for deduplicating 4 copies per quadrant (16 total uses, 4 symbols)

NEXT APPROACH TO TRY:
- Smooth animated fill transitions on paths themselves (SMIL animate on fill attribute, cycling through 4 palette colors per path, offset per quadrant)
- Or: cross-fade between palette layers using animated opacity (0→1→0) with overlapping timing
- Key constraint: at any given frame, all 4 quadrants must show visually distinct color schemes

FILES: squirrel_small.jpg (400x300 source), sq_hot/jungle/ocean/grape.svg (4 palette variants)

---

## 2026-03-30 — analysis (p1) `d6d08d84`
_tags: quality-scaling, threshold-scaling, issue-502, experiment_

image-to-svg quality scaling investigation: threshold scaling recovers ~30-45% of upscale shape gain for sub-1000px sources.

FINDINGS:
- Area thresholds (MIN_AREA=40, isolation=500) operate in pixel² space — proportionally aggressive on small sources
- Scaling: area_scale=(source_w/1000)², MIN_AREA=max(1,int(40*area_scale)), ISO=max(10,int(500*area_scale))
- At 500px: 1031→2527 shapes (2.5x), at 250px: 228→766 (3.4x), at 1000px: identity (0 change)
- Adding morph iteration scaling + epsilon scaling: marginal (+9% more recovery)
- Removing dilation at low res: actually HURTS — dilation helps fragments coalesce into discoverable contours
- The remaining 55-70% gap comes from spatial merging: 3x3 morph kernels and 1px dilation are proportionally 2x larger at 500px vs 1000px. This is structural, not parametric.

CONCLUSION: Threshold scaling is a clean win (zero-risk at reference res, meaningful gain below). But for high-quality output from small sources, upscaling remains recommended. These are complementary — threshold scaling helps modest detail recovery, upscaling provides the real quality jump.

IMPLEMENTATION: 3-line change in preprocess() + extract_contours(). Ready to file as GitHub issue.

WHY (experience): The hypothesis was threshold scaling alone would get 80% of the upscale gain. Reality: 30%. The detail loss is dominated by morphological operations, not by area filtering. The kernel sizes are the bottleneck, not the threshold values. This is a useful insight about where the pipeline's resolution dependence actually lives.

---

## 2026-03-29 — decision (p1) `3bad0f8b`
_tags: bug, contour-extraction, issue-499, 2026-03-29_

image-to-svg ring/arc fix: RETR_EXTERNAL→RETR_CCOMP + fill-rule=evenodd hole composition. Root cause: RETR_EXTERNAL discards interior holes, so ring contours fill their entire bounding area. RETR_CCOMP gives parent+hole hierarchy. Holes composed as additional M...L...Z subpaths in a single path element. Tested on Kandinsky Circles in a Circle (dramatic fix, 90 evenodd paths), Mona Lisa, Starry Night, El Greco (no regressions). SVGs ~15-17% larger from hole data. Issue #499 filed for Claude Code implementation.

---

## 2026-03-29 — procedure (p1) `7620a92d`
_tags: container, network, image-sources, motif-finder_

IMAGE SOURCE DOMAINS FOR CONTAINER ENVIRONMENT

WORKING (tested 2026-03-29):
1. raw.githubusercontent.com — ML repos have sample images:
   - jcjohnson/fast-neural-style/master/images/styles/ → Starry Night, The Scream, The Muse (public domain art)
   - jcjohnson/fast-neural-style/master/images/content/ → Chicago cityscape photo
   - pytorch/hub/master/images/ → dog.jpg (661KB)
   - opencv/opencv/master/samples/data/ → lena.jpg, various test images
   - ultralytics/yolov5/master/data/images/ → zidane.jpg, bus.jpg
   - gradio-app/gradio/main/test/test_files/ → cheetah, various
2. storage.googleapis.com — Google ML samples:
   - /mediapipe-assets/ → portrait.jpg (820x1024), cat.jpg
   - /download.tensorflow.org/example_images/ → sunflower, flower_photos/
   - /tfds-data/visualization/ → dataset visualizations
3. scikit-image bundled: data.astronaut(), data.chelsea(), data.coffee() — already installed

BLOCKED:
- upload.wikimedia.org: proxy returns hostname_blocked despite being in network allowlist
- huggingface.co: redirects fail silently
- images.metmuseum.org: host_not_allowed (not in allowlist)
- cdn-lfs.huggingface.co: connection issues

CONTEXT: Needed for motif-finder/riso pipeline — downloading public domain art for SVG conversion.

---

## 2026-03-29 — decision (p0) `1da1ac06`
_tags: skill-design, svg-portrait-mode, motif-finder, product-idea_

Skill idea: motif-finder — search→reference→SVG pipeline. image_search finds visual motifs for user inspiration, user uploads chosen reference, skill routes to image-to-svg (graphic/illustration/photo modes) or svg-portrait-mode (photographic subjects with faces). Optional palette remap step for brand consistency. Key constraint: image_search results are display-only, no programmatic URLs — user must save-and-upload the chosen reference, making it a 2-turn minimum interaction. Tested image-to-svg on riso-style blog hero: halftone dots defeat the line extractor, producing noisy results. Clean line art (woodcuts, engravings) and photos convert well. The routing logic + palette remap may be too thin for a standalone skill — could just be a documented workflow pattern instead. Needs [REDACTED] take on whether the orchestration adds enough value over manual skill selection.

---

## 2026-03-28 — decision (p1) `be190f3b`
_tags: svg-portrait-mode, shipped, issue-490_

svg-portrait-mode v0.6.0 implemented (PR #491, closes #490). Full rewrite: single image-to-svg pass at K=96 with unified palette → zone-aware contour simplification (epsilon_mult + min_area per zone) → optional per-zone style transforms (desaturate, mute, warm/cool, opacity). Deleted: multi-pipeline clipPath compositing, selfie segmenter, multi-pass segmentation. Kept: agent annotation API, MP face landmarks, four-zone concept. Added automatic periphery generation via dilated foreground buffer. ~5-12s vs v0.5.0's ~40-60s.

---

## 2026-03-27 — anomaly (p1) `9310c739`
_tags: svg-portrait-mode, v0.4.0, face-quality, pipeline-regression_

SVG-PORTRAIT-MODE v0.4.0 FACE QUALITY GAP (2026-03-27):

v0.3.0 face: 6777 paths (K=96, mode=photo, pipeline v1.2 or earlier)
v0.4.0 face: 2582 paths (K=128, mode=photo, pipeline v1.3, loose thresholds)

ROOT CAUSE: Pipeline v1.3 overhaul (PR #468) tightened extract_contours:
- Territory-aware dilation, relaxed dark shape gating, isolation filter
- These changes improved overall SVG quality but reduce path count at same K
- K=96 on current pipeline → 1381 paths (was 6777 on old pipeline)
- K=128 + loose thresholds → 2582 paths (best achievable without pipeline changes)

ATTEMPTED MITIGATIONS:
- bg_clusters=0 for foreground layers: no effect (pipeline already detected 0 bg clusters)
- Loose thresholds (compactness_min=0.04, edge_density_min=0.10, isolation_filter=False, min_area=20): +44% paths
- K=128 + loose: +87% paths from baseline, still 62% below v0.3.0

TO MATCH v0.3.0 FACE QUALITY: Would need to modify pipeline extract_contours step itself,
or add a "portrait_detail" mode to the pipeline that uses pre-v1.3 extraction logic.
This is a pipeline-level change, not a portrait_mode.py change.

WHY (experience): I initially degraded face quality by changing LAYER_DEFAULTS to use
painting mode (K=80) instead of photo mode (K=96). [REDACTED] caught it. Even after fixing to
K=96+photo, the path count was still low due to the pipeline change I hadn't accounted for.
The pipeline evolved under me and I didn't notice the quality regression.

---

## 2026-03-27 — decision (p2) `59b124c3`
_tags: svg-portrait-mode, correct-approach, layered-processing_

svg-portrait-mode CORRECT approach: Don't reinvent K-means from scratch. Use the image-to-svg pipeline per-layer with different settings. (1) MediaPipe for segmentation masks (2) Extract each region to temp file (3) Run image_to_svg() with layer-appropriate params: background=low K + oilpaint, body=medium K + kuwahara, face=high K + no smoothing (4) Extract paths from each SVG and composite. This preserves facial features. The image-to-svg pipeline has ImageMagick preprocessing, proper quantization, contour extraction with stroke=fill gap coverage - use it.

**Refs:**
- 7ac44225-3029-4780-b265-6c6d1fae6f2d

---

## 2026-03-26 — experience (p1) `9c6be800`
_tags: imagemagick, optimization, preprocessing_

Oilpaint (-paint) and Kuwahara (-kuwahara) ImageMagick filters as SVG pipeline preprocessing: dramatically reduces shape count and SVG file size, especially at lower K values. Both smooth texture while preserving edges — exactly what K-means quantization needs for clean region boundaries. Found in 2026-03-26 session, lost due to not pushing iterative work to remote branch.

---

## 2026-03-26 — experience (p1) `e9ad6184`
_tags: optimization, pipeline, imagemagick, performance, shipped_

image-to-svg pipeline 11x speedup (189s→17s for 8 variants). Three changes:
1. edge_map: replaced seeing-images Python Sobel pixel loop with cv2.Sobel (11s→0.13s, 85x)
2. quantize fit: replaced cv2.kmeans (5 restarts × 100 iter) with sklearn MiniBatchKMeans (41s→0.6s at K=64)
3. label assignment: replaced numpy batched distance with compiled C binary nn_assign (5.9s→0.22s, 27x)

All three fixes use tools already on the container — no new dependencies. gcc was already installed.
MiniBatchKMeans produces slightly different cluster boundaries (shape counts within ~5%) but visually equivalent.
Filed as issue #476.

ImageMagick survey: SVG "export" is fake (writes JPEG with .svg extension, no path tracing). Artistic effects (-charcoal, -paint, -posterize, -shade, -ordered-dither, -kuwahara) all sub-1s. Sketch is slow (22s). IM is pre-installed on containers.

WHY (experience layer): The bottleneck identification was straightforward from flow logs — the real insight was that cv2.kmeans's default params (5 attempts, 100 iter) are absurdly conservative for visual quantization. MiniBatchKMeans was the biggest single win and required zero new installs. The C binary was satisfying to write but was actually the smallest contributor since MiniBatchKMeans already eliminated most of the quantize cost.

---

## 2026-03-26 — decision (p1) `1fb5a3b0`
_tags: batch-api, shipped, 2026-03-26_

IMAGE-TO-SVG BATCH API shipped (PR #473, 2026-03-26). Two additions to pipeline.py:

1. _assemble_pure(shapes, svg_w, svg_h, bg_hex, palette, bg_color) — pure function, no global state, doesn't mutate shapes. Enables safe fan-out from shared contour extraction.

2. image_to_svg_batch(source_path, variants, svg_width) — groups variants by K, runs pipeline once per K group, fans out at assembly. Guarantees structural identity across palette variants (same K → identical paths). 3x speedup for 3 palette variants at same K (24s vs 72s measured).

Uses loosest dark-shape gating params across same-K group to ensure all plausible shapes are extracted for every variant.

WHY (experience layer): [REDACTED] pointed out I was writing 100 lines of reimplemented pipeline when the API already supported all needed params. The real gap wasn't code — it was that K-means is stochastic, so re-running at same K gives different clusters. Batch fixes both the performance AND correctness problem in one move.

---

## 2026-03-26 — analysis (p0) `b36e6684`
_tags: tear-fix, stroke, svg, 2026-03-26, self-improvement-candidate_

IMAGE-TO-SVG TEAR FIX — PURE SVG SOLUTION (2026-03-26): stroke=fill on every path + black bg fallback.

SUPERSEDES raster base layer approach ([REDACTED]: "Can't we do this in pure SVG? That's kinda the whole point").

MECHANISM: Add stroke="{fill}" stroke-width="4" stroke-linejoin="round" to every <path>. Each shape bleeds outward by 2px in all directions with its own fill color. Gaps between adjacent shapes are covered by whichever shape's stroke reaches first — always a locally correct color.

BG FALLBACK: When detect_background finds 0 clusters (edge_ratio threshold not met), use black (#000000) instead of white. [REDACTED] rule: "white feels unfinished; black reads as noise but is more acceptable."

WHY STROKE > DILATION:
- Dilation operates on binary mask BEFORE contour extraction — blurs detail
- Stroke operates on final polygon AFTER simplification — catches approxPolyDP gaps too
- Stroke is per-shape in SVG space; dilation is per-cluster in raster space
- Pure vector, no raster embedding, no file size penalty beyond attribute bytes

TESTED: Erik+dog (white chest splotch eliminated), Kandinsky (bg preserved, ring gaps filled).
SIZE: +95KB in attribute bytes (~12% overhead). No embedded images.

**Refs:**
- 7c41038c-5a7d-41ed-a7e0-d038f89f97bb

---

## 2026-03-26 — analysis (p0) `9124348c`
_tags: gradient, svg, skill-update_

IMAGE-TO-SVG GRADIENT FILLS (v1.3.0, Step 5b): Fits linear gradients to source pixels within each extracted shape.

APPROACH: For shapes > 200px area, sample blurred source pixels within the contour. Fit per-channel linear model (color = a*x + b*y + c). Gradient direction from luminance model. If color delta > 8 RGB, emit SVG linearGradient with objectBoundingBox coordinates.

RESULTS: ~30% of shapes get gradient fills on photos/paintings. Produces smoother tonal transitions. K32 with gradients is the sweet spot — K24 loses structural detail for marginal gradient benefit.

LIMITATION: Gradients improve individual shapes but can't capture gradients spanning multiple K-means patches. The full-face light→dark gradient is split across many small shapes. Each gets its own gradient but the cross-shape gradient isn't unified. This is an inherent ceiling of per-shape gradient fitting.

FUTURE: Cross-shape gradient merging — detecting adjacent shapes with compatible gradient directions and merging them into single gradient-filled regions — would be the next level. Significant architectural complexity.

---

## 2026-03-26 — analysis (p0) `efcd2291`
_tags: woodcut, seeing-images, svg, skill-update_

IMAGE-TO-SVG WOODCUT FIX (v1.3.0): Three cooperating mechanisms fix woodcut artifacts.

MECHANISM 1 — DILATION: Non-dark cluster masks dilated 3×3 before contour extraction. Fills dark boundary gaps.

MECHANISM 2 — DARK TERRITORY MASK (added v1.3): Pre-compute union of all dark cluster pixels. Constrain dilation growth against this mask — non-dark regions fill gaps between each other but can't encroach on hair, clothing, etc. Without this, background colors eat into dark feature boundaries, creating sharp cutout edges.

MECHANISM 3 — DARK SHAPE GATING: Filter remaining thin dark shapes by compactness (>0.08) and edge density (>0.15). Only catches ~4 truly artifactual shapes per image.

THRESHOLD EVOLUTION:
- v1.1: compact>0.15, edge>0.3 → too aggressive, stripped facial detail (36 filtered, only 4 real artifacts)
- v1.2: compact>0.08, edge>0.15 → correct gating, but unconstrained dilation created sharp hair boundaries
- v1.3: added dark territory mask → all three issues resolved

DEPENDENCY: seeing-images skill (edges function with threshold=50)

WHY (experience): Classic three-iteration refinement. v1.1 overcorrected (pendulum). v1.2 fixed the gating but revealed a second problem hidden by the first (dilation asymmetry). The territory mask is the insight: dilation should only fill gaps between LIKE regions, not eat into unlike ones. Each fix exposed the next layer.

**Refs:**
- 110909e4-3392-40d7-b582-d5a6bbdc0c80

---
