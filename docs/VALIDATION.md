# Validation record

Validation performed in the implementation environment:

- `python -m compileall -q src`: passed
- `pytest -q`: passed, 18 tests
- `PYTHONPATH=src python -m nix_settings.__main__ --help`: passed
- `PYTHONPATH=src python -m nix_settings.__main__ --version`: passed

Not executed in this environment because the executables or desktop services were unavailable:

- `ruff check .`
- `mypy src`
- `nix flake check --print-build-logs`
- `nix build .#nix-settings --print-build-logs`
- built-package doctor smoke test
- real GTK4 Layer Shell visual test
- real PipeWire and WirePlumber live-audio test

The Flake defines checks for compilation, pytest, Ruff, mypy, CLI smoke behavior and runtime-closure policy. Visual behavior and live audio controls must still be tested in a real Wayland desktop session with PipeWire and WirePlumber.
