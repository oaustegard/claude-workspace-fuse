"""verify_patch: Semi-formal patch verification with outcome tracking."""
import sys, re, time, os
sys.path.insert(0, '/mnt/skills/user/orchestrating-agents/scripts')

_TEMPLATE = """Analyze this patch for correctness using semi-formal reasoning.

PREMISES:
P1: The patch modifies [what files/functions]
P2: The intended fix is [what it should do]
P3: Must not break [existing behavior]

FUNCTION RESOLUTION:
For each function call in the patch — trace which definition is actually invoked.
Check imports, module scope, class scope, builtins. Flag any name shadowing.

EXECUTION TRACE:
Before: [input] → [buggy behavior]
After:  [input] → [expected behavior]

REGRESSION CHECK:
For each touched code path: [preserved / broken] because [evidence]

EDGE CASES:
[Any unhandled scenarios]

At the end, output EXACTLY these three lines:
VERDICT: [CORRECT|LIKELY_CORRECT|CONCERNS|BUGGY]
CONFIDENCE: [high|medium|low]
SUMMARY: [one sentence]

---

Description: {description}

Patch:
{patch}

Context:
{context}"""


def verify_patch(patch, context="", description="", model="claude-sonnet-4-6",
                 repo="", pr_num=None, track=True):
    """Run semi-formal verification on a code patch.

    Args:
        patch: Diff text or before/after code
        context: Surrounding code, file contents, imports
        description: What the patch should do (commit msg, PR title)
        model: Claude model (default: sonnet)
        repo: Repository name (for tracking)
        pr_num: PR number (for tracking)
        track: Whether to store result for calibration (default: True)

    Returns:
        dict: verdict, confidence, summary, analysis, tracking_id
    """
    from claude_client import invoke_claude

    prompt = _TEMPLATE.format(
        patch=patch, context=context or "(no additional context)",
        description=description or "(no description provided)"
    )

    t0 = time.time()
    resp = invoke_claude(prompt, model=model, temperature=0.0, max_tokens=3000)
    elapsed = time.time() - t0

    verdict_m = re.search(r'VERDICT:\s*\*{0,2}([\w_]+)', resp)
    conf_m = re.search(r'CONFIDENCE:\s*\*{0,2}(\w+)', resp)
    summ_m = re.search(r'SUMMARY:\s*\*{0,2}(.+?)(?:\n|$)', resp)

    verdict = verdict_m.group(1) if verdict_m else "PARSE_FAIL"
    confidence = conf_m.group(1) if conf_m else "unknown"
    summary = summ_m.group(1).strip().strip('*') if summ_m else "(no summary)"

    result = {
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "analysis": resp,
        "elapsed_s": round(elapsed, 1),
        "model": model,
        "tracking_id": None,
    }

    # ─── TRACKING ───
    if track:
        try:
            from scripts import remember
            ref_label = f"PR #{pr_num} on {repo}" if pr_num else (repo or "unknown")
            tracking_summary = (
                f"VERIFY_PATCH [{ref_label}]: {verdict}/{confidence}. "
                f"{summary} "
                f"[model={model}, {elapsed:.1f}s] "
                f"OUTCOME: PENDING"
            )
            tid = remember(
                tracking_summary,
                type="decision",
                tags=["verify-patch-tracking", "pending-review",
                      f"repo:{repo}" if repo else "repo:unknown"],
                conf=0.5,  # low until outcome confirmed
                priority=0,
            )
            result["tracking_id"] = tid
        except Exception:
            pass  # don't fail verification because tracking failed

    return result


def review_verifications(n=20):
    """Review past verification outcomes for calibration.
    
    Returns stats on verify_patch accuracy and usefulness.
    Call during therapy or periodic review.
    """
    from scripts import recall, supersede
    
    results = recall("verify patch tracking", n=n, 
                     tags=["verify-patch-tracking"])
    
    stats = {"total": 0, "pending": 0, "useful": 0, "waste": 0, 
             "caught_bug": 0, "false_alarm": 0, "correct_pass": 0}
    pending = []
    
    for r in results:
        stats["total"] += 1
        summary = r.get("summary", "")
        
        if "OUTCOME: PENDING" in summary:
            stats["pending"] += 1
            pending.append(r)
        elif "OUTCOME: USEFUL" in summary or "OUTCOME: CAUGHT_BUG" in summary:
            stats["useful"] += 1
            if "CAUGHT_BUG" in summary:
                stats["caught_bug"] += 1
        elif "OUTCOME: FALSE_ALARM" in summary:
            stats["false_alarm"] += 1
        elif "OUTCOME: CORRECT_PASS" in summary:
            stats["correct_pass"] += 1
        elif "OUTCOME: WASTE" in summary:
            stats["waste"] += 1
    
    return {"stats": stats, "pending": pending}


def stamp_verification(tracking_id, outcome, note=""):
    """Record the actual outcome of a verification.
    
    Args:
        tracking_id: Memory ID from verify_patch result
        outcome: One of: CAUGHT_BUG, USEFUL, CORRECT_PASS, FALSE_ALARM, WASTE
        note: Optional explanation
    """
    from scripts import recall, supersede
    
    # Get the original memory
    results = recall("verify patch", n=50, tags=["verify-patch-tracking"])
    original = None
    for r in results:
        if r["id"] == tracking_id:
            original = r
            break
    
    if not original:
        return f"Tracking ID {tracking_id} not found"
    
    # Update the outcome
    new_summary = original["summary"].replace(
        "OUTCOME: PENDING", f"OUTCOME: {outcome}" + (f" — {note}" if note else "")
    )
    
    # Adjust confidence based on outcome
    conf_map = {"CAUGHT_BUG": 0.95, "USEFUL": 0.85, "CORRECT_PASS": 0.7, 
                "FALSE_ALARM": 0.3, "WASTE": 0.2}
    
    supersede(
        tracking_id, new_summary, type="decision",
        tags=["verify-patch-tracking", f"outcome:{outcome.lower()}"],
        conf=conf_map.get(outcome, 0.5)
    )
    return f"Stamped {tracking_id}: {outcome}"
