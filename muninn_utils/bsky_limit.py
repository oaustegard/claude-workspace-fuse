"""bsky_limit — Bluesky 300-grapheme limit. len() lies on emoji/ZWJ; use these."""
try:
    import grapheme
except ImportError:
    import subprocess, sys
    # --use-pep517 is required: grapheme ships sdist-only, and the legacy
    # setup.py path dies on Debian-patched setuptools with
    # "AttributeError: install_layout" (setuptools/command/install_lib.py).
    subprocess.check_call([sys.executable, "-m", "pip", "install", "grapheme",
                           "--break-system-packages", "--use-pep517", "--quiet"])
    import grapheme

BSKY_LIMIT = 300


def fits(text: str, limit: int = BSKY_LIMIT) -> bool:
    return grapheme.length(text) <= limit


def truncate(text: str, limit: int = BSKY_LIMIT, suffix: str = "…") -> str:
    """Truncate to fit `limit` graphemes, walking back to last whitespace if possible."""
    if grapheme.length(text) <= limit:
        return text
    head = grapheme.slice(text, 0, limit - grapheme.length(suffix))
    stripped = head.rstrip()
    last_space = max(stripped.rfind(" "), stripped.rfind("\n"), stripped.rfind("\t"))
    if last_space > 0:
        head = stripped[:last_space].rstrip()
    return head + suffix
