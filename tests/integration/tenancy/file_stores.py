"""The file stores the tenancy tests run against, and the mark of a test that needs only the fake.

A test that reads or writes files runs against the fake and Garage (the ``files`` fixture of the
conftest). A test that asserts nothing about files carries ``FAKE_FILES_ONLY``: Garage would add a
container run and no behaviour.
"""

import pytest

FAKE = "fake"
GARAGE = "garage"
FILE_STORES = [FAKE, GARAGE]
FAKE_FILES_ONLY = pytest.mark.parametrize("files", [FAKE], indirect=True)
