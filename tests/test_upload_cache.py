import unittest

from app.utils.upload_cache import build_uploaded_file_cache_key


class FakeUploadedFile:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self.size = len(content)
        self._content = content

    def getvalue(self):
        return self._content


class UploadCacheKeyTests(unittest.TestCase):
    def test_cache_key_changes_when_file_content_changes(self):
        original = FakeUploadedFile("invoice.png", b"original-bytes")
        updated = FakeUploadedFile("invoice.png", b"updated-bytes")

        original_key = build_uploaded_file_cache_key(original)
        updated_key = build_uploaded_file_cache_key(updated)

        self.assertNotEqual(original_key, updated_key)


if __name__ == "__main__":
    unittest.main()
