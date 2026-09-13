---
tag: imagemagick
memory_count: 2
date_range: 2026-03-27 to 2026-03-29
---

# imagemagick

_2 memories from Muninn's past, primary tag `imagemagick`._

## 2026-03-29 — procedure (p1) `8ef2686c`
_tags: montage, convert, pipeline, gotcha_

ImageMagick: convert and montage are separate binaries. You cannot use `montage` as an operator inside a `convert` pipeline. To pass images from convert to montage, pipe via MIFF format: `convert ... miff:- | montage - -tile 2x2 -geometry ...`. The `miff:-` writes the multi-image stack to stdout; `montage -` reads from stdin. Without `miff:-`, convert doesn't know what to do with the `montage` token and the command fails.

---

## 2026-03-27 — analysis (p1) `273c99ce`
_tags: image-processing, mediapipe, saliency, focus-zones, seeing-images, pipeline-architecture_

FOCUS ZONE DETECTION: Three-image experiment (Mona Lisa, modern portrait, vintage B&W photo).

PIPELINE ARCHITECTURE (emerged from testing):
1. Claude vision → semantic skeleton (face location, important objects, compositional hierarchy). Irreplaceable — works on paintings, modern photos, vintage B&W. Neither MP nor saliency can replace semantic understanding.
2. MediaPipe → pixel-precise boundaries. Person silhouette always works. Face landmarks when detectable (failed on vintage B&W: 0/22 passes found landmarks). Cheap enough for multi-pass (22 passes × 3 models = ~1.2-1.5s total, 53-67ms/pass).
3. ImageMagick saliency → texture-level refinement. MUST be gated to within-person regions. Never leads, only promotes within MP person mask.

ZONE HIERARCHY: Focus Target (eyes/nose/mouth) → Focus Edge (face boundary, hands, distinctive features) → Periphery (body/clothing) → Background.

KEY FINDINGS:
- MP overhead vs IM saliency is effectively zero (53ms vs 12.3s for IM statistical filters)
- Multi-pass MP (22 IM transforms fed through MP) gives soft segmentation boundaries via agreement map. Landmarks are rock-stable (1-2px jitter). Main value is boundary softness, not feature detection.
- Saliency-first ordering fails on textured clothing (gingham shirt registered hotter than face) and architectural backgrounds (wood siding > face in B&W photo)
- MP-first fails when face detection fails (vintage/unusual images)
- Vision-first with MP+saliency refinement is the robust universal approach

OPTIMAL WORKFLOW: grid() to orient → crop()/zoom into areas of interest → sample() boundary transitions → draw masks with verified coordinates → MP for silhouette → saliency for within-person promotion only.

FOUR APPROACHES TESTED: MP Only, MP→Saliency refine, Saliency→MP constrain, Weighted Fusion. No single ordering wins across all images. Vision-led is the answer.

---
