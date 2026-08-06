# Validation record

Validation performed while preparing the GTK3 layer-shell repair:

- changed Python files compile with `python -m compileall -q`;
- focused CLI and volume-format tests pass: 5 tests;
- the implementation was checked against the working GTK3 layer-shell patterns in `madebycli/git-backup` and `madebycli/GIF-Player`.

The following must be executed by Nix or on a real target desktop before merge:

- `pytest -q` for the complete suite;
- `ruff check .`;
- `mypy src`;
- `nix flake check --print-build-logs`;
- `nix build .#nix-settings --print-build-logs`;
- `./result/bin/nix-settings doctor`;
- `./result/bin/nix-settings sound` on Wayland with PipeWire and WirePlumber.

The live test must confirm that the compositor reports a layer surface, the window does not float, sliders remain draggable, selection changes fire once, and scrolling remains stable while PipeWire events arrive.
