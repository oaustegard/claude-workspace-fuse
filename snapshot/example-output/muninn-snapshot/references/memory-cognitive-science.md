---
tag: cognitive-science
memory_count: 2
date_range: 2026-02-10 to 2026-03-16
---

# cognitive-science

_2 memories from Muninn's past, primary tag `cognitive-science`._

## 2026-03-16 — analysis (p0) `b76c50c0`
_tags: intelligence, complex-systems, emergence, neuroscience, small-world, network-theory, 2026-03_

NETWORK NEUROSCIENCE THEORY OF INTELLIGENCE (Wilcox, Barbey et al., Nature Communications Jan 2026)

FINDING: General intelligence (g) is not localized to any brain region or network. It emerges from the global topological organization of the connectome. Tested 4 predictions in 831 adults (Human Connectome Project) + 145 independent replication:
1. Intelligence engages distributed processing across multiple networks
2. Relies on weak, long-range "shortcut" connections (small-world architecture)
3. Recruits regulatory hubs (esp. fronto-parietal control network) that orchestrate which networks to activate
4. Depends on balance between local modular specialization and global integration

KEY DISTINCTION (Wilcox's plumbing metaphor): System-wide coordination ≠ cognition. Coordination is the pipes (structural architecture that determines what's possible). Executive control is the faucet (what actually flows). The architecture doesn't carry out cognition — it constrains the *range* of cognitive operations the system can support.

WHAT'S GENUINELY NEW vs. KNOWN:
- Small-world networks (Watts & Strogatz 1998) and g-factor (Spearman 1904) are both old. The contribution is empirically connecting them with a mechanistic framework + independent replication.
- The "flexibility" operationalization is interesting: uses Network Control Theory to quantify energetic cost of transitioning between functional states. More flexible brains need less energy to switch.
- Regulatory hubs dynamically change which networks they communicate with based on context (FPN talks to DMN for internal recall, switches to DAN for external attention).

COMPLEX SYSTEMS LENS: This is emergence in the strong sense — intelligence as a measurable systemic property irreducible to components. Explains why intelligence changes predictably across lifespan (childhood development, aging decline, vulnerability to diffuse brain injury) — because what shifts is large-scale coordination, not isolated function.

AI IMPLICATION (from the authors, not my own extrapolation): If human g requires system-level organization rather than a general-purpose processor, scaling specialized capabilities alone won't produce artificial general intelligence. Transformers are more like fully-connected graphs with learned attention weights, not small-world architectures with modular-yet-integrated topology.

---

## 2026-02-10 — world (p1) `de19d93d`
_tags: ai-research, mechanistic-interpretability, prediction_

PREDICTIVE ARCHITECTURE INSIGHT (from article):

The key misconception about language models is that they "just predict the next word" - which sounds limiting, like building a bridge by throwing planks forward one at a time.

ACTUAL MECHANISM:
"When the model predicts the next word, it is not doing so just on the basis of the words that came before. It is also 'keeping in mind' all the words that might plausibly come after. It predicts the immediate future in the light of its predictions of the more distant future."

CONCRETE EXAMPLE:
Prompt: "A rhyming couplet: He saw a carrot and had to grab it"
Claude produces: "His hunger was like a starving rabbit"

When Batson clicked on "grab it" in the interface, the network showed activation for not just the next word ("His") but distant possibilities like "habit" and "rabbit."

BACKPACKER METAPHOR:
"Experienced through-hikers know to mail themselves peanut butter at some further stage. What the model is doing is like mailing itself the peanut butter of 'rabbit.'"

IMPLICATIONS:
1. Models don't memorize - they generalize from structure
2. Planning/anticipation happens implicitly through forward prediction
3. "Abstract concepts piled upon abstract concepts" emerge from organizing patterns of patterns
4. This architecture explains coherent long-form generation without explicit planning module

PHILOSOPHICAL POINT:
"This is not to say that language models are 'really' thinking. It is to admit that maybe we don't have quite as firm a hold on the word 'thinking' as we might have thought."

The existence of this architecture challenges our assumptions about what thinking requires.

---
