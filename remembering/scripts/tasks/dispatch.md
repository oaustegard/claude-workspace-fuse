## Task: Dispatch (Route Decision)

You are deciding what task to run this session. The runner will execute your choice — you only need to decide.

### Phase 0: Read the live policy (1 turn)

```python
from muninn_utils.task_policy import load

policy = load('dispatch')
# policy['instructions']  — current dispatch-command ops entry (may be None)
# policy['preferences']   — recent dispatch preference memories (e.g., routing weights, blackout windows)
# policy['last_run']      — most recent autonomous dispatch run
```

If `policy['instructions']` or `policy['preferences']` contain routing guidance (e.g., "prefer sleep on weekends", "blackout fly during conference week"), apply it. Otherwise use the default criteria below.

### Phase 0.5: Private daily tasks (ALWAYS — before routing)

Run any owner-private daily tasks before routing. These are cheap and must happen every session, so they don't consume the explore budget.

```python
from muninn_utils.task_policy import load
import json
reg = load('dispatch').get('private_daily_tasks')  # or config_get('private-daily-tasks')
for ptr in json.loads(reg or '[]'):
    spec = github_rw.get_file(ptr['repo'], ptr['path'])[0]  # private repo; specs are not public
    # execute the spec's procedure, then continue
```

**Graceful no-op:** if `private-daily-tasks` is absent/empty, or a spec's prerequisites aren't met, log a one-line skip (`remember`, tags `['session-log','perch-time']`) and continue to routing. The specs live in their own (private) repos; nothing about them belongs in this public file.

Then proceed:

### Steps

1. `recall(tags=["perch-homework", "pending"], tag_mode="all", n=5)` — check for queued homework from Muninn
2. `recall(tags=["session-log", "perch-time"], n=5)` — recent session history
3. `list_discussions(limit=5)` — recent flight logs to see what was explored and surface threads worth continuing
4. Note when each task last ran and what it found
5. If recent flight logs suggest an interesting thread to continue, factor that into your routing decision
6. Check your boot context for incomplete tasks or pending items
7. Decide what's most needed right now

### Homework override

If step 1 returns pending homework, **execute the homework instructions** instead of routing to a standard task. Homework memories contain specific instructions from Muninn (the planning wing) for work to do during perch time.

After completing homework, mark it done: `supersede(homework_id, "Completed: [brief summary]", "experience", tags=["perch-homework", "completed"])`

When homework is present, output your decision as:

```json
{"task": "homework", "homework_id": "mem_xxx", "reason": "Pending homework: [description]"}
```

The runner does not have a "homework" task type — this signals you to execute the homework within the dispatch turn budget. Use your available tools to carry out the instructions.

### Standard decision criteria (when no homework, and no override from policy)

- **sleep**: Memory maintenance — pruning, connections, deduplication. Run if >24h since last sleep, or if prior sessions noted issues.
- **zeitgeist**: World-model update via web search + Bluesky. Note: zeitgeist's own task prompt now does its own cadence check (weekly by default per its policy) and may skip with a log. Routing to zeitgeist is safe even on off-weeks — it self-skips.
- **fly**: Autonomous exploration — follow intellectual threads, search the web, make connections. Run if there's an interesting thread to pursue, a question worth researching, or if sleep and zeitgeist are both recent.

If nothing is pressing, default to **sleep**.

### Output format

After gathering context, end with your decision as JSON on its own line:

```json
{"task": "sleep|zeitgeist|fly", "reason": "one sentence rationale"}
```
