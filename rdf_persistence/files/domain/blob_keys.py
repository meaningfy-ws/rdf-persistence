"""The one rule for a blob key: the S3 adapter, the fake file store and a restore all apply it (tenant-dump-restore PD-13)."""

DOT_SEGMENTS = frozenset({".", ".."})
DELETE_CHARACTER = "\x7f"


def checked_blob_key(key: str) -> str:
    """``key`` if it is a key the toolkit stores.

    A key is not empty, has no ``.`` or ``..`` segment (a path to climb out of a prefix), no control
    character and is UTF-8 (``tarfile`` decodes a stray byte to a lone surrogate, which does not encode).

    Raises:
        ValueError: ``key`` is none of that.
    """
    if (
        not key
        or not DOT_SEGMENTS.isdisjoint(key.split("/"))
        or any(ord(c) < ord(" ") or c == DELETE_CHARACTER for c in key)
        or not _is_utf8(key)
    ):
        raise ValueError(
            "the key is empty, has a '.' or '..' segment, has a control character or is not UTF-8"
        )
    return key


def _is_utf8(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True
