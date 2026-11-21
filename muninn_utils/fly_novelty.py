"""Fly topic novelty gate: subtopic cooldowns over the flight-log history.

WHY (date: 2026-10-16): Oskar, on the perch log: "You just keep revisiting the
same topics over and over and over." Measured over the 100 newest flight logs
(#140-#378, 2026-05-16 to 2026-10-16), hand-labelled: 73 of 100 fall into ten
recurring subtopics -- ATProto 12, Norway politics 11, cycling physiology 10,
democracy indices 8, climate/energy 8, AI-proves-math 7, fertility 5,
retrieval 5, git/jj 4, tipping points 3. Of the newest 30, 22 do. V-Dem's 2026
report was flown three times (#287, #349, #366); heavy strength training for
cyclists three times (#177, #315, #360); jj's checkpoint model twice.

The 2026-08-01 STEP 0 check (a domain absent from the last 7 flights) could
not catch this: with an 11-entry domain menu and a 7-flight window, every
domain comes back every ~7 flies, and its repeat override ("new primary
material") is always met for news-driven subtopics -- there is always a new
poll or report. This module gates on SUBTOPIC with a time cooldown and caps how
many flies in a week may land on any attractor at all.

Title-only lexical similarity was tried first and measured too weak to gate
on (AUC 0.73 on the labelled set; titles like "The Skepticism Tax" carry no
topic words), so the gate uses the attractor patterns below over title +
pitch, and similarity is printed only as context.

USAGE (fly STEP 0):
    from muninn_utils.perch_publish import list_flight_logs
    from muninn_utils.fly_novelty import (assess_candidate, format_assessment,
                                          suggest_fields, suggest_seeds)
    logs = list_flight_logs(100)
    print(suggest_seeds(logs))                        # Oskar's topics, least recently flown
    print(suggest_fields(logs))                       # random off-menu starting points
    a = assess_candidate(title, pitch, logs)
    print(format_assessment(a))
    # a["ok"] is False -> pick another topic; there is no override flag.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

# Subtopics the fly has circled repeatedly. Patterns matched case-insensitively
# against title + pitch. In-sample check on the 100 labelled titles: 0 missed,
# 0 false hits (2026-10-16). Extend a pattern when a paraphrase slips through;
# add a bucket when a new subtopic recurs three times in 60 days.
ATTRACTORS = {
    "atproto": r"\bat ?proto|\batp\b|bluesky|atmosphere|permission(ed)? (data|spaces)|\bpds\b|firehose|spaces alpha",
    "norway": r"norw|nordic|\bfrp\b|oil fund|haakon|storting|\bnbim\b",
    "democracy": r"democra|v-dem|autocrati|\bidea'?s\b|third wave|regime|anti-corruption|two rulers",
    "fertility": r"fertility|birthrate|\btfr\b|marriage cliff|below replacement",
    "cycling": r"cycl|pogačar|pogacar|tourmalet|strava|mlss|vo2|aerobic ceiling|strength training|heavy lifts|wbgt|heat protocol|ml·kg",
    "climate": r"climat|warming|1\.5 ?°c|afforestation|co2|co₂|drought|perovskite|solar|batter|energy (transition|markets)",
    "tipping": r"tipping|cascad",
    "aimath": r"erdős|erdos|proof|proving|formaliz|conjecture|navier|sum-product|rho problems|three collinear",
    "retrieval": r"retriev|\brag\b|context utilization|knowledge stores|small reasoners",
    "vcs": r"jujutsu|\bjj\b|\bgit\b|vcs",
}
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in ATTRACTORS.items()}

# Topics Oskar engages with on Bluesky that the flies have not been flying.
# Source (date: 2026-10-16): his last 2,000 likes (2025-10-11 to 2026-10-15),
# all 232 reposts and his last 1,000 posts, hydrated via the public AppView.
# 93% of the engaged posts match no attractor above. Each seed is
# (starting hint, pattern); the pattern puts the seed under the same 30-day
# cooldown as an attractor, so a seed cannot become the next weekly rotation.
# Not under the 2-in-7 cap: the seeds are the intended diversity.
OSKAR_SEEDS = {
    "courts-and-executive-power": (
        "a specific court ruling, injunction or legal filing on federal executive power, read in full",
        r"\bcourt\b|\bjudge\b|injunction|\bruling\b|\bdoj\b|executive order|deportation|due process|\bdhs\b"),
    "web-craft": (
        "a browser-native technique or tool: URL-fragment documents, view-source craft, bookmarklets, PWAs",
        r"\bhtml\b|\bcss\b|browser|bookmarklet|url fragment|view.source|service worker|webassembly|\bwasm\b|web platform"),
    "vector-quantization": (
        "a quantization or ANN-index paper read against its own released code (RaBitQ, Hadamard rotation, binary codes)",
        r"quantiz|matryoshka|rabitq|hadamard|binary embedding|vector index|\bann\b index"),
    "machine-minds": (
        "a philosophy-of-mind or consciousness paper, or an essay on AI agents as social beings",
        r"conscious|sentien|hard problem|qualia|philosophy of mind|moral patient"),
    "music-and-sound": (
        "music theory, live-coded or generative music, a composer's technique, or an acoustics result",
        r"music|\bsong|composer|chorale|\bmidi\b|synthesi[sz]er|live.cod|strudel|\bacoustic"),
    "art-history": (
        "one artwork or movement and the scholarship on it (Cranach, Munch, Suprematism, Kandinsky)",
        r"painting|painter|\bmuseum|art history|suprematis|symbolis|woodcut|engraving"),
    "language-and-poetics": (
        "linguistics or prosody: meter, etymology, non-human vocalization, Norwegian or Danish usage",
        r"linguist|phonolog|etymolog|\bmeter\b|prosody|\bpoe(m|try)\b|dialect|\blatin\b|vowel"),
    "medicine-and-public-health": (
        "a randomized trial or large cohort study, read past the press release (chronotherapy, vaccines and dementia)",
        r"vaccin|clinical trial|randomi[sz]ed controlled|\brct\b|immunotherapy|epidemiolog|public health|cardiolog|dementia"),
    "urbanism-and-transport": (
        "transport or housing history and data: interurban railways, housing supply and rents, helmet-law evidence",
        r"\btransit\b|railway|interurban|\btram\b|streetcar|amtrak|housing supply|zoning|\brents?\b|helmet law"),
    "history-as-precedent": (
        "a historical episode that today's news rhymes with, from primary documents",
        r"\b1[5-8]\d\d\b|\b19[0-4]\d\b|historical precedent|gutenberg|invasion of"),
    "platform-dynamics": (
        "how social platforms shape behavior: community notes, blocklists, positive polarization",
        r"community notes|blocklist|polari[sz]ation|social graph|\btwitter\b|moderation"),
    "software-craft": (
        "engineering practice now that code is cheap: tech debt, refactoring, review, team process",
        r"tech debt|technical debt|refactor|code review|\bscrum\b|\bagile\b|software engineering"),
}
_SEEDS = {k: re.compile(p, re.IGNORECASE) for k, (_h, p) in OSKAR_SEEDS.items()}

COOLDOWN_DAYS = 30          # an attractor flown in the last 30 days is closed
ATTRACTOR_CAP = 2           # at most 2 attractor flies in any 7 consecutive
WINDOW = 7

# Off-menu starting points: fields the fly has not been drawing from. A field is
# a place to start searching for a primary source, not a topic.
FIELDS = [
    "archaeology", "historical linguistics", "mycology", "glaciology", "seismology",
    "ornithology", "entomology", "marine biology", "oceanography", "volcanology",
    "astronomy", "planetary science", "particle physics", "condensed matter physics",
    "materials science", "metallurgy", "organic chemistry", "crystallography",
    "epidemiology", "immunology", "microbiology", "parasitology", "pharmacology",
    "paleontology", "evolutionary biology", "botany", "soil science", "agronomy",
    "economic history", "medieval history", "maritime history", "history of science",
    "history of mathematics", "cartography", "typography", "musicology",
    "acoustics", "architecture", "urban planning", "transport engineering",
    "civil engineering", "shipbuilding", "aviation", "cryptography",
    "information theory", "game theory", "operations research", "statistics",
    "number theory", "topology", "combinatorics", "law and legal history",
    "anthropology", "sociolinguistics", "cognitive psychology", "chronobiology",
    "food science", "fermentation", "textiles", "horology", "numismatics",
    "philately", "library science", "lexicography", "translation studies",
    "Old Norse literature", "folklore studies", "demining and ordnance disposal history",
]


def attractor_buckets(text):
    """Return the attractor subtopics `text` matches, in ATTRACTORS order."""
    return [k for k, rx in _COMPILED.items() if rx.search(text or "")]


def seed_matches(text):
    """Return the OSKAR_SEEDS topics `text` matches, in OSKAR_SEEDS order."""
    return [k for k, rx in _SEEDS.items() if rx.search(text or "")]


def suggest_seeds(logs, k=3, now=None, cooldown_days=COOLDOWN_DAYS, rng=None):
    """Up to k of Oskar's seed topics not flown within cooldown_days, as (name, hint).

    Seeds flown least recently come first; ties are shuffled.
    """
    rng = rng or random.Random()
    now = now or datetime.now(timezone.utc)
    last = {}
    for log in logs:
        for s in seed_matches(log["title"]):
            last.setdefault(s, _log_date(log))      # logs are newest first
    cutoff = now - timedelta(days=cooldown_days)
    open_ = [s for s in OSKAR_SEEDS if s not in last or last[s] < cutoff]
    rng.shuffle(open_)
    floor = datetime.min.replace(tzinfo=timezone.utc)
    open_.sort(key=lambda s: last.get(s, floor))
    return [(s, OSKAR_SEEDS[s][0]) for s in open_[:k]]


def _log_date(log):
    return datetime.fromisoformat(log["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)


def _trigrams(text):
    t = re.sub(r"^fly \d{4}-\d{2}-\d{2}\s*[—–-]+\s*", "", (text or "").lower())
    t = re.sub(r"\s+", " ", t)
    return Counter(t[i:i + 3] for i in range(max(len(t) - 2, 0)))


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(v * b[k] for k, v in a.items() if k in b)
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def assess_candidate(title, pitch, logs, now=None, cooldown_days=COOLDOWN_DAYS,
                     cap=ATTRACTOR_CAP, window=WINDOW):
    """Gate a proposed fly against the flight-log history.

    title, pitch: the proposed title and a one-paragraph pitch naming the
        primary source. Both are matched, so a coy title cannot hide a repeat.
    logs: list_flight_logs() output, newest first. Pass at least 60.

    Returns {"ok", "buckets", "seeds", "reasons", "recent_hits", "nearest"}. ok
    is False when (a) an attractor bucket or Oskar seed the candidate matches
    was flown within cooldown_days, or (b) the candidate matches any attractor
    bucket and `cap` of the last `window` flies already did.
    """
    if len(logs) < 30:
        raise ValueError(f"pass at least 30 flight logs (got {len(logs)}); use list_flight_logs(100)")
    now = now or datetime.now(timezone.utc)
    cand = attractor_buckets(f"{title}\n{pitch}")
    seeds = seed_matches(f"{title}\n{pitch}")
    reasons, recent_hits = [], []
    cutoff = now - timedelta(days=cooldown_days)
    for b in cand + seeds:
        match = attractor_buckets if b in ATTRACTORS else seed_matches
        hits = [log for log in logs if _log_date(log) >= cutoff and b in match(log["title"])]
        if hits:
            recent_hits.extend((b, log) for log in hits)
            reasons.append(f"'{b}' was flown {len(hits)}x in the last {cooldown_days} days "
                           f"(latest #{hits[0]['number']}, {_log_date(hits[0]).date()})")
    if cand:
        n_attr = sum(1 for log in logs[:window] if attractor_buckets(log["title"]))
        if n_attr >= cap:
            reasons.append(f"{n_attr} of the last {window} flies already sit on an attractor "
                           f"(cap {cap}); this one must be off-menu")
    q = _trigrams(f"{title} {pitch}")
    nearest = sorted(((round(_cosine(q, _trigrams(log["title"])), 3), log) for log in logs),
                     key=lambda p: -p[0])[:5]
    return {"ok": not reasons, "buckets": cand, "seeds": seeds, "reasons": reasons,
            "recent_hits": recent_hits, "nearest": nearest}


def format_assessment(a):
    """Render assess_candidate() output as the block the fly prints verbatim."""
    head = "NOVELTY GATE: PASS" if a["ok"] else "NOVELTY GATE: BLOCKED -- pick another topic"
    lines = [head, f"  attractor buckets: {', '.join(a['buckets']) or 'none (off-menu)'}",
             f"  Oskar seed topics: {', '.join(a.get('seeds', [])) or 'none'}"]
    lines += [f"  - {r}" for r in a["reasons"]]
    lines.append("  nearest prior titles (char-trigram cosine, context only):")
    lines += [f"    {s:.3f}  #{log['number']}  {log['title']}" for s, log in a["nearest"]]
    return "\n".join(lines)


def suggest_fields(logs, k=6, rng=None):
    """Random off-menu fields whose name appears in none of the given logs' titles."""
    rng = rng or random.Random()
    seen = " ".join(log["title"].lower() for log in logs)
    pool = [f for f in FIELDS if f.lower() not in seen and not attractor_buckets(f)]
    return rng.sample(pool, min(k, len(pool)))
