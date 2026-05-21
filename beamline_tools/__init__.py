"""BTH extension layer on top of `beamtimehero_cli`.

Owns the agent-role allowlist (`agent_roles`) and the env-var defaults
applied before upstream config is imported (`config`). The CLI wrapper
in `scripts/beamtimehero` composes these with upstream helpers to build
the `beamtimehero bth` branch.
"""
