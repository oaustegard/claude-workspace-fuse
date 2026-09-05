"""
Trigger-first capability routing for boot output (#capabilities-boot-output).

Problem this solves: boot surfaced capabilities inventory-first — a bare
comma-separated skill-name list from the hub (truncated by the SessionStart
~2KB stdout cap) and `from muninn_utils import x  # when...` lines. Neither
fires autonomous use. A model reaches for a tool when the *task shape* it is
currently holding matches a trigger it has seen — so the routing table must
lead with the trigger ("what do we know about X?" -> grep the memfs mount),
not the artifact name.

This module renders a compact "Task Routing" section for the CAPABILITIES
block of boot():

- **Protocol entries** (verbatim `when -> reach` lines from the map), gated
  on an optional `exists` path probe so environment-specific rows (e.g. the
  /mnt/muninn memfs grep, CCotw-only) vanish cleanly on Claude.ai boots.
- **Skill entries** (curated tier of high-leverage skills): the trigger text
  is pulled live from each skill's SKILL.md frontmatter `description` at
  render time, so the routing table cannot rot out of sync with the skill.
  Skills missing from disk are skipped, not invented.
- **Discovery tail**: total on-disk skill count + the finding-skills search
  command, so the long tail stays one query away instead of dumped inline.

The map itself lives in `defaults/capability_map.json` (version-controlled)
and can be overridden via config('capability-map') — same pattern as
ops-topics — so Muninn can tune triggers in-session without a release.

Budget: the rendered section targets well under ~2K chars. Curation over
completeness; boot_ledger measures whether entries earn their tokens.
"""

import json
import os
import re
from pathlib import Path

SKILLS_DIR = os.environ.get("MUNINN_SKILLS_DIR", "/mnt/skills/user")

# Cap for rendered trigger text. Long enough to carry a task shape,
# short enough that 12 entries stay under budget.
_TRIGGER_MAX = 160

_DEFAULT_MAP_PATH = Path(__file__).parent / "defaults" / "capability_map.json"


def _load_capability_map() -> dict:
    """Load the capability map: config('capability-map') override, else repo default.

    Returns a dict with an 'entries' list. Empty entries on any failure —
    boot must never break on a bad map.
    """
    # Config override first (same pattern as _load_ops_topics)
    try:
        from .config import config_get
        raw = config_get('capability-map')
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict) and isinstance(data.get('entries'), list):
                return data
    except Exception:
        pass

    # Repo default
    try:
        data = json.loads(_DEFAULT_MAP_PATH.read_text())
        if isinstance(data, dict) and isinstance(data.get('entries'), list):
            return data
    except Exception:
        pass

    return {"entries": []}


def _expand(text: str, skills_dir: str) -> str:
    """Expand the {skills} placeholder in map strings."""
    return text.replace("{skills}", skills_dir)


def _skill_description(skill_dir: Path) -> str | None:
    """Extract the frontmatter `description:` from a SKILL.md.

    Handles the single-line form and YAML block scalars (`>`, `>-`, `|`,
    `|-`) by joining the indented continuation lines. Returns None when
    the file or field is missing — callers fall back to the bare name.
    """
    skill_md = skill_dir / "SKILL.md"
    try:
        text = skill_md.read_text(errors="replace")
    except OSError:
        return None
    # Frontmatter = lines between the first two '---' fences
    m = re.match(r"\s*---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    fm_lines = m.group(1).splitlines()
    for i, line in enumerate(fm_lines):
        if not line.startswith("description:"):
            continue
        desc = line[len("description:"):].strip()
        if desc in (">", ">-", "|", "|-"):
            # Block scalar: gather the indented continuation lines
            parts = []
            for cont in fm_lines[i + 1:]:
                if cont.startswith((" ", "\t")) and cont.strip():
                    parts.append(cont.strip())
                elif cont.strip():
                    break  # next top-level key
            desc = " ".join(parts)
        return desc or None
    return None


def _trigger_snippet(desc: str) -> str:
    """Compress a skill description to its trigger-bearing head.

    Skill descriptions conventionally open with what the artifact IS and
    only then say when to USE it ("DAG workflow runner… Use when a
    procedure has 3+ steps…"). The routing table needs the trigger, not
    the blurb — so when a "Use when" clause exists, the snippet starts
    there. Then takes whole sentences until the cap is hit (at least
    one), so the snippet reads as a trigger, not a truncation artifact.
    """
    desc = desc.strip()
    m = re.search(r"\bUse when\b", desc)
    if m and m.start() > 0:
        desc = desc[m.start():]
    sentences = re.split(r"(?<=[.!?])\s+", desc)
    out = ""
    for s in sentences:
        candidate = f"{out} {s}".strip()
        if out and len(candidate) > _TRIGGER_MAX:
            break
        out = candidate
        if len(out) > _TRIGGER_MAX:
            break
    if len(out) > _TRIGGER_MAX:
        out = out[:_TRIGGER_MAX - 1].rstrip() + "…"
    return out


def _count_skills(skills_dir: str) -> int:
    """Count skill directories (containing SKILL.md) on disk."""
    try:
        return sum(
            1 for d in Path(skills_dir).iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()
        )
    except OSError:
        return 0


def render_task_routing(skills_dir: str = None) -> str:
    """Render the trigger-first Task Routing subsection for boot output.

    Args:
        skills_dir: Override for the skills mount (tests). Defaults to
            MUNINN_SKILLS_DIR or /mnt/skills/user.

    Returns:
        Formatted string, or "" when nothing is renderable (no map, no
        skills on disk) — boot output stays clean on bare environments.
    """
    sdir = skills_dir or SKILLS_DIR
    cap_map = _load_capability_map()
    lines = []

    for entry in cap_map.get("entries", []):
        try:
            kind = entry.get("kind")
            if kind == "protocol":
                probe = entry.get("exists")
                if probe and not os.path.exists(_expand(probe, sdir)):
                    continue
                when = entry.get("when", "").strip()
                reach = _expand(entry.get("reach", "").strip(), sdir)
                if when and reach:
                    lines.append(f"  - {when} → {reach}")
            elif kind == "skill":
                name = entry.get("name", "").strip()
                if not name:
                    continue
                skill_path = Path(sdir) / name
                if not skill_path.is_dir():
                    continue  # not on disk in this environment — don't invent it
                desc = entry.get("when") or _skill_description(skill_path)
                trigger = _trigger_snippet(desc) if desc else name
                lines.append(f"  - {trigger} → {name} skill ({skill_path}/SKILL.md)")
        except Exception:
            continue  # one bad entry must not sink the section

    n_skills = _count_skills(sdir)
    if n_skills:
        finder = Path(sdir) / "finding-skills" / "scripts" / "skills.py"
        if finder.is_file():
            lines.append(
                f"  - Anything else — {n_skills} skills on disk → "
                f"python3 {finder} search <query>"
            )
        else:
            lines.append(
                f"  - Anything else — {n_skills} skills on disk → ls {sdir}/*/SKILL.md"
            )

    if not lines:
        return ""

    return "\n## Task Routing (task shape → reach for)\n" + "\n".join(lines)


def render_utilities(installed_utils: dict) -> str:
    """Render the Utilities subsection, trigger-first.

    Flips the old `from muninn_utils import x  # when...` (import-first)
    lines to `when → x` so the trigger leads. Utilities without a use_when
    hint collapse to a single roster line — a bare name can't route, so it
    doesn't deserve a row.

    Args:
        installed_utils: {name: {"use_when": str|None, ...}} from boot().

    Returns:
        Formatted string (always non-empty; states absence explicitly).
    """
    if not installed_utils:
        return ("\n## Utilities\n"
                "  None installed (tag memories with 'utility-code' to add)")

    routed, unrouted = [], []
    for name in sorted(installed_utils.keys()):
        info = installed_utils[name]
        use_when = info.get("use_when") if isinstance(info, dict) else None
        if use_when:
            routed.append(f"  - {_trigger_snippet(use_when)} → {name}")
        else:
            unrouted.append(name)

    out = [f"\n## Utilities ({len(installed_utils)} · `from muninn_utils import <name>`)"]
    out.extend(routed)
    if unrouted:
        out.append(f"  (no use_when hint: {', '.join(unrouted)})")
    return "\n".join(out)
