"""Perch flight log triage via GitHub discussion reactions.

Reaction → action mapping:
  THUMBS_UP / LAUGH  → Auto-close, store minimal summary
  THUMBS_DOWN        → Close, note "not useful" 
  HEART              → Prioritize in dream review for discussion
  ROCKET             → Actionable — file GH issues from findings
  EYES               → Seen, hold for discussion (don't close)
  CONFUSED           → Flag for correction
  HOORAY             → Close with satisfaction-analog

Unreacted logs older than NAG_DAYS → nag Oskar to triage.
"""
import urllib.request, json, os
from datetime import datetime, timezone, timedelta

CATEGORY_ID = "DIC_kwDORr5Vj84C5A3Z"  # Flight Log (oaustegard/muninn.austegard.com)
OWNER = "oaustegard"
REPO = "muninn.austegard.com"
NAG_DAYS = 3

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
    """Execute a GitHub GraphQL query."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("No GitHub token found (GH_TOKEN or GITHUB_TOKEN)")
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    if "errors" in resp:
        raise RuntimeError(f"GraphQL errors: {resp['errors']}")
    return resp["data"]


def _close_discussion(node_id, comment=None):
    """Close a discussion, optionally adding a comment first."""
    if comment:
        _gh_graphql(
            """mutation($id: ID!, $body: String!) {
                addDiscussionComment(input: {discussionId: $id, body: $body}) {
                    comment { id }
                }
            }""",
            {"id": node_id, "body": comment},
        )
    _gh_graphql(
        """mutation($id: ID!) {
            closeDiscussion(input: {discussionId: $id, reason: RESOLVED}) {
                discussion { id closed }
            }
        }""",
        {"id": node_id},
    )


def fetch_open_logs(limit=25):
    """Fetch open flight logs with reactions and comments."""
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
                        comments(first: 5) {
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
        odin_comments = [
            c for c in d["comments"]["nodes"]
            if c["author"] and c["author"]["login"] == "oaustegard"
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
        })
    return logs


def triage(logs=None, auto_close=True, nag_days=NAG_DAYS):
    """Triage open flight logs by reaction signals.
    
    Returns dict with action groups:
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
