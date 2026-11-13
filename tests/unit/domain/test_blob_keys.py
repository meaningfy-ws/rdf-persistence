"""The one rule for a blob key: the S3 adapter, the fake file store and a restore all apply it (tenant-dump-restore PD-13)."""

import pytest

from rdf_persistence.domain.blob_keys import checked_blob_key

BAD_KEYS = [
    "a/../b",
    "..",
    "../x",
    "a/..",
    "a/./b",
    "./a",
    "a/.",
    ".",
    "a\x00b",
    "a\nb",
    "a\x7fb",
    "",
    "a\udcffb",  # a byte that is not UTF-8, as tarfile decodes it
]
ORDINARY_KEYS = ["a..b", "..x", "x/..y/z", "folder/ä b+c.bin", "été/日本語 ✓.bin", "k" * 300]


@pytest.mark.parametrize("key", BAD_KEYS, ids=repr)
def test_a_key_that_climbs_is_empty_or_holds_a_control_or_non_utf8_character_is_refused(key):
    with pytest.raises(ValueError, match="key"):
        checked_blob_key(key)


@pytest.mark.parametrize("key", ORDINARY_KEYS)
def test_an_ordinary_key_is_returned_unchanged(key):
    assert checked_blob_key(key) == key, "the key itself"
