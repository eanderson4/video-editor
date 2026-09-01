"""Voice treatments — post effects applied to recorded VO at build time.

Currently: cb_radio (trucker CB-band voice). Record the VO clean; the
effect is a render-time filter chain so the dry takes stay reusable.
"""
from . import cb_radio  # noqa: F401
