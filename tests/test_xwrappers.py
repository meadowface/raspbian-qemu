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
    test_xwrappers - Tests for the xwrappers module.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

# Prevent next imports from creating __pycache__ directory
sys.dont_write_bytecode = True
import xwrappers
from xwrappers import (Display,
                       saved_display,
                       xvfb,
                       linux_unix_domain_sockets,
                       xtrace,
                      )

class TestDISPLAYBase(unittest.TestCase):
    """Base test class which saves/restores the DISPLAY environment variable
    around each test.  Much like saved_display(), but since that's being
    tested too..."""
    def setUp(self):
        self.saved_display = os.environ.get("DISPLAY")

    def tearDown(self):
        if self.saved_display is None:
            del os.environ["DISPLAY"]
        else:
            os.environ["DISPLAY"] = self.saved_display

class TestDisplay(TestDISPLAYBase):
    """Test the Display str derivative class."""
    def test_new(self):
        with self.assertRaises(ValueError):
            Display("missing colon")

        with self.assertRaises(ValueError):
            Display("nodisplaynum:")

        self.assertEqual(Display(0), ":0")

        self.assertEqual(Display(":44"), ":44")

    def test_int(self):
        self.assertEqual(int(Display(":1")), 1)

        self.assertEqual(int(Display("host:10")), 10)

    def test_set(self):
        d = Display(7)
        d.set()
        self.assertEqual(os.environ[Display.DISPLAY], d)

    def test_get(self):
        os.environ["DISPLAY"] = ":8"
        self.assertEqual(os.environ[Display.DISPLAY], Display.get())

class TestSavedDisplay(TestDISPLAYBase):
    """Test the saved_display context manager."""
    def test_basic_save(self):
        os.environ["DISPLAY"] = "abc:1"
        with saved_display() as old_display:
           self.assertEqual(old_display, "abc:1")
           os.environ["DISPLAY"] = "123:4"
        self.assertEqual(os.environ["DISPLAY"], "abc:1")

    def test_no_display_env(self):
        del os.environ["DISPLAY"]
        with saved_display() as old_display:
            self.assertIsNone(old_display)
            os.environ["DISPLAY"] = "123:4"
        self.assertIsNone(os.environ.get("DISPLAY"))

    def test_empty_display_env(self):
        os.environ["DISPLAY"] = ""
        with saved_display() as old_display:
            self.assertEqual(old_display, "")
            os.environ["DISPLAY"] = ":123"
        self.assertEqual(os.environ.get("DISPLAY"), "")

class TestXvfb(TestDISPLAYBase):
    """Test the Xvfb context manager."""
    def test_simple(self):
        os.environ["DISPLAY"] = ":88"
        with xvfb() as display:
            self.assertEqual(display, os.environ["DISPLAY"])
            self.assertNotEqual(display, ":88")

    def test_bad_options(self):
        with self.assertRaises(subprocess.CalledProcessError):
            with xvfb(options=["-xxx"]) as display:
                pass

    def test_good_options(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with xvfb(options=["-fbdir", tmpdir]) as display:
                # A file in this directory means the option got through.
                self.assertTrue(os.path.exists(os.path.join(tmpdir,
                                                            "Xvfb_screen0")))

class TestLinuxUnixDomainSockets(unittest.TestCase):
    """Test the utility function linux_unix_domain_sockets()"""
    def test_all(self):
        sockets = linux_unix_domain_sockets()
        #NOTE: This presupposes that a Linux system will have *some*
        #      unix domain sockets defined.
        self.assertGreater(len(sockets), 0)

    def test_pid(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            #NOTE: Use an abstract socket to not have any message in the
            #      filesystem.  They should up in /proc/net/unix too.
            sock.bind("\0AbstractSocket")
            sockets = linux_unix_domain_sockets(os.getpid())
            self.assertIn("@AbstractSocket", sockets)

        sockets = linux_unix_domain_sockets(os.getpid())
        self.assertNotIn("@AbstractSocket", sockets)

class TestXTrace(TestDISPLAYBase):
    """Test the xtrace context manager."""
    def test_simple(self):
        with tempfile.NamedTemporaryFile() as log:
            with xtrace(log.name) as display:
                # Send an X connect.  Must recv the first 8 bytes back for
                # xtrace to log.
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.connect("/tmp/.X11-unix/X%d" % (int(display)))
                    sock.sendall(b"l\0\x0b\0\0\0\0\0\0\0\0\0")
                    #              ^-- little-endian
                    #                 ^^^^--- protocol version (11)
                    sock.recv(8)
            self.assertIn(b"lsb-first", log.read())

if __name__ == "__main__":
    unittest.main(failfast=True)
