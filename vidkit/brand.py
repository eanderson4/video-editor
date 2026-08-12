"""Brand/design systems — single source of truth for promo/video tokens.

Protocol (mirrors design-page-bot): a system is a directory under
`systems/` containing at minimum `brand.json`. Optional: `assets/` (shared
art textures), `fonts/` (system font files, referenced from brand.json).
Adding a system requires zero code changes — drop the directory in and it
is registered. `list_systems()` enumerates, `load_system(name)` reads one.

The active system is chosen by the VIDKIT_SYSTEM env var, defaulting to
"math-vs-vibes". Tokens are exposed three ways:

- structured: `PALETTE` / `WORDMARK` dicts, `SHEET_W/H`, `ASSETS`
- legacy module constants: `brand.MATH_BLUE`, `brand.MATH_BOX`, ... resolve
  dynamically from the active system's tokens (module __getattr__), so
  existing usage scripts keep working unchanged

Fonts are universal, not per-system: VIDKIT_FONT_HEAVY / VIDKIT_FONT_BOLD
env overrides, then a "fonts" entry in brand.json (paths relative to the
system dir), then macOS Arial, then Linux Liberation Sans (metric-compatible
Arial clone; no Black weight, Bold covers both heavy and bold roles).
"""
import json
import os

REPO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir))
SYSTEMS_DIR = os.path.join(REPO, "systems")

_MAC_ARIAL_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
_MAC_ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_LINUX_LIBERATION_BOLD = \
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def list_systems():
    if not os.path.isdir(SYSTEMS_DIR):
        return []
    return sorted(d for d in os.listdir(SYSTEMS_DIR)
                  if os.path.isfile(os.path.join(SYSTEMS_DIR, d, "brand.json")))


def load_system(name):
    path = os.path.join(SYSTEMS_DIR, name)
    manifest = os.path.join(path, "brand.json")
    if not os.path.isfile(manifest):
        available = ", ".join(list_systems()) or "(none)"
        raise RuntimeError("unknown brand system '%s' — no %s\n"
                           "available systems: %s" % (name, manifest, available))
    with open(manifest) as f:
        spec = json.load(f)
    spec["_path"] = path
    return spec


SYSTEM_NAME = os.environ.get("VIDKIT_SYSTEM", "math-vs-vibes")
_sys = load_system(SYSTEM_NAME)

# structured tokens
PALETTE = {k: tuple(v) for k, v in _sys["palette"].items()}
WORDMARK = {k: tuple(v) for k, v in _sys.get("wordmark", {}).items()}
_sheet = _sys.get("sheet", {})
SHEET_W, SHEET_H = _sheet.get("w", 3840), _sheet.get("h", 2160)

# shared art shipped with the system (hero/intro textures). VIDKIT_ASSETS
# overrides the directory.
ASSETS = os.environ.get("VIDKIT_ASSETS") or os.path.join(_sys["_path"], "assets")


def _resolve_font(env, role):
    if os.environ.get(env):
        return os.environ[env]
    candidates = [
        os.path.join(_sys["_path"], p)
        for p in _sys.get("fonts", {}).get(role, [])
    ]
    if role == "heavy":
        candidates += [_MAC_ARIAL_BLACK, _LINUX_LIBERATION_BOLD]
    else:
        candidates += [_MAC_ARIAL_BOLD, _LINUX_LIBERATION_BOLD]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise RuntimeError("brand font missing for role '%s': tried %s (or set %s)"
                       % (role, candidates, env))


FONT_HEAVY = _resolve_font("VIDKIT_FONT_HEAVY", "heavy")
FONT_BOLD = _resolve_font("VIDKIT_FONT_BOLD", "bold")


def __getattr__(name):
    """Legacy module constants (brand.MATH_BLUE, brand.MATH_BOX, ...) resolve
    from the active system's palette/wordmark tokens."""
    if name in PALETTE:
        return PALETTE[name]
    if name in WORDMARK:
        return WORDMARK[name]
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


if __name__ == "__main__":
    print("\n".join(list_systems()))
