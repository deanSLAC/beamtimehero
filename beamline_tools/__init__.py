"""BTH extension layer on top of `beamtimehero_cli`.

Owns the env-var defaults applied before upstream config is imported
(`config`) and the BTH agent profile (`bth_profile`). The CLI wrapper
in `cli.py` registers the profile with upstream and composes upstream's
parser helpers so `beamtimehero bth <leaf>` resolves through the
canonical tool catalog.
"""
