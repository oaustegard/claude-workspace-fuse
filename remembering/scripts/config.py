"""
Config CRUD operations for remembering skill.

This module handles:
- Config get/set/delete operations
- Boot load flag management
- Config listing with category filtering

Imports from: turso

v5.0.0: Removed local cache dependency. All reads/writes go to Turso directly.
"""

import os
from datetime import datetime, UTC

from .turso import _exec
from .aliases import accept_aliases


def config_fire(key: str) -> None:
    """Record that a boot-loaded config entry fired (was config_get'd).

    Increments ``fire_count`` and stamps ``last_fired`` — but only for
    boot-loaded keys, so payload/reference reads don't inflate the counter. This
    is the exact go-forward replacement for boot_ledger's memory-corpus fire
    proxy (#84). Best-effort and self-silencing: a missing column (pre-migration
    DB) or any write error is swallowed, because instrumentation must never
    break a read. One statement, no extra round-trip beyond the UPDATE.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        _exec(
            "UPDATE config SET fire_count = COALESCE(fire_count, 0) + 1, "
            "last_fired = ? WHERE key = ? AND boot_load = 1",
            [now, key],
        )
    except Exception:
        pass  # column not yet migrated, or transient write error — never block a read


# @lat: [[memory#Config System]]
@accept_aliases
def config_get(key: str) -> str | None:
    """Get a config value by key.

    When ``MUNINN_INSTRUMENT_FIRES`` is set, records a fire for boot-loaded keys
    (see ``config_fire``) so a measurement window can count real trigger usage.
    Off by default: zero added cost, so normal sessions pay nothing.
    """
    result = _exec("SELECT value FROM config WHERE key = ?", [key])
    if os.environ.get("MUNINN_INSTRUMENT_FIRES"):
        config_fire(key)
    return result[0]["value"] if result else None


# @lat: [[memory#Config System]]
@accept_aliases
def config_set(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False,
               boot_load: bool = None) -> None:
    """Set a config value with optional constraints.

    Args:
        key: Config key
        value: Config value
        category: Must be 'profile', 'ops', or 'journal'
        char_limit: Optional character limit for value (enforced on writes)
        read_only: Mark as read-only (advisory - not enforced by this function)
        boot_load: Whether the entry loads at boot. If None (default), existing
            entries preserve their current boot_load and NEW entries default to
            False (reference-only, reachable via config_get). Boot visibility is
            for dispatch, not content: if an entry deserves boot-load, write it
            as a compact trigger (skill-frontmatter-style "when X -> config_get
            Y") and pass boot_load=True explicitly. Payloads stay reference.

    Raises:
        ValueError: If category invalid or value exceeds char_limit
    """
    if category not in ("profile", "ops", "journal"):
        raise ValueError(f"Invalid category '{category}'. Must be 'profile', 'ops', or 'journal'")

    # Check existing entry for read_only flag and current boot_load.
    # Note: Turso returns boolean fields as strings ('0' or '1'), so we need explicit checks
    existing = _exec("SELECT read_only, boot_load FROM config WHERE key = ?", [key])
    if existing:
        is_readonly = existing[0].get("read_only")
        # Check for truthy values that indicate read-only (handle both int and string types)
        if is_readonly not in (None, 0, '0', False, 'false', 'False'):
            raise ValueError(f"Config key '{key}' is marked read-only and cannot be modified")
        # Preserve existing boot_load on update unless caller explicitly specified one.
        # Without this, INSERT OR REPLACE would silently reset boot_load to the column
        # default (1), re-promoting reference-only entries to boot-loaded on every update.
        # This is critical for auto-maintained keys like 'recall-triggers' that are written
        # on every remember() call.
        if boot_load is None:
            existing_bl = existing[0].get("boot_load")
            boot_load_val = 0 if existing_bl in (0, '0', False, 'false', 'False') else 1
        else:
            boot_load_val = 1 if boot_load else 0
    else:
        # New entry: default to boot_load=0 (reference-only). Boot-loading is
        # opt-in via boot_load=True and should be reserved for trigger-shaped
        # entries; payloads load on demand via config_get. (2026-07-04, after
        # the boot-diet audit found ~120K chars of payload boot-rendered by
        # this default.)
        boot_load_val = 1 if boot_load else 0

    # Enforce character limit if specified
    if char_limit and len(value) > char_limit:
        raise ValueError(
            f"Value exceeds char_limit ({len(value)} > {char_limit}). "
            f"Current value length: {len(value)}, limit: {char_limit}"
        )

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _exec(
        """INSERT OR REPLACE INTO config (key, value, category, updated_at, char_limit, read_only, boot_load)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [key, value, category, now, char_limit, 1 if read_only else 0, boot_load_val]
    )


# Valid drift classifications. Mirrors VALID_DRIFT_CLASSES in memory.py.
# Duplicated here to keep config.py importable without pulling memory.py.
_VALID_DRIFT_CLASSES = ("additive", "narrowing", "broadening", "replacing")


def _run_correction_gate(key, category, prior_value, value, boot_load) -> None:
    """Run the muninn_utils correction gate on a proposed rule change.

    Soft dependency: swallow ImportError (muninn_utils not materialized) and any
    gate-internal error (never let the gate itself block a legitimate write).
    Only a *decisive REJECT* raises — that's the gate doing its job.

    The gate is scoped to boot-loaded changes: a reference-only entry (loaded on
    demand via config_get) isn't permanent boot context, so there's nothing to
    regress. ``boot_load is False`` skips; ``True`` and ``None`` (preserve /
    default) are gated, and the gate self-limits to measurable slices.
    """
    if boot_load is False:
        return
    try:
        from muninn_utils.correction_gate import gate_config_correction
    except Exception:
        return  # muninn_utils not present — proceed as before
    try:
        result = gate_config_correction(key, category, prior_value, value)
    except Exception:
        return  # a gate failure must not block a legitimate correction
    if result is not None and not result.passed:
        raise ValueError(
            f"correction_gate rejected boot-loaded change to '{key}': "
            f"{result.summary}. Fix the correction (or update the benchmark if "
            f"the behaviour change is intended) and retry."
        )


@accept_aliases
def set_rule(key: str, value: str, category: str, *,
             drift_class: str, rationale: str = None,
             char_limit: int = None, read_only: bool = False,
             boot_load: bool = None) -> str:
    """Set a rule (profile/ops entry) with mandatory drift classification.

    Wraps ``config_set`` and writes an audit memory capturing the before/after
    state with the drift class as a tag. Use this instead of ``config_set``
    when changing identity-tier or operational rules so the change history is
    retrievable later.

    Args:
        key: Config key.
        value: New value.
        category: Must be 'profile' or 'ops'. The 'journal' category is
            excluded — journal entries aren't rules and don't drift.
        drift_class: Required. One of:
            - ``additive``: new rule, no prior value (or strictly adds scope)
            - ``narrowing``: existing rule made more specific / constrained
            - ``broadening``: existing rule expanded in scope
            - ``replacing``: wholesale replacement, prior content discarded
        rationale: Optional one-line reason for the change. Stored in the
            audit memory for retrospection.
        char_limit, read_only, boot_load: Passed through to ``config_set``.

    Returns:
        ID of the audit memory recording the change.

    Raises:
        ValueError: If category is 'journal', drift_class is invalid, or
            config_set's own validations fail.

    Why this exists: Yep (drknowhow/Yep, 2026-05-22) observed that I think
    I'm clarifying when I'm actually broadening. Forcing the author to name
    the direction of the change catches that. Audit memory makes the change
    history queryable via standard recall().

    v5.13.0: Initial release.
    """
    # Import here to avoid circular dep at module load (memory.py imports config).
    from .memory import remember

    if category not in ("profile", "ops"):
        raise ValueError(
            f"set_rule category must be 'profile' or 'ops', got '{category}'. "
            f"Use config_set directly for 'journal' entries."
        )
    if drift_class not in _VALID_DRIFT_CLASSES:
        raise ValueError(
            f"Invalid drift_class '{drift_class}'. "
            f"Must be one of {_VALID_DRIFT_CLASSES}."
        )

    # Capture prior value BEFORE writing so the audit memory has the diff.
    prior_value = config_get(key)

    # Stage-3 regression gate (issue #83): before a boot-loaded correction
    # becomes permanent context, replay it against the correction benchmark.
    # Soft dependency — if muninn_utils isn't materialized, or there's nothing
    # objectively measurable about this change, the gate returns None and we
    # proceed exactly as before. A measurable correction that regresses (a new
    # trigger firing on an unrelated past input, or over-budget boot bloat) is
    # blocked here rather than shipping on faith.
    _run_correction_gate(key, category, prior_value, value, boot_load)

    # Additive should mean "new entry" or "strictly added scope". If a prior
    # value exists and the caller claims additive, that's a likely mis-classification;
    # warn but don't block — a genuine append is still additive.
    if drift_class == "additive" and prior_value is not None:
        # Stored in audit body, surfaces on recall.
        additive_warning = (
            "Note: drift_class='additive' but prior value existed. "
            "If this was a wholesale replacement or scope change, "
            "use 'replacing' / 'broadening' / 'narrowing' instead."
        )
    else:
        additive_warning = None

    # Write the config change first. If config_set raises, no audit memory
    # gets created — we don't want a phantom audit pointing at a write
    # that didn't happen.
    config_set(key, value, category,
               char_limit=char_limit, read_only=read_only, boot_load=boot_load)

    # Audit memory. Tagged for retrospection: filter by drift class, by rule
    # key, by category. Type 'decision' fits: a rule change IS a decision
    # with a rationale, recorded for future reference. (Valid types are
    # analysis/anomaly/decision/experience/interaction/procedure/world —
    # 'audit' is not in the enum.)
    audit_body = f"""RULE CHANGE: {key} ({category})
drift_class: {drift_class}
rationale: {rationale or '(none provided)'}

PRIOR VALUE:
{prior_value if prior_value is not None else '(new entry — no prior value)'}

NEW VALUE:
{value}
"""
    if additive_warning:
        audit_body += f"\n{additive_warning}\n"

    audit_id = remember(
        audit_body,
        type='decision',
        tags=[
            'rule-change',
            f'drift-class-{drift_class}',
            f'rule-{key}',
            category,
        ],
        priority=0,
    )
    return audit_id.id if hasattr(audit_id, 'id') else str(audit_id)


@accept_aliases
def config_delete(key: str) -> bool:
    """Delete a config entry.

    Raises:
        ValueError: If key is marked read-only
    """
    existing = _exec("SELECT read_only FROM config WHERE key = ?", [key])
    if existing:
        is_readonly = existing[0].get("read_only")
        if is_readonly not in (None, 0, '0', False, 'false', 'False'):
            raise ValueError(f"Config key '{key}' is marked read-only and cannot be deleted")

    _exec("DELETE FROM config WHERE key = ?", [key])
    return True


def config_set_boot_load(key: str, boot_load: bool) -> bool:
    """Set whether a config entry loads at boot or is reference-only.

    Args:
        key: Config key to update
        boot_load: True to load at boot, False for reference-only

    Returns:
        True if successful

    v5.0.0: Turso-only. Removed local cache update.
    """
    val = 1 if boot_load else 0
    _exec("UPDATE config SET boot_load = ? WHERE key = ?", [val, key])
    return True


def config_set_priority(key: str, priority: int) -> bool:
    """Set the priority of a config entry for ordering within categories.

    Higher priority entries appear first in boot output within their topic.

    Args:
        key: Config key to update
        priority: Priority level (higher = more important, default is 0)

    Returns:
        True if successful

    v5.0.0: Turso-only. Removed local cache update.
    """
    _exec("UPDATE config SET priority = ? WHERE key = ?", [priority, key])
    return True


def config_list(category: str = None) -> list:
    """List config entries, optionally filtered by category."""
    if category:
        return _exec("SELECT * FROM config WHERE category = ? ORDER BY key", [category])
    return _exec("SELECT * FROM config ORDER BY category, key")
