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
    xwrappers - Wrappers around Xvfb and xtrace for use in testing X
                applications headlessly under Linux.

    Includes:
        Display       - str subclass for containing DISPLAY values.
        saved_display - context manager to save and restore DISPLAY.
        xvfb          - context manager which sets up an Xvfb.
        xtrace        - context manager which sets up xtrace.

    NOTE: Not using xvfbwrapper (https://github.com/cgoldberg/xvfbwrapper)
          because we're trying out more modern methods of closing the races
          in knowing when the X servers are ready and not providing python 2.x
          support.  It is also a bit behind upstream in current (mid-2016)
          distributions.

"""

import contextlib
import io
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

class Display(str):
    """Convenient str derivative which holds an X-Windows DISPLAY value.
       Can instantiate with either a str or an int and can cast to int.
       Can use set()/get() to set/get it in the DISPLAY environment var.
    """
    DISPLAY = "DISPLAY"

    def __new__(cls, value):
        """Create a new Display, accepting strs or ints and validating that
        this value is either blank or matches: [method] ':' display."""
        if isinstance(value, str):
            method, colon, display = value.partition(":")
            if value and (colon != ":" or not display):
                raise ValueError("%r is not a valid DISPLAY value" % (value,))
            return super().__new__(cls, value)
        elif isinstance(value, int):
            return super().__new__(cls, ":%d" % (value,))

    def __int__(self):
        """Return the display number, regardless of connection method used."""
        return int(self.split(":")[-1])

    @classmethod
    def get(cls):
        """Return the value os DISPLAY in the environment, or None if it's
        missing."""
        value = os.environ.get(cls.DISPLAY)
        if value is None:
            return None
        else:
            return cls(value)

    def set(self):
        """Set the current value into the DISPLAY variable int he environment."""
        os.environ[self.DISPLAY] = self

@contextlib.contextmanager
def saved_display():
    """Context manager which saves and restores the DISPLAY environment
    variable within its context.  If DISPLAY is not part of the
    environment before the context it makes sure it isn't after.
    yields the old display value.
    """
    old_display = Display.get()
    try:
        yield old_display
    finally:
        if old_display is None:
            if Display.DISPLAY in os.environ:
                del os.environ[Display.DISPLAY]
        else:
            old_display.set()

def have_xvfb():
    """Returns True if Xvfb is installed and runnable."""
    try:
        subprocess.check_call(["Xvfb", "-help"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

@contextlib.contextmanager
def xvfb(options=("-screen", "0", "1024x768x24")):
    """Context manager to run things against a Xvfb instance.  Restoring the
    original X environment (if any) after context exit.
    """
    with saved_display():
        fd_read, fd_write = os.pipe()

        cmd = ["Xvfb",
               "-displayfd", str(fd_write),
              ] + list(options)

        with subprocess.Popen(cmd,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              pass_fds=[fd_write]) as xvfb:
            try:
                os.close(fd_write)
                with open(fd_read, "rb", buffering=0) as displayfile:
                    line = displayfile.readline()

                if xvfb.poll() is None:
                    display = Display(int(line))
                    display.set()
                    yield display
                else:
                    raise subprocess.CalledProcessError(xvfb.returncode, cmd)
            finally:
                xvfb.kill()

def linux_unix_domain_sockets(pid=None):
    """Return a list of all open unix domain sockets.  If pid is not None,
    then filter the list to only those owned by process pid.

    Works only under Linux as it requires /proc/net/unix.
    """
    def socket_map():
        """Return a mapping of inode: socket path for the unix domain
        sockets in the system."""
        with open("/proc/net/unix") as unix:
            return {inode: path.rstrip("\n") for inode, path in
                    [line.split(None, 7)[-2:] for line in unix]}

    if pid is None:
        result = socket_map().values()
    else:
        # The process can be opening and closing files as we're checking, so
        # retry a few times, always re-reading the directory listing and the
        # sockets maps if we run into a socket not being in the map or a
        # permissions error.
        #
        # If after 3 tries we're still getting problems, then return an empty
        # result to the caller, who is likely looking for a particular entry
        # and will call us again or error out.
        fdpath = "/proc/%d/fd" % (pid,)
        for attempt in range(3):
            try:
                result = []
                sockets = socket_map()
                for entry in os.listdir(fdpath):
                    try:
                        target = os.readlink(os.path.join(fdpath,entry))
                        socket, colon, inode = target.partition(":")
                        if socket == "socket":
                            result.append(sockets[inode.strip("[]")])
                    except FileNotFoundError:
                        # Allow for files disappearing between listdir()
                        # and the readlink().
                        pass
                break
            except (KeyError, PermissionError) as e:
                continue
        else:
            result = []
    return result

def have_xtrace():
    """Returns True if xtrace is installed and runnable."""
    try:
        subprocess.check_call(["xtrace", "--help"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

@contextlib.contextmanager
def xtrace(outfile):
    """
    Context manager which uses xtrace to set up a fake display and logs
    all x-traffic to the file named by outfile.  yields the fake Display.
    """
    with saved_display() as upstream_display:
        if not upstream_display:
            raise ValueError("No upstream display")

        for display in (Display(d) for d in range(64)):
            # xtrace itself is not polite, so be polite on its behalf and
            # don't run it if we have any clues that a server might be
            # listening on this display.  IF we don't check, and it's under
            # our user, xtrace will simply stomp over the endpoint.
            if display == upstream_display:
                continue

            uds = "/tmp/.X11-unix/X%d" % (int(display),)
            if uds in linux_unix_domain_sockets():
                continue

            # Since we don't think there's a server there, see if xtrace will
            # be able to run.
            cmd = ["xtrace",
                   "--display", upstream_display,
                   "--fakedisplay", display,
                   "--nocopyauthentication",
                   "--keeprunning",
                   "--outfile", outfile,
                  ]
            with subprocess.Popen(cmd,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL) as xtrace:
                try:
                    # Poll until either the process dies or until we can
                    # connect to the uds socket that is owned by the process
                    # we spawned.  Connecting to the socket without checking
                    # ownership could mean another process is listening on
                    # that socket.
                    while xtrace.poll() is None:
                        if uds in linux_unix_domain_sockets(xtrace.pid):
                            # Connecting to the fake display is the only
                            # way to ensure it's up and ready for business.
                            with socket.socket(socket.AF_UNIX,
                                               socket.SOCK_STREAM) as sock:
                                sock.connect(uds)
                            display.set()
                            yield display
                            break

                        # If the process hasn't died, sleep before we check
                        # for the socket again.
                        if xtrace.poll() is None:
                            time.sleep(0.01)
                    else:
                        # xtrace process died before it was ever ready, so
                        # continue the outer for loop to trace another
                        # display.
                        continue

                    # We happily found a display that worked and yielded, so
                    # break out of the outer for loop as we're done.
                    break
                finally:
                    xtrace.kill()
        else:
            raise Exception("No reasonable free display found.")
def test():
    """Module tests."""
    import doctest
    print(doctest.testmod())

if __name__ == "__main__":
    test()
