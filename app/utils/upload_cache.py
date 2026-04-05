import hashlib


def build_uploaded_file_cache_key(uploaded_file: object, prefix: str = "invoice") -> str:
    """Build a stable cache key from uploaded file metadata and content bytes."""
    name = getattr(uploaded_file, "name", "uploaded_file")
    size = getattr(uploaded_file, "size", None)

    if hasattr(uploaded_file, "getvalue"):
        content = uploaded_file.getvalue()
    else:
        current_position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
        content = uploaded_file.read()
        if current_position is not None and hasattr(uploaded_file, "seek"):
            uploaded_file.seek(current_position)

    if size is None:
        size = len(content)

    digest = hashlib.sha256(content).hexdigest()[:16]
    return f"{prefix}_{name}_{size}_{digest}"
