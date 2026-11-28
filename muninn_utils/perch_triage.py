"""Perch flight log triage via GitHub discussion reactions.

Reaction → action mapping:
  THUMBS_UP / LAUGH  → Auto-close, store minimal summary
  THUMBS_DOWN        → Close, note "not useful" 
  HEART              → Prioritize in dream review for discussion
  ROCKET             → Actionable — file GH issues from findings
  EYES               → Seen, hold for discussion (don't close)
  CONFUSED           → Flag for correction
  HOORAY             → Close with satisfaction-analog

Comments outrank reactions. A comment from Oskar posted after Muninn's last
reply lands in the `respond` bucket regardless of any reaction, and a log in
that bucket is never auto-closed. A 👍 plus "you should explore this" must not
close the log and drop the request (discussion #331 sat unanswered for a week
because triage routed on reactions alone and read no comment text).

Muninn and Oskar post through the same PAT, so both show up as `oaustegard`.
Muninn's comments carry MUNINN_MARKER (an invisible HTML comment) to tell them
apart. Post through `reply()` so the marker is always there.

Unreacted logs older than NAG_DAYS → nag Oskar to triage.
"""
from datetime import datetime, timezone, timedelta

CATEGORY_ID = "DIC_kwDORr5Vj84C5A3Z"  # Flight Log (oaustegard/muninn.austegard.com)
OWNER = "oaustegard"
REPO = "muninn.austegard.com"
NAG_DAYS = 3
MUNINN_MARKER = "<!-- muninn -->"

# Reaction → action type
ACTION_MAP = {
    "THUMBS_UP": "auto_close",
    "LAUGH": "auto_close",
    "THUMBS_DOWN": "close_not_useful",
    "HEART": "discuss_priority",
    "ROCKET": "file_issues",
    "EYES": "hold",
    "CONFUSED": "correction",
    "HOORAY": "close_celebrate",
}


def _gh_graphql(query, variables=None):
    """Execute a GitHub GraphQL query. Returns response["data"].

    Routes through muninn_utils.gh_proxy rather than hitting api.github.com
    directly. Anthropic's session egress proxy serves only a pinned set of
    GraphQL operations and 403s everything else with a docs.anthropic.com
    documentation_url; the discussion query and the close/comment mutations
    below are not in that set, so the direct transport was dead here. gh_proxy
    keys on that tell and falls back to gh-api-proxy, which forwards the
    Authorization header verbatim on any method and any path — /graphql
    included.

    The import is function-local on purpose: gh_proxy reaches Turso for the
    proxy key on first use, so hoisting it would make importing this module do
    network I/O. gh_proxy.graphql already raises GitHubTransportError (a
    RuntimeError) both for a missing/placeholder token and for a populated
    `errors` key, which is the same contract this helper had.
    """
    from . import gh_proxy
    return gh_proxy.graphql(query, variables)


def _is_muninn(body):
    return MUNINN_MARKER in (body or "")


def reply(node_id, body):
    """Comment on a flight log as Muninn. Returns the comment URL.

    Appends MUNINN_MARKER so later triage runs count this as Muninn's answer
    and stop surfacing the Oskar comments that precede it.
    """
    if not _is_muninn(body):
        body = f"{body.rstrip()}\n\n{MUNINN_MARKER}"
    data = _gh_graphql(
        """mutation($id: ID!, $body: String!) {
            addDiscussionComment(input: {discussionId: $id, body: $body}) {
                comment { id url }
            }
        }""",
        {"id": node_id, "body": body},
    )
    return data["addDiscussionComment"]["comment"]["url"]


def unanswered_comments(comments):
    """Oskar's comments newer than Muninn's latest marked reply, oldest first."""
    last_reply = max(
        (c["createdAt"] for c in comments if _is_muninn(c["body"])), default=""
    )
    return [
        c for c in comments
        if c["author"] and c["author"]["login"] == OWNER
        and not _is_muninn(c["body"])
        and c["createdAt"] > last_reply
    ]


def _close_discussion(node_id, comment=None):
    """Close a discussion, optionally adding a comment first."""
    if comment:
        reply(node_id, comment)
    _gh_graphql(
        """mutation($id: ID!) {
            closeDiscussion(input: {discussionId: $id, reason: RESOLVED}) {
                discussion { id closed }
            }
        }""",
        {"id": node_id},
    )


def fetch_open_logs(limit=25):
    """Fetch open flight logs with reactions and comments.

    Each log carries `unanswered`: Oskar comments Muninn has not replied to.
    """
    data = _gh_graphql(
        """query($owner: String!, $repo: String!, $categoryId: ID!, $limit: Int!) {
            repository(owner: $owner, name: $repo) {
                discussions(first: $limit, categoryId: $categoryId,
                            orderBy: {field: UPDATED_AT, direction: DESC}) {
                    nodes {
                        id number title closed createdAt updatedAt
                        body
                        reactionGroups {
                            content
                            reactors(first: 1) { totalCount }
                        }
                        comments(last: 30) {
                            nodes { author { login } body createdAt }
                        }
                    }
                }
            }
        }""",
        {"owner": OWNER, "repo": REPO, "categoryId": CATEGORY_ID, "limit": limit},
    )
    logs = []
    for d in data["repository"]["discussions"]["nodes"]:
        if d["closed"]:
            continue
        reactions = {
            r["content"]: r["reactors"]["totalCount"]
            for r in d["reactionGroups"]
            if r["reactors"]["totalCount"] > 0
        }
        comments = sorted(d["comments"]["nodes"], key=lambda c: c["createdAt"])
        odin_comments = [
            c for c in comments
            if c["author"] and c["author"]["login"] == OWNER
            and not _is_muninn(c["body"])
        ]
        logs.append({
            "node_id": d["id"],
            "number": d["number"],
            "title": d["title"],
            "created": d["createdAt"],
            "updated": d["updatedAt"],
            "body": d["body"],
            "reactions": reactions,
            "odin_comments": odin_comments,
            "unanswered": unanswered_comments(comments),
        })
    return logs


def pending_comments(limit=25):
    """Open flight logs with Oskar comments awaiting a Muninn reply.

    The inbox-review routine calls this; dream review gets the same logs via
    triage()'s `respond` bucket.
    """
    return [log for log in fetch_open_logs(limit) if log["unanswered"]]


def triage(logs=None, auto_close=True, nag_days=NAG_DAYS):
    """Triage open flight logs by reaction signals.
    
    Returns dict with action groups:
      respond: Oskar commented after Muninn's last reply; outranks reactions
      auto_closed: list of logs that were auto-closed (if auto_close=True)
      discuss_priority: HEART-reacted, prioritize in review
      file_issues: ROCKET-reacted, need GH issues created
      hold: EYES-reacted, surface but don't close
      correction: CONFUSED-reacted, something's wrong
      close_not_useful: THUMBS_DOWN, will close with note
      close_celebrate: HOORAY, will close with satisfaction-analog
      nag: unreacted and older than nag_days
      unreacted_recent: unreacted but still fresh
    """
    if logs is None:
        logs = fetch_open_logs()
    
    now = datetime.now(timezone.utc)
    result = {
        "respond": [],
        "auto_closed": [],
        "discuss_priority": [],
        "file_issues": [],
        "hold": [],
        "correction": [],
        "close_not_useful": [],
        "close_celebrate": [],
        "nag": [],
        "unreacted_recent": [],
    }
    
    for log in logs:
        if log.get("unanswered"):
            result["respond"].append(log)
            continue
        reactions = log["reactions"]
        if not reactions:
            # Unreacted — check age
            created = datetime.fromisoformat(log["created"].replace("Z", "+00:00"))
            age_days = (now - created).days
            if age_days >= nag_days:
                log["age_days"] = age_days
                result["nag"].append(log)
            else:
                log["age_days"] = age_days
                result["unreacted_recent"].append(log)
            continue
        
        # Determine primary action (highest-priority reaction wins)
        # Priority: ROCKET > HEART > CONFUSED > EYES > HOORAY > THUMBS_DOWN > THUMBS_UP/LAUGH
        priority_order = ["ROCKET", "HEART", "CONFUSED", "EYES", "HOORAY", "THUMBS_DOWN", "THUMBS_UP", "LAUGH"]
        action = None
        for r in priority_order:
            if r in reactions:
                action = ACTION_MAP[r]
                break
        
        if action == "auto_close":
            if auto_close:
                # Extract first line of body as summary
                first_line = (log["body"] or "").split("\n")[0][:200]
                from scripts import remember as _remember
                mem_id = _remember(
                    f"Perch flight log #{log['number']}: {log['title']}. {first_line}",
                    type="world",
                    tags=["perch", "dream-review", f"flight-log-{log['number']}"],
                )
                _close_discussion(log["node_id"], f"Auto-closed via 👍 triage. Memory: `{mem_id}`")
                log["memory_id"] = mem_id
            result["auto_closed"].append(log)
        else:
            result[action].append(log)
    
    return result


def triage_report(result=None):
    """Format triage results as a concise report string."""
    if result is None:
        result = triage()
    
    lines = []

    if result.get("respond"):
        lines.append(f"**Comments awaiting a reply** 💬 ({len(result['respond'])}):")
        for l in result["respond"]:
            lines.append(f"  - #{l['number']}: {l['title']}")
            for c in l["unanswered"]:
                first = next((x for x in c["body"].splitlines() if x.strip()), "")
                lines.append(f"    > {c['createdAt'][:10]}: {first[:160]}")

    if result["auto_closed"]:
        lines.append(f"**Auto-closed** ({len(result['auto_closed'])}):")
        for l in result["auto_closed"]:
            mid = l.get("memory_id", "")
            lines.append(f"  - #{l['number']}: {l['title']}" + (f" → `{mid}`" if mid else ""))
    
    for key, label, emoji in [
        ("discuss_priority", "Discuss (priority)", "❤️"),
        ("file_issues", "File issues from", "🚀"),
        ("hold", "Holding for discussion", "👀"),
        ("correction", "Needs correction", "😕"),
        ("close_not_useful", "Not useful (will close)", "👎"),
        ("close_celebrate", "Celebrate & close", "🎉"),
    ]:
        if result[key]:
            lines.append(f"**{label}** {emoji} ({len(result[key])}):")
            for l in result[key]:
                lines.append(f"  - #{l['number']}: {l['title']}")
    
    if result["nag"]:
        lines.append(f"**Needs triage** ({len(result['nag'])} logs, {NAG_DAYS}+ days old):")
        for l in result["nag"]:
            lines.append(f"  - #{l['number']}: {l['title']} ({l['age_days']}d old)")
    
    if result["unreacted_recent"]:
        lines.append(f"**Recent, no reaction yet** ({len(result['unreacted_recent'])}):")
        for l in result["unreacted_recent"]:
            lines.append(f"  - #{l['number']}: {l['title']} ({l['age_days']}d)")
    
    if not any(result.values()):
        lines.append("All flight logs reviewed. Clean perch.")
    
    return "\n".join(lines)
