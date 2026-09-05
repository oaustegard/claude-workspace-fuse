---
tag: embeddings
memory_count: 2
date_range: 2026-03-27 to 2026-04-10
---

# embeddings

_2 memories from Muninn's past, primary tag `embeddings`._

## 2026-04-10 — world (p1) `a241394f`
_tags: sentence-transformers, multimodal, reranking, huggingface_

sentence-transformers v5.4.0 (2026-04-09). Three pillars: (1) Multimodal — SentenceTransformer/CrossEncoder natively support text/image/audio/video, auto modality detection via infer_modality(), Router module for composing encoders. (2) Modular CrossEncoder — BaseModel(nn.Sequential), LogitScore module for generative rerankers (logit[true]-logit[false]), transformer_task types. (3) FA2 input flattening — auto-skips padding for text-only, requires transformers>=5.0. Also: CausalLM default pooling→last-token, TripletLoss distance bug fixed.

---

## 2026-03-27 — experience (p1) `42452ac8`
_tags: mediapipe, text-embedding, image-embedding, on-device-ml, exploration_

MediaPipe exploration (2026-03-27): Tested on-device ML capabilities via Google's MediaPipe library.

TEXT TASKS (all working):
- TextEmbedder: 100-dim embeddings via Universal Sentence Encoder (5.9MB model). Built-in cosine similarity. Correctly groups semantically similar sentences even with different words.
- TextClassifier: BERT-based sentiment (25MB). Binary pos/neg.
- LanguageDetector: 100+ languages, only 308KB model. Norwegian detected at 0.48 confidence.

VISION TASKS (all working):
- ImageEmbedder: 1024-dim embeddings via MobileNetV3 (4MB). Useful for image similarity.
- ObjectDetector: EfficientDet-Lite0 (6.7MB). COCO classes.
- ImageClassifier: EfficientNet (18MB). ImageNet classes.
- Also available: FaceDetector, FaceLandmarker, HandLandmarker, GestureRecognizer, PoseLandmarker, ImageSegmenter

AUDIO:
- AudioClassifier: YAMNet (4MB) with 500+ sound classes. Correctly identified 440Hz sine wave.

POTENTIAL USES:
1. TextEmbedder for semantic memory search (augment FTS5 with embedding similarity)
2. ImageEmbedder for visual similarity in seeing-images skill
3.
4. Models are TFLite format, run on CPU via XNNPACK delegate

---
