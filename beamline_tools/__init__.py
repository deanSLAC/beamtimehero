"""BTH extension layer on top of `beamtimehero_cli`.

Owns the station selection (`station`, `stations/`), the env-var defaults
applied before upstream config is imported (`config`) and each station's
BTH agent profile (`stations/<name>.PROFILE`). The CLI wrapper
in `cli.py` registers the profile with upstream and composes upstream's
parser helpers so `beamtimehero bth <leaf>` resolves through the
canonical tool catalog.
"""
