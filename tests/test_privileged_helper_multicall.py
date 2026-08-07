from pathlib import Path
from unittest import mock

import pytest

from nix_settings import privileged_helper


def test_executable_preserves_nix_multicall_entrypoint() -> None:
    invocation = "/nix/store/fake-nix/bin/nix-env"
    resolved = Path("/nix/store/fake-nix/bin/nix")

    with (
        mock.patch.object(privileged_helper.shutil, "which", return_value=invocation),
        mock.patch.object(privileged_helper.Path, "resolve", return_value=resolved),
    ):
        assert privileged_helper.executable("nix-env") == invocation


def test_executable_rejects_untrusted_alias_to_store_binary() -> None:
    invocation = "/tmp/nix-env"
    resolved = Path("/nix/store/fake-nix/bin/nix")

    with (
        mock.patch.object(privileged_helper.shutil, "which", return_value=invocation),
        mock.patch.object(privileged_helper.Path, "resolve", return_value=resolved),
        pytest.raises(privileged_helper.HelperError, match="refusing non-Nix executable path"),
    ):
        privileged_helper.executable("nix-env")
