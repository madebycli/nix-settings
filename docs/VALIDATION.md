# Validation

## Executed in the implementation workspace

```text
python -m compileall -q src
PYTHONPATH=src pytest -q
```

Result: 29 tests passed.

Coverage includes default Overview routing, direct Sound routing, six monitor/workarea cases, fixed header geometry, status/update/generation/cleanup parsers, exact update-mode mapping, Config Sync models, path and secret checks, ANSI/log redaction, stale request rejection, helper allowlist, fixed argv construction, desktop entry and GTK4/non-hermetic path guards.

No test performs a real update, generation deletion, system switch, rollback, optimization or Git push.

## Not available in the API execution environment

The environment did not provide `ruff`, `mypy` or `nix`, so these commands were not claimed as executed locally:

```text
ruff check .
mypy src
nix flake check --no-write-lock-file --print-build-logs
nix build .#nix-settings
```

GitHub Actions is expected to run the repository's normal checks after the draft pull request is opened.

## Required before merge

Validate on an actual target NixOS desktop:

1. Overview opens without a visible resize.
2. Every view keeps identical outer geometry and internal scrolling.
3. `nix-settings sound` preserves all existing Sound behavior and visual geometry.
4. GTK foreground/accent colors match the active theme without white or grey fallback surfaces.
5. Online status and update preview do not mutate the real lock file/profile.
6. The desktop Polkit agent authenticates refresh, switch, cleanup, optimize and rollback.
7. No terminal sudo/password prompt appears.
8. Cancellation and failure restore controls and terminate process groups.
9. Cleanup blocks unsafe generation/boot states and only deletes the confirmed dry-run set.
10. `nix profile add github:madebycli/nix-settings#nix-settings` installs successfully.

Do not merge solely from static/API validation; real Wayland, Polkit and NixOS-system behavior remains a release gate.
