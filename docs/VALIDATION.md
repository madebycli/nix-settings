# Validation

## Automated

```bash
python -m compileall -q src
pytest -q
ruff check .
mypy src
nix flake check
```

## Live Wayland and PipeWire validation

```bash
nix-settings doctor
nix-settings sound
```

Confirm that the window is a GtkLayerShell surface, opens at its final size, and keeps the 2x2 workspace. Recording should contain only real apps. Sliders must remain stable during PipeWire events. Every stream Route selector must keep the same 300 logical-pixel width on normal and 15-inch displays, with a smaller non-overlapping fallback on narrow monitors. Long labels must ellipsize instead of resizing rows. The close control must stay circular and theme colors must be respected.
