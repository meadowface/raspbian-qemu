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
    test_tool - Test running of the tool itself.
"""

import contextlib
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

# Prevent next imports from creating __pycache__ directory
sys.dont_write_bytecode = True
from test_common import TestImageBase, read_mbr, raspiqemu

OTHERIMG  = "other.img"

class TestPrep(TestImageBase):
    """Check the prep and unprep actions."""
    def assertPrepped(self, image):
        """Perform checks to assert that an image is in a prepped state.
           Returns the results of runImage for further checking.
        """
        runinfo = self.runImage(image)

        self.assertIn(self.SDA_RULES, runinfo.files)

        preload = b"#" + self.MAGIC_PRELOAD.encode() + b"\n"
        self.assertEqual(runinfo.files[self.PRELOAD].contents, preload)

        return runinfo

    def assertUnPrepped(self, image):
        """Perform checks to assert that an image is in a unprepped state.
           Returns the results of runImage for further checking.
        """
        runinfo = self.runImage(image)

        self.assertNotIn(self.SDA_RULES, runinfo.files)

        preload = self.MAGIC_PRELOAD.encode() + b"\n"
        self.assertEqual(runinfo.files[self.PRELOAD].contents, preload)

        # If there are no host keys, then the initscript should be set to
        # generate them.
        if "/etc/ssh/ssh_host_dsa_key" not in runinfo.files:
            initscript = runinfo.files[self.REGEN_INITSCRIPT]
            self.assertIn(b"ssh-keygen", initscript.contents)

        return runinfo

    def test_testimg_starts_unprepped(self):
        """Check that test image is initially unprepped."""
        self.assertUnPrepped(self.TESTIMG)

    def test_simple_prep(self):
        """Simple prep."""
        self.callTool(["prep", self.TESTIMG])
        self.assertPrepped(self.TESTIMG)

    def test_simple_prep_keep_root(self):
        """Simple prep with --keep-root."""
        self.callTool(["--keep-root", "prep", self.TESTIMG])
        self.assertPrepped(self.TESTIMG)

    def test_prep_missing_source(self):
        """Prep with missing source file."""
        with self.assertRaises(subprocess.CalledProcessError):
            self.callTool(["--debug", "prep", "missing.img"])

    def test_multi_prep(self):
        """Multiple preps on same image."""
        self.callTool(["prep", self.TESTIMG])
        self.callTool(["prep", self.TESTIMG])
        self.assertPrepped(self.TESTIMG)

    def test_prep_to_dest(self):
        """Prep to a different dest file."""
        with self.assertImageNotAltered(self.TESTIMG):
            self.callTool(["prep", self.TESTIMG, OTHERIMG])
            self.assertPrepped(OTHERIMG)
            self.assertOnlyUserReadable(OTHERIMG)
            os.unlink(OTHERIMG)

    def test_simple_unprep(self):
        """Simple unprep."""
        self.callTool(["unprep", self.TESTIMG])
        self.assertUnPrepped(self.TESTIMG)

    def test_simple_unprep_keep_root(self):
        """Simple unprep. with --keep-root"""
        self.callTool(["--keep-root", "unprep", self.TESTIMG])
        self.assertUnPrepped(self.TESTIMG)

    def test_multi_unprep(self):
        """Multiple unpreps on same image."""
        self.callTool(["unprep", self.TESTIMG])
        self.callTool(["unprep", self.TESTIMG])
        self.assertUnPrepped(self.TESTIMG)

    def test_unprep_to_dest(self):
        """Unprep to a different dest file."""
        self.callTool(["unprep", self.TESTIMG, OTHERIMG])
        self.assertUnPrepped(OTHERIMG)
        self.assertOnlyUserReadable(OTHERIMG)
        os.unlink(OTHERIMG)

    def test_grow_root(self):
        """Prep with growing root."""
        root_before = read_mbr(self.TESTIMG).partitions[1].size
        self.callTool(["prep", "--grow-root=1M", self.TESTIMG])
        root_after = read_mbr(self.TESTIMG).partitions[1].size
        self.assertEqual(root_after, root_before + 1024**2)

        # Make sure that as well as growing the root, it was prepped too.
        self.assertPrepped(self.TESTIMG)

    def prep_with_public_key(self, pubkey):
        """prep an image adding a public key with the contents of pubkey."""
        with tempfile.NamedTemporaryFile() as keyfile:
            keyfile.write(pubkey)
            keyfile.flush()
            self.callTool(["prep", "--add-public-key=" + keyfile.name, self.TESTIMG])

    def test_add_public_key(self):
        """prep --add-public-key."""
        PUBKEY = b"LET ME IN\n"
        self.prep_with_public_key(PUBKEY)
        runinfo = self.assertPrepped(self.TESTIMG)
        self.assertIn(self.AUTHKEYS, runinfo.files)
        self.assertEqual(runinfo.files[self.AUTHKEYS].contents,
                         PUBKEY)

    def test_add_bad_public_key(self):
        """prep --add-public-key but with a private key file.
        Make sure image isn't altered at all."""
        with self.assertImageNotAltered(self.TESTIMG):
            with self.assertRaises(subprocess.CalledProcessError):
                self.callTool(["prep", "--add-public-key=", self.TESTIMG])

    def test_add_bad_private_key(self):
        with self.assertImageNotAltered(self.TESTIMG):
            with self.assertRaises(subprocess.CalledProcessError):
                self.prep_with_public_key(b"-----BEGIN RSA PRIVATE KEY-----")

    def test_add_duplicate_public_key(self):
        """prep --add-public-key with a duplicate key."""
        PUBKEY = b"LET ME IN\n"
        for attempt in range(2):
            self.prep_with_public_key(PUBKEY)

        runinfo = self.assertPrepped(self.TESTIMG)
        self.assertIn(self.AUTHKEYS, runinfo.files)
        self.assertEqual(runinfo.files[self.AUTHKEYS].contents,
                         PUBKEY)

    def test_add_multiple_public_keys(self):
        """prep --add-public-key with a multiple keys."""
        PUBKEY_ONE = b"LET ME IN\n"
        PUBKEY_TWO = b"SUDO LET ME IN!\n"
        self.prep_with_public_key(PUBKEY_ONE)
        self.prep_with_public_key(PUBKEY_TWO)

        runinfo = self.assertPrepped(self.TESTIMG)
        self.assertIn(self.AUTHKEYS, runinfo.files)
        self.assertEqual(runinfo.files[self.AUTHKEYS].contents,
                         PUBKEY_ONE + PUBKEY_TWO)

    def test_set_host_keys(self):
        """prep --set-host-keys.
        Make sure the keys get injected with the right permissions and that
        the initscript is properly altered."""

        self.callTool(["prep", "--set-host-keys=" + self.HOSTKEYSTAR, self.TESTIMG])

        runinfo = self.assertPrepped(self.TESTIMG)
        with tarfile.open(self.HOSTKEYSTAR) as tar:
            for member in tar:
                filespec = os.path.join("/etc/ssh", member.name)
                self.assertIn(filespec, runinfo.files)
                self.assertEqual(runinfo.files[filespec].mode, member.mode)
                self.assertEqual(runinfo.files[filespec].uid, member.gid)
                self.assertEqual(runinfo.files[filespec].uid, member.gid)

        initscript = runinfo.files[self.REGEN_INITSCRIPT]
        self.assertNotIn(b"ssh-keygen", initscript.contents)

    @contextlib.contextmanager
    def bad_host_keys(self, alterfunc):
        """Context maager which yields a temp filename of a tarfile that
        is a copy of the self.HOSTKEYSTAR file but with members altered with
        alterfunc."""
        with tempfile.NamedTemporaryFile() as tmptar:
            with tarfile.open(fileobj=tmptar, mode="w") as badtar:
                with tarfile.open(self.HOSTKEYSTAR) as goodtar:
                    for member in goodtar:
                        alterfunc(member)
                        badtar.addfile(member, goodtar.extractfile(member))
                    tmptar.flush()
                    yield tmptar.name

    def test_set_bad_host_keys(self):
        """prep --set-host-keys with a keys with bad permissions."""
        def bad_mode_pub(member):
            if member.name.endswith(".pub"):
                member.mode=0o077
        def bad_mode_private(member):
            if not member.name.endswith(".pub"):
                member.mode=0o077
        def bad_owner(member):
            member.uid = 1000
        def bad_group(member):
            member.gid = 1000

        for alterfunc in (bad_mode_pub, bad_mode_private, bad_owner, bad_group):
            with self.bad_host_keys(alterfunc) as badkeys:
                with self.assertRaises(subprocess.CalledProcessError):
                    with self.assertImageNotAltered(self.TESTIMG):
                        self.callTool(["prep", "--set-host-keys=" + badkeys,
                                      self.TESTIMG])


class TestExtract(TestImageBase):
    """Test the extract action."""
    def assertTarfilesEqual(self, afilespec, bfilespec):
        """Check that the contents of tarfiles afilespec and bfilespec
        are the same for the attributes we care about:
            name, uid, gid, mode, size and contents.
        The members do not have to be in the same order.
        """
        with tarfile.open(afilespec) as a, tarfile.open(bfilespec) as b:
            a_members = sorted(a.getmembers(), key=lambda m: m.name)
            b_members = sorted(b.getmembers(), key=lambda m: m.name)

            self.assertEqual(len(a_members), len(b_members))
            for a_member, b_member in zip(a_members, b_members):
                self.assertEqual(a_member.name, b_member.name)
                self.assertEqual(a_member.uid, b_member.uid)
                self.assertEqual(a_member.gid, b_member.gid)
                self.assertEqual(a_member.mode, b_member.mode)
                self.assertEqual(a_member.size, b_member.size)
                a_contents = a.extractfile(a_member).read()
                b_contents = b.extractfile(b_member).read()
                self.assertEqual(a_contents, b_contents)

    def test_no_hostkeys(self):
        """Test extract when there are no host keys."""
        with self.assertRaises(subprocess.CalledProcessError):
            self.callTool(["extract", self.TESTIMG, "hostkeys", "missing.tar"])

    def test_hostkeys(self):
        """Inject some host keys and then extract, confirming that what we
        extracted is what we injected."""
        EXTRACTED="extracted.tar"
        self.callTool(["prep", "--set-host-keys=" + self.HOSTKEYSTAR, self.TESTIMG])
        self.callTool(["extract", self.TESTIMG, "hostkeys", EXTRACTED])
        try:
            self.assertTarfilesEqual(self.HOSTKEYSTAR, EXTRACTED)
            self.assertOnlyUserReadable(EXTRACTED)
        finally:
            os.unlink(EXTRACTED)

    def test_hostkeys_keep_root(self):
        """Simple host keys extraction with --keep-root."""
        EXTRACTED="ignored.tar"
        self.callTool(["prep", "--set-host-keys=" + self.HOSTKEYSTAR, self.TESTIMG])
        self.callTool(["--keep-root", "extract", self.TESTIMG, "hostkeys", EXTRACTED])
        os.unlink(EXTRACTED)

class TestBuildKernel(TestImageBase):
    """Test the build-kernel action."""
    SOURCEDIR="test-linux"

    def test_build_kernel_no_arg(self):
        """Run build-kernel without a source argument."""
        with self.assertRaises(subprocess.CalledProcessError):
            self.callTool(["build-kernel"])

    def test_build_kernel_bad_arg(self):
        """Run build-kernel with bad source arguments."""
        # Non-existing dir
        with self.assertRaises(subprocess.CalledProcessError):
            self.callTool(["build-kernel", ""])

        # Empty dir
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(subprocess.CalledProcessError):
                self.callTool(["build-kernel", tmpdir])

        # File, not dir
        with self.assertRaises(subprocess.CalledProcessError):
            self.callTool(["build-kernel", self.TESTIMG])

    @unittest.skipIf(os.path.isfile(raspiqemu.KERNEL_BINARY),
                     "%s already exists." % (raspiqemu.KERNEL_BINARY,))
    @unittest.skipUnless(os.path.isdir(SOURCEDIR),
                         "requires %s/" % (SOURCEDIR,))
    def test_build_kernel(self):
        """Build the kernel from a checkout named test-linux.  Easiest
        way is to just symlink test-linux to an existing checkout.

        If test-linux does not exist, this test will be skipped.
        """
        self.callTool(["build-kernel", self.SOURCEDIR])
        self.assertTrue(os.path.isfile(raspiqemu.KERNEL_BINARY))

class TestRun(TestImageBase):
    """Check the run action."""
    def test_monitor_quit(self):
        """run and quit using the monitor."""
        self.runImage(self.TESTIMG, growmode=self.MAGIC_GROW_MODE_SLEEP)

    def test_console_input(self):
        """run and quit using the monitor."""
        self.runImage(self.TESTIMG, growmode=self.MAGIC_GROW_MODE_INPUT)

    def test_with_ssh_port(self):
        """run --with-ssh-port."""
        self.runImage(self.TESTIMG, growmode=self.MAGIC_GROW_MODE_SSH)

    def test_with_display(self):
        """run --with-display.  Only checked if DISPLAY is set.
        (It's up to test runner to confirm a window pops up, it's not checked
        by code.)"""
        #TODO: Put in a headless xserver of some sort and check the window.
        if "DISPLAY" in os.environ and os.environ["DISPLAY"]:
            self.runImage(self.TESTIMG, options=["--with-display"])

    def test_with_audio(self):
        """run --with-audio.
        (Nothing is really checked except that the switch is accepted and the
        machine boots."""
        self.runImage(self.TESTIMG, options=["--with-audio"])

if __name__ == "__main__":
    unittest.main(failfast=True)
