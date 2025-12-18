from pathlib import Path

import pytest


ALLOWED_TEST_FILES = {"test_vector_can_interface_unit.py"}


def pytest_ignore_collect(collection_path, config):
    """Skip collecting any hardware-dependent demo tests.

    Import errors were raised before we could mark items as skipped in
    ``pytest_collection_modifyitems``. By ignoring disallowed files here, we
    prevent pytest from importing them at all on non-Windows/non-hardware
    environments.
    """

    return Path(collection_path).name not in ALLOWED_TEST_FILES


def pytest_collection_modifyitems(config, items):
    for item in items:
        if Path(str(item.fspath)).name not in ALLOWED_TEST_FILES:
            item.add_marker(
                pytest.mark.skip(reason="Pominięto demonstracyjne testy wymagające sprzętu Vector")
            )
