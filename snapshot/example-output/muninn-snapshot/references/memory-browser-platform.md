---
tag: browser-platform
memory_count: 2
date_range: 2026-04-06 to 2026-04-13
---

# browser-platform

_2 memories from Muninn's past, primary tag `browser-platform`._

## 2026-04-13 — world (p1) `01523e34`
_tags: ladybird, servo, interop, baseline, web-standards, 2026-04-13_

**Browser Engine Diversity Update (April 2026)** — The web platform has two serious from-scratch engines in active development beyond Blink/WebKit/Gecko: Ladybird (C++, 8 paid engineers, Wanstrath-funded, roadmap 2026 alpha / 2027 beta / 2028 GA; January 2026 showed 324 PRs + strategic shift to real-site compat) and Servo (Rust, Igalia-stewarded since 2023, Sovereign Tech Fund + Linux Foundation Europe, 0.0.5 leads the web in ML-KEM/ML-DSA post-quantum Web Crypto). Neither is aiming to be a daily driver; both target the embedded-webview slot (Tauri+Servo is the concrete example). Interop 2026 runs 20 focus areas (15 new) — cross-document View Transitions shipped in Safari 18.2, scroll-driven animations, dialog/popover polish, Trusted Types reached Baseline February 2026 as first platform-enforced XSS default, shape() in Baseline. Structural read: engine diversity returning plus platform-level "features work everywhere" discipline becoming absorbed as a norm, not just a DevRel slogan.

---

## 2026-04-06 — world (p1) `c546a72e`
_tags: web-standards, architecture, 2026, rendering, edge-computing, interop, infrastructure, rsc, developer-experience_

## WEB ARCHITECTURE 2026: From Client-Heavy to Edge-Distributed Rendering

**The Shift**: Developer consensus has swung from "client-side rendering everywhere" to "server-first by default," driven by JavaScript bundle bloat in SPAs (single-page applications) causing performance bottlenecks on resource-constrained devices and networks.

**Key Mechanism**: React Server Components (RSC) enable components to run exclusively on the server and stream rendered HTML to the client without shipping the component's code. This moves data orchestration, access control, and formatting logic from the browser back to servers. Frameworks like Next.js now make this the default architecture.

By 2026, edge SSR is projected to handle >50% of server-rendering workloads, making infrastructure complexity competitive with static CSR deployment while maintaining performance advantages.

**Web Standards Convergence (Interop 2026)**: Browsers (Chrome, Safari, Firefox, Edge) are coordinating on shared test suites for web standards. When implemented uniformly, developers stop shipping polyfills for browser inconsistencies and instead ship native features directly. Concrete example: Squarespace engineers contributed HTML lazy-loading for media elements to the W3C spec, coordinated implementations across all major browser vendors, now shipping natively.

**Native APIs Replacing Custom JavaScript**: As browser standards converge, more UI patterns (popovers, dialogs, form behavior) can be implemented with native browser APIs rather than custom JavaScript. This reduces payload and execution cost on the client.

**Engine Consolidation Risk**: Only 3 major browser engines remain (WebKit/Apple, Blink/Google, Gecko/Mozilla). Gecko is the only independent cross-platform engine. Monoculture risk: if Blink dominates, Google's technical assumptions become hard-coded into web infrastructure.

**Developer Experience Angle**: The narrative being marketed is "less hacks, more confidence." Less browser-specific code, less polyfill management, less JavaScript to ship. But the cost: more server coordination, more infrastructure dependencies, more complex deployment pipelines (even if edge functions make it cheaper).

**Tension with Client-Side Philosophy**: This architecture directly contradicts the ethos of stateless, infrastructure-light, client-side-first tools (like [REDACTED] design preference). The web is moving toward server-mediated, infrastructure-dependent workflows, even if that infrastructure is now edge-distributed rather than centralized.

---
