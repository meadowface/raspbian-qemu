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
    test_common - Common code for testing raspbian-qemu with the include
                  test.img.gz.  This module works in concert, and requires,
                  make-test-image.  But a test.img.gz is included in the
                  repository, so make-test-image only has to be present, not
                  run.
"""

import codecs
import collections
import contextlib
from ctypes import LittleEndianStructure, c_ubyte, c_uint, sizeof
import gzip
import hashlib
import importlib.machinery
import io
import os
import socket
import subprocess
import sys
import tarfile
import unittest

TOOL = "../raspbian-qemu"

# Prevent next imports from creating __pycache__ directory
sys.dont_write_bytecode = True

# import the tool so we can access it directly as a module for some unit tests.
raspiqemu = importlib.machinery.SourceFileLoader('raspiqemu', TOOL).load_module()

def read_mbr(image):
    """Read an MBR with ctypes and return it.  Not for general use.  Works
    with the MBRs in the Raspbian images we test, not tested with anything
    else.  Mostly used as a fun second opinion to parted which is used in
    the tool under testing.
    """
    class Partition(LittleEndianStructure):
        """https://en.wikipedia.org/wiki/Master_boot_record#Partition_table_entries"""
        SECTOR_SIZE = 512
        _pack_ = 1
        _fields_ = [("status",    c_ubyte),
                    ("chs_begin", c_ubyte * 3),
                    ("type",      c_ubyte),
                    ("chs_end",   c_ubyte * 3),
                    ("lba_begin", c_uint),
                    ("lba_size",  c_uint),
                   ]

        @property
        def begin(self):
            """Convenience function for returning begin in bytes."""
            return self.lba_begin * self.SECTOR_SIZE

        @property
        def size(self):
            """Convenience function for returning size in bytes."""
            return self.lba_size * self.SECTOR_SIZE
    assert sizeof(Partition) == 16, "Partition definition error"

    class MBR(LittleEndianStructure):
        """https://en.wikipedia.org/wiki/Master_boot_record#Sector_layout"""
        _pack_ = 1
        _fields_ = [("skip",       c_ubyte * 446),
                    ("partitions", Partition * 4),
                    ("signature",  c_ubyte * 2),
                   ]
    assert sizeof(MBR) == 512, "MBR definition error"

    with open(image, "rb") as img:
        mbr = MBR.from_buffer(bytearray(img.read(sizeof(MBR))))
        assert bytes(mbr.signature) == b"\x55\xAA", "Invalid MBR signature."
        return mbr

class TestImageBase(unittest.TestCase):
    """Base class for tests using the included test.img which is created
    with the make-test-image script.
    """
    TESTIMG = "test.img"

    # This will be there if the hidden --keep-root is passed.
    ROOT_IMG = "root.img"

    # Some files we will be using repeatedly during checks.
    HOSTKEYSTAR      = "test-host-keys.tar"
    REGEN_INITSCRIPT = "/etc/init.d/regenerate_ssh_host_keys"
    AUTHKEYS         = "/home/pi/.ssh/authorized_keys"
    PRELOAD          = "/etc/ld.so.preload"
    SDA_RULES        = "/etc/udev/rules.d/90-qemu-sda.rules"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Extract the magic strings from the make-test-image script so we only
        # define them in one place and set them as instance variables.
        for line in open("make-test-image"):
            if line.startswith("MAGIC"):
                name, equal, value = line.strip().partition("=")
                if '"' not in value:
                    value = int(value)
                else:
                    value = value.strip('"')
                setattr(self, name, value)

    def setUp(self):
        """Create a shiny new TESTIMG from the included .gz file for each run."""
        with gzip.open("test.img.gz") as gz, open(self.TESTIMG, "wb") as img:
            #NOTE: It's doesn't matter that this slurps everything up into
            #      memory as it's a < 5Mb file.
            img.write(gz.read())

    def tearDown(self):
        os.unlink(self.TESTIMG)

    def test_read_mbr(self):
        """Sanity check unit test read_mbr() against the test image which
        has a known partition layout.
        (and yes, this is testing code testing testing code)
        """
        mbr = read_mbr(self.TESTIMG)
        self.assertEqual(mbr.partitions[0].begin, 4096)
        self.assertEqual(mbr.partitions[0].size,  4096)
        self.assertEqual(mbr.partitions[1].begin, 8192)
        self.assertEqual(mbr.partitions[1].size,
                         self.MAGIC_ROOT_SECTORS * 512)

    def callTool(self, args):
        """Call the raspbian-qemu tool with a check for a kept root.img."""
        # Clean up any root images so we can assert whether it's created
        # or not after the run.
        if os.path.exists(self.ROOT_IMG):
            os.unlink(self.ROOT_IMG)

        cmd = [TOOL]
        # Assume any time the trace function is set it's coverage and make
        # sure to spawn the tool under coverage as well.
        if sys.gettrace():
            cmd = ["python3-coverage", "run", "--parallel-mode"] + cmd
        subprocess.check_output(cmd + args, stderr=subprocess.STDOUT)

        # Now make sure root.img was created if request but not if it wasn't.
        # If created correctly, check its state and then clean it up.
        keep_root = "--keep-root" in args
        self.assertEqual(os.path.exists(self.ROOT_IMG), keep_root)
        if keep_root:
            self.assertOnlyUserReadable(self.ROOT_IMG)
            os.unlink(self.ROOT_IMG)

    def runImage(self, image, *, growmode=None, options=[]):
        """Execute the test image pointed to by image, adding any options
        and interact with it according to the growmode if any (see below).

        Returns a RunInfo tuple, see its docstring for description
        of fields.
        """
        class File(tarfile.TarInfo):
            """TarInfo descendant with no changes except that we can add a
            contents attribute. (TarInfo has slots set)"""

        class RunInfo(collections.namedtuple("RunInfo",
                                             ("growmode",
                                              "version",
                                              "bootup",
                                              "files",
                                              "growmode_output",
                                              "shutdown"
                                             ))):
            """Data-holder for the results of a running the test image.
                growmode        - which growmode was used.
                version         - version of the test image.
                bootup          - bootup messages on the console.
                files           - a mapping of path to File object.
                growmode_output - any output from growmodes.
                shutdown        - shutdown messages on the console.
            """
            pass

        marker = "\n" + self.MAGIC_MARKER + "\n"

        # Pass in the growmode by growing the root partition that many sectors.
        # First make sure the root partition is an exepcted size.  If it's
        # been grown already, growmode won't work.
        if growmode:
            self.assertEqual(read_mbr(self.TESTIMG).partitions[1].size,
                             self.MAGIC_ROOT_SECTORS * 512)
            self.callTool(["prep", image, "--grow-root", str(growmode * 512)])

        if growmode == self.MAGIC_GROW_MODE_SSH:
            options += ["--with-ssh-port", "7022"]

        # Run the image using the tool and gather its output.
        # Along the way, select behavior based on the current growmode.
        output = ""
        with subprocess.Popen([TOOL, "run", image] + options,
                               universal_newlines=True,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL) as run:
            try:
                def read_markers(count):
                    """Read until count *more* markers are read
                    and return a list containing the data between the
                    new markers."""
                    nonlocal output
                    start_count = output.count(marker)

                    while True:
                        output_byte = run.stdout.read(1)
                        if not output_byte:
                            raise ValueError("Unexpected EOF from run.")
                        output += output_byte
                        if output.count(marker) - start_count == count:
                            break

                    return output.split(marker)[start_count:]

                version = read_markers(3)[1]
                self.assertEqual(version, self.MAGIC_VERSION)

                if growmode == self.MAGIC_GROW_MODE_SSH:
                    # In this growmode the test image is going to wait for a
                    # connection on the ssh port, display whatever is sent to
                    # that port, and then continue on to clean shutdown.

                    #TODO: Is a race possible here where we try to connect before
                    #TODO: the nc is listening?  Or does the qemu networking
                    #TODO: basically eliminate it by keeping data in transit?
                    #TODO: Putting in a sleep 10 before bringing up the network
                    #TODO: in the test image still worked...
                    #TODO: use timeout in create_connection()
                    sshdata = "HIYA-FROM-SSH\n"
                    with socket.create_connection(("127.0.0.1", 7022)) as s:
                        s.send(sshdata.encode())

                    self.assertIn(sshdata, read_markers(1)[0])
                elif growmode == self.MAGIC_GROW_MODE_INPUT:
                    # In this growmode the test image is going to wait forever
                    # for a line to be input.  Send it something so it will
                    # exit cleanly.  This proves that the console will receive
                    # data from stdin.
                    inputdata = "HIYA FROM STDIN\n"
                    run.stdin.write(inputdata)
                    run.stdin.flush()
                    self.assertIn(inputdata, read_markers(1)[0])
                elif growmode == self.MAGIC_GROW_MODE_SLEEP:
                    # In this growmode the test image is going to sleep
                    # forever.  Since we're using mon:stdio, send Ctrl-a 'c'
                    # to enter the monitor, then 'quit<enter>'' to exit the
                    # emulator.
                    run.stdin.write("\x01cquit\n")
                    run.stdin.flush()
                    #print("quit sent", flush=True)
                output += run.stdout.read()
            except:
                run.terminate()
                raise

        # The test image will output to stdout the following:
        #   boot up messages
        #   "\n$MAGIC_MARKER\n"
        #   "$MAGIC_VERSION"
        #   "\n$MAGIC_MARKER\n"
        #   a uuencoded tarfile containing the contents of the filesystem
        #   "\n$MAGIC_MARKER\n"
        #   any growmode output
        #   (The below might not be present in some growmodes.)
        #   "\n$MAGIC_MARKER\n"
        #   shutdown messages

        # Decode the filesystem tar and make a TarFile object out of it.
        sections = output.split(marker)
        bootup, version, uu, growmode_output = sections[:4]
        shutdown = sections[4] if len(sections) >= 5 else None
        tarbytes = io.BytesIO(codecs.decode(uu.encode(), "uu"))
        tar = tarfile.open(fileobj=tarbytes, tarinfo=File)

        # Go through the tarfile extracting File objects and populating
        # a .contents member with the contents of each file, finally putting
        # them in a files dictionary to return.
        files = {}
        for file in tar:
            file.contents = tar.extractfile(file)
            if file.contents is not None:
                file.contents = file.contents.read()
            files["/" + file.name] = file

        return RunInfo(growmode, version,
                       bootup, files, growmode_output, shutdown)

    @contextlib.contextmanager
    def assertImageNotAltered(self, image):
        """Context manager which asserts that the image file is not altered
        during the context."""
        def filehash(filespec):
            """Return the SHA256 hash of filespecs' contents."""
            with open(filespec, "rb") as file:
                return hashlib.sha256(file.read())

        before_hash = filehash(image)
        yield
        after_hash = filehash(image)
        self.assertEqual(before_hash.hexdigest(), after_hash.hexdigest())

    def assertOnlyUserReadable(self, filespec):
        """Assert that only the owner of a file can access it."""
        self.assertEqual(os.stat(filespec).st_mode & 0o077, 0)

if __name__ == "__main__":
    unittest.main(failfast=True)
