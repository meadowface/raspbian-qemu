#!/usr/bin/env python3
# The MIT License (MIT)
#
# Copyright (c) 2016 Marc Meadows
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
    test_utils - Test for the utility classes and functions inside
                 raspbian-qemu.
"""

import os
import sys
import tempfile
import unittest

# Prevent next imports from creating __pycache__ directory
sys.dont_write_bytecode = True
from test_common import raspiqemu

class TestDataCopy(unittest.TestCase):
    """Unit test data_copy() and related functions."""
    SOURCE = "1234567890"
    DEST   = "abcdefghjiklmnopqrstuvwxyz"
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

        self.source = os.path.join(self.tmpdir.name, "source")
        with open(self.source, "w") as sourcefile:
            sourcefile.write(self.SOURCE)

        self.dest = os.path.join(self.tmpdir.name, "dest")
        with open(self.dest, "w") as destfile:
            destfile.write(self.DEST)

    def tearDown(self):
        self.tmpdir.cleanup()

    @property
    def source_contents(self):
        """Return the contents of the sourcefile as bytes."""
        with open(self.source) as sourcefile:
            return sourcefile.read()

    @property
    def dest_contents(self):
        """Return the contents of the destfile as bytes."""
        with open(self.dest) as destfile:
            return destfile.read()

    def test_wholefilecopy(self):
        """Simple file copy."""
        raspiqemu.data_copy(self.source, self.dest)
        self.assertEqual(self.dest_contents, self.SOURCE)

    def test_source_offset(self):
        """File copy with source_offset."""
        raspiqemu.data_copy(self.source, self.dest, source_offset=2)
        self.assertEqual(self.dest_contents, self.SOURCE[2:])

    def test_source_offset_same(self):
        """File copy with source_offset into same file."""
        raspiqemu.data_copy(self.source, self.source, source_offset=2)
        self.assertEqual(self.source_contents, self.SOURCE[2:])

    def test_dest_offset(self):
        """File copy with dest_offset."""
        raspiqemu.data_copy(self.source, self.dest, dest_offset=2)
        self.assertEqual(self.dest_contents, self.DEST[:2] + self.SOURCE)

    def test_dest_offset_same(self):
        """File copy with dest_offset into same file."""
        raspiqemu.data_copy(self.source, self.source, dest_offset=2)
        self.assertEqual(self.source_contents, self.SOURCE[:2] + self.SOURCE)

    def test_count(self):
        """File copy with count."""
        raspiqemu.data_copy(self.source, self.dest, count=5)
        self.assertEqual(self.dest_contents, self.SOURCE[:5])

    def test_suffixes(self):
        """Suffix conversion."""
        counts = ((5, "5"),
                  (1024, "1K"),
                  (4096, "4K"),
                  (1024**2, "1M"),
                  (1024**3, "1G"),
                 )

        self.assertIsNone(raspiqemu.resolve_suffix(None))
        self.assertEqual(raspiqemu.resolve_suffix(99), 99)
        for sizeint, sizestr in counts:
            for case in (sizestr.upper(), sizestr.lower()):
                self.assertEqual(raspiqemu.resolve_suffix(case), sizeint)

if __name__ == "__main__":
    unittest.main(failfast=True)
