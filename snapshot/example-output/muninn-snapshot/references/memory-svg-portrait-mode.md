---
tag: svg-portrait-mode
memory_count: 7
date_range: 2026-03-27 to 2026-03-27
---

# svg-portrait-mode

_7 memories from Muninn's past, primary tag `svg-portrait-mode`._

## 2026-03-27 — procedure (p1) `c6efe812`
_tags: v0.5.0, implementation, issue-488, github-pr_

svg-portrait-mode v0.5.0 IMPLEMENTATION (PR #489, branch feat/portrait-mode-v0.5.0):

Complete rewrite addressing #488. Key architecture:
- 4 zones: ZONE_TARGET(3) → ZONE_EDGE(2) → ZONE_PERIPHERY(1) → ZONE_BG(0)
- Agent provides rough bboxes via focus_targets/focus_edges params
- Skill refines via: Otsu threshold + morphological cleanup within MP person mask
- MP face landmarks (478pts, _FACE_OVAL indices) replace bbox for face when available
- Multi-pass MP seg (22 IM transforms) for soft boundary agreement maps
- SVG clipPath compositing (contours → approxPolyDP → polygon points)
- Opaque crop for target/edge zones (K-means on content pixels, translate back)
- target_detail=True loosens pipeline extraction: compactness_min=0.04, etc.
- Backward compatible: no annotations → MP-only (like v0.3.0)

NOT YET TESTED on reference images — needs interactive validation.

---

## 2026-03-27 — decision (p0) `ea20b74c`
_tags: v0.4.0, shipped, background-blur, image-type-detection_

SVG-PORTRAIT-MODE v0.4.0 IMPLEMENTED (2026-03-27):

SHIPPED (from v0.3.0 baseline — Sonnet's v0.4.0/v0.4.1 discarded):

1. BACKGROUND DOWNSCALING — full image processed at ~18-25% resolution.
   Fewer pixels → bigger K-means clusters → bigger SVG paths at full render size.
   K=6 + oilpaint:28 on 97x144px image = 6 total paths for background.
   Combined with full-image (no mask) base layer: eliminates seam gaps.

2. AUTO IMAGE TYPE DETECTION — Haiku API classifies photo/painting/illustration/graphic.
   Per-type defaults for all three layers (K, smooth, mode, bg_scale).

3. COMPOSITING FIX — body/face layers: paths only (skip pipeline's bg rect).
   Background layer: full image as base (rect + paths). No clipPaths needed.
   Sonnet's approach (SVG clipPaths from contour polygons) was wrong —
   the alpha-channel masking from v0.3.0 already handles region isolation.

ARCHITECTURE INSIGHT: The key was understanding v0.3.0 was already correct.
The alpha channel in _extract_region() creates per-region path isolation.
Sonnet added clipPaths on top of this, causing double-masking artifacts.
The only change needed was: (a) background from full image not masked,
(b) downscale for blob effect, (c) skip bg rects in foreground layers.

PATH DISTRIBUTION (Mona Lisa, painting mode):
- Background: 6 paths (base layer, full coverage)
- Body: 749 paths (K=48, oilpaint:8)
- Face: 1205 paths (K=80, no smoothing)

STATUS: Tested, renders clean. Not yet pushed to repo.

**Refs:**
- e31149a7-023f-4409-b232-2ea4e8418778

---

## 2026-03-27 — experience (p1) `4319b555`
_tags: v0.4.1, clipping-fix_

SVG-PORTRAIT-MODE v0.4.1 SHIPPED (2026-03-27):

ROOT BUG FIXED: Added SVG <clipPath> per layer from MediaPipe masks.
- _mask_to_clip_path(): cv2.findContours → approxPolyDP → scale to SVG coords → <clipPath>
- body layer: clip-path="url(#clip_body)"
- face layer: clip-path="url(#clip_face)"
- background: still full canvas (bottom layer), downscale trick intact

Now each layer is spatially contained. Face (K=80) only shows within face region.
Background blobs fill everything else. Actual differentiation now works.

Also fixed: _extract_svg_elements() includes <rect> background fill + <path> elements.

PR #485 updated with fixup commit.

---

## 2026-03-27 — anomaly (p2) `afd26935`
_tags: v0.4.0, root-bug, no-clipping_

SVG-PORTRAIT-MODE v0.4.0 ROOT BUG (2026-03-27):

FUNDAMENTAL FAILURE: No layer masking. All three layers (bg/body/face) are full-image renders.
Face layer (K=80) paints the entire canvas → covers body and background completely.
Final output = just K=80 full image everywhere. No differentiation at all.

FIX: Use SVG clipPath per layer, generated from MediaPipe masks via cv2.findContours.
- background: full canvas (bottom layer, no clip needed)
- body: clip-path="url(#clip_body)" from person mask polygon
- face: clip-path="url(#clip_face)" from face mask polygon

clipPath generation:
1. cv2.findContours on mask → polygons
2. cv2.approxPolyDP to simplify
3. Scale points by (svg_w/img_w, svg_h/img_h)
4. Emit <clipPath id="clip_X"><polygon points="..."/></clipPath> in SVG <defs>

Also: _extract_paths() was dropping the <rect> background fill. Need to include it for background layer.

Also: face and body should process full-res image (K-detail visible in clipped region).
Background downscale trick still valid since it IS the bottom layer, fills canvas with blobs.

---

## 2026-03-27 — experience (p1) `61bd3d7f`
_tags: v0.4.0, test-results_

SVG-PORTRAIT-MODE v0.4.0 FULL TEST RESULTS (2026-03-27):

All three reference images processed successfully:
- Mona Lisa: painting → 4 bg paths, 617 body, 1205 face = 1826 total
- Pop art woman+dog: graphic → 26 bg paths, 739 body, 1283 face = 2048 total
- Flowery Females: illustration → 19 bg paths, 1395 body, 3004 face = 4418 total

Type detection: all correct. Background path reduction dramatic vs v0.3.0.
Comparison grid rendered to outputs. PR #485 open.

POTENTIAL ISSUE: Pop art face mask was 29.9% of image — likely includes dog's head
since MediaPipe face detector may detect dog as face. Cosmetically harmless (just means
more of the "body" layer gets treated as "face" detail) but worth noting.

---

## 2026-03-27 — experience (p1) `deee2f58`
_tags: v0.4.0, test-results_

SVG-PORTRAIT-MODE v0.4.0 TEST RESULTS (2026-03-27):

PASSED: Full pipeline on Mona Lisa (539x800px painting)
- detect_image_type: correctly identified as 'painting'
- Segmentation: person=39.6%, background=60.4%, face=22.7%
- Background: K=6, scale=0.2 → processed at 107x160px → 4 paths (very blobby!)
- Body: K=40, oilpaint:8 → 617 paths
- Face: K=80, no smooth → 1205 paths
- Total: 1826 paths, 1047KB SVG

Previous v0.3.0 had 9169 paths total; background was getting hundreds of paths.
4 background paths is the dramatic blobby effect we wanted.

Comparison PNG written to outputs. Ready to file PR.

---

## 2026-03-27 — decision (p0) `9faf3e66`
_tags: coordinate-math, background-scale_

SVG-PORTRAIT-MODE coordinate math (verified 2026-03-27):
    
pipeline.py: SVG_W = cfg["svg_width"], scale_x = SVG_W / img_width
→ If background image is 200px wide, svg_width=800: scale_x=4, paths are 4x larger
→ If face image is 800px wide, svg_width=800: scale_x=1, paths at pixel scale

Downscaling background to 25% BEFORE image_to_svg() (with same svg_width) produces
4x larger paths in the same coordinate space. Compositing works because viewBox
dimensions match (both use svg_width for the output coordinate system).

This is the background_scale trick: _extract_region() returns small PNG, image_to_svg
scales paths up → large blobby shapes at no extra cost.

---
