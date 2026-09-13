# Getting Started: building a persistent-memory loop

> Audience: an engineer building their own persistent agent. Code marked
> "Muninn-specific" is local wiring. The pattern transfers. The exact names may not.

This walks through the core that everything else in muninn-utilities assumes: a
loop where the agent stores what it learns, recalls it later, and revises it
without losing the history. Work through it and you have a usable mental model of
how the agent remembers.

## Connecting to a memory store over HTTP

The memory store lives outside the agent process. Muninn runs in containers wiped
between sessions, so anything held in local files or process memory is gone by the
next boot. A remote database survives that. The agent reaches the store the way a
web server reaches its database, connecting over the network to read and write.
Nothing it needs to remember lives in the agent itself.

Two environment variables point the library at the store. `TURSO_URL` names the
database host, and `TURSO_TOKEN` authenticates the connection. The library reads
both at import time, so set them before the first call. These names are Muninn's.
In your own agent they can carry any names your connection layer expects.

```bash
export TURSO_URL="your-db.turso.io"
export TURSO_TOKEN="..."        # auth token with read/write
```

```python
from scripts import recall

recent = recall(n=5)            # empty list-like result on a fresh store
print(recent)
```

The first recall confirms the connection. On a fresh store it returns an empty
result rather than an error, which tells you the credentials and host resolved. If
the call raises instead, the problem is the connection rather than your code. Check
the two variables before going further.

## Storing your first memory

Every memory carries a required type. The type sorts what kind of thing the memory
is, drawn from a small fixed set: a procedure, a decision, an observation about the
world, an analysis, something that happened. Recall can filter on it later, so the
type is the coarsest handle you have on a growing store. Choosing it at write time
costs nothing and saves a scan later.

```python
from scripts import remember

mem_id = remember(
    "The deploy step waits for HTTP 200 before updating the feed.",
    type="procedure",           # required; one of a small fixed set
    tags=["deploy", "feed"],
    priority=1,                  # higher surfaces earlier in later recalls
)
print(mem_id)                   # -> a UUID string
```

Tags and priority shape how a memory surfaces later. Tags are free-form labels for
retrieval by topic, and priority orders results when many match. Neither is
required, and you can use a tag you have never used before without declaring it
anywhere. The call returns the new memory's id, which you keep when you plan to
revise or link the memory later.

## Recalling memories by text and tag

Full-text search matches against the text of stored memories. Pass a query and the
store ranks memories by relevance to those words, the way a search box does. This
is the path you reach for when you remember roughly what a memory said but not how
you tagged it. It searches the body, not the tags.

Tag filters narrow recall by label instead of content. Passing tags returns
memories carrying those labels, and `tag_mode` decides whether a memory needs every
tag or any one of them. Tags give you precision full-text search can't. They return
an exact slice of the store regardless of wording. Combine a query with tags when
you want both at once.

```python
from scripts import recall

# Full-text search over memory bodies.
hits = recall(query="deploy feed", n=5)

# Tag filter; tag_mode="any" matches one or more, "all" requires every tag.
tagged = recall(tags=["deploy"], tag_mode="any", n=5)

for m in hits:
    print(m["id"], m["type"], m["summary"][:60])
```

Recall returns an iterable result set rather than raw rows. Each item exposes the
memory's id, type, tags, and body, so you can loop over results and read fields
directly. The result behaves like a list, so slicing and `len` work as expected.
You shape the query going in. You read structured memories coming out.

## Revising a memory without deleting it

A correction creates a new memory linked to the old one. Instead of editing the
original in place, `supersede` writes a fresh memory and records that it replaces
its predecessor. The new version is what recall returns from then on. The old one
steps out of the way without disappearing.

The superseded memory survives the revision. Every correction leaves the prior
version in the store, building a chain of how a fact changed over time. For an
agent reasoning about its own past, that history is data rather than clutter. It
can tell what it used to believe and when that changed. Editing in place would
erase the record that makes the change legible.

```python
from scripts import supersede, recall, forget

new_id = supersede(
    mem_id,
    "The deploy step polls for HTTP 200, then updates the Atom feed.",
    type="procedure",
    tags=["deploy", "feed"],
)
```

Forget removes a memory from recall without replacing it. Use it when something
should stop surfacing and no correction takes its place, like a reminder that has
been handled. The delete is soft, so a forgotten memory can be recovered rather
than destroyed. Supersede is for what changed. Forget is for what is done.

```python
# Forget has no replacement: the memory stops surfacing.
handled = recall(tags=["reminder", "done"], n=1)
if handled:
    forget(handled[0]["id"])
```

## Following a memory's history

`get_chain` walks the supersession links for a memory. Give it any id in the chain
and it follows the replaces-pointers back through every prior version, returning
them in order. One call reconstructs the full arc of a fact, from its first form to
its current one.

```python
from scripts import get_chain

chain = get_chain(new_id)       # walks back through the supersede links
for m in chain:
    print(m["created_at"], m["summary"][:60])
```

The trail gives the agent provenance over its own knowledge. It can answer not only
what it believes but how that belief got there, which is the difference between a
memory store and a cache. A cache holds the latest value. This store holds the
reasoning.
