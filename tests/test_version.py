from __future__ import annotations

import os
import unittest
from unittest import mock

import version


class VersionTests(unittest.TestCase):
    def test_normalizes_tag_prefix(self) -> None:
        self.assertEqual(version.normalize_version("v1.2.3"), "1.2.3")

    def test_reads_release_version_from_environment(self) -> None:
        with mock.patch.dict(os.environ, {"K2C_VERSION": "v2.0.1"}):
            self.assertEqual(version.get_version(), "2.0.1")


if __name__ == "__main__":
    unittest.main()
