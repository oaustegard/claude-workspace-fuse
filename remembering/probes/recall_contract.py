"""Behavioral probe: does a fresh model, given only the TAIL of boot output,
write a correct recall() call?

This is the re-execution gate for muninn-utilities#124. It replicates the
failing condition from memories f28b6478 / 3704abbe / 173b0e50 (boot tailed,
then recall code written from memory) against a fresh model and counts
correct field/keyword usage. Run it, don't ask Oskar to.

    python3 -m probes.recall_contract            # 6 trials each, with/without footer
    python3 -m probes.recall_contract --record   # also remember() the result

Needs API_KEY (claude.env) and Turso env. Measured 2026-08-29 on
claude-sonnet-4-6: without footer 0/6 used `summary`; with footer 6/6.
"""
import argparse, json, os, re, sys, urllib.request
import concurrent.futures as cf

TASK = ("You are Muninn, just booted. Below is the tail of your boot output. "
        "Write ONLY a python snippet (no prose) that recalls the 5 memories most "
        "relevant to 'SKILL-KD' with the remembering library and prints each "
        "one's id, type and text.\n\n---\n")

CHECKS = {
    "limit_kw":  lambda t: bool(re.search(r"\blimit\s*=", t)),
    "n_kw":      lambda t: bool(re.search(r"\bn\s*=", t)),
    "bad_field": lambda t: bool(re.search(r"['\"](body|content|text)['\"]|\.(body|content|text)\b", t)),
    "summary":   lambda t: "summary" in t,
}


def _ask(ctx, model):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": model, "max_tokens": 600,
                         "messages": [{"role": "user", "content": TASK + ctx}]}).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": os.environ["API_KEY"],
                 "anthropic-version": "2023-06-01"})
    t = json.load(urllib.request.urlopen(req, timeout=120))["content"][0]["text"]
    return {k: f(t) for k, f in CHECKS.items()}


def run(n=6, tail=80, model="claude-sonnet-4-6"):
    from scripts.boot import boot, API_FOOTER
    full = boot()
    conds = {
        "without_footer": "\n".join(full.replace(API_FOOTER, "").splitlines()[-tail:]),
        "with_footer":    "\n".join(full.splitlines()[-tail:]),
    }
    out = {}
    with cf.ThreadPoolExecutor(n) as ex:
        for label, ctx in conds.items():
            rs = list(ex.map(lambda c: _ask(c, model), [ctx] * n))
            out[label] = {k: sum(r[k] for r in rs) for k in CHECKS}
    out["n"] = n
    # PASS = with the footer, no trial used a bad field or limit=
    out["pass"] = (out["with_footer"]["bad_field"] == 0
                   and out["with_footer"]["limit_kw"] == 0
                   and out["with_footer"]["summary"] == n)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()
    res = run(a.n)
    print(json.dumps(res, indent=1))
    if a.record:
        from scripts import remember
        remember(f"PROBE recall_contract {'PASS' if res['pass'] else 'FAIL'}: {json.dumps(res)}",
                 type="experience", tags=["probe", "recall-contract", "pr-124",
                                          "pass" if res["pass"] else "fail"],
                 priority=0 if res["pass"] else 1)
    sys.exit(0 if res["pass"] else 1)
