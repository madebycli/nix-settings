from nix_settings.backend.requests import RequestGate


def test_stale_request_results_are_rejected() -> None:
    gate: RequestGate[int] = RequestGate()
    first = gate.begin()
    second = gate.begin()
    assert not gate.current(first)
    assert gate.current(second)
