"""BeamtimeHero tool metadata — descriptions consumed by the frontend
sidebar. The agent invokes tools via Bash against `./scripts/beamtimehero
bth …`; no in-process dispatch happens here.
"""

from .definitions import TOOL_DESCRIPTIONS

__all__ = ["TOOL_DESCRIPTIONS"]
