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
    test_source - Test consistency in the source code and documentation.
"""

import contextlib
import fnmatch
import hashlib
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
import urllib.robotparser


# Prevent next imports from creating __pycache__ directory
sys.dont_write_bytecode = True

def sources(pattern="*"):
    """Generator which yields the filename and contents (as bytes) of each
    source file in the current git repository."""
    git_files = subprocess.check_output(["git", "ls-files", ".."])
    for filename in git_files.decode().splitlines():
        if fnmatch.fnmatch(filename, pattern):
            with open(filename, "rb") as file:
                yield filename, file.read()

class LinkValidator:
    """Class which will validate URLs, while caching the checks for a day.
    robots.txt for each domain is checked and obeyed.
    """
    ROBOTS_DENIED = "Check defeated by domain's robots.txt"
    def __init__(self, cachepath=".cache/urls"):
        self.cachepath = cachepath
        if not os.path.isdir(self.cachepath):
            os.makedirs(self.cachepath)
        self.sites = {}

    def robots_allowed(self, url):
        """Return True if the site at url allows crawling of that url."""
        parts = urllib.parse.urlparse(url)
        site = parts.scheme + "://" + parts.netloc
        if site in self.sites:
            robotparser = self.sites[site]
        else:
            robotparser = urllib.robotparser.RobotFileParser()
            robotparser.set_url(urllib.parse.urljoin(site, "robots.txt"))
            robotparser.read()
            self.sites[site] = robotparser

        return self.sites[site].can_fetch("*", url)

    def check_cache(self, url):
        """Return a tuple of:
            urlcachepath - the path to the cached result file
            urlok        - if the cache shows that the URL is valid.
        """
        urlhash = hashlib.sha256(url.encode()).hexdigest()
        urlcachepath = os.path.join(self.cachepath, urlhash)
        try:
            cachetime = os.path.getctime(urlcachepath)
            if time.time() - cachetime < 24*60*60:
                return urlcachepath, True
        except FileNotFoundError:
            pass
        return urlcachepath, False

    def validate(self, url):
        """Validate the url, using the cache and return either an empty string
        if the URL is valid or an error string as to why it's invalid."""
        urlcachepath, ok = self.check_cache(url)
        if ok:
            return ""
        else:
            parts = urllib.parse.urlparse(url)
            if self.robots_allowed(url):
                req = urllib.request.Request(url=url, method="HEAD")
                req.headers["User-Agent"] = "python/" + __file__
                req.headers["Accept"] = "*/*"
                try:
                    with urllib.request.urlopen(req) as f:
                        if f.status == 200:
                            with open(urlcachepath, "w") as cachefile:
                                cachefile.write("\n".join([url,
                                                           str(f.status)]))
                            return ""
                except urllib.error.HTTPError as e:
                    return str(e)
            else:
                return self.ROBOTS_DENIED

def unique_urls_in_sources():
    """Return a set of URLs extracted from the sources."""
    # Use a very simple loose match for an accurate count of links and then
    # a tight match to get the full URLs.  Comparing these guards against the
    # tighter regex missing URLs.
    #
    # NOTE: This match is *extremely specific* to this repository.  This is
    #       not a general URL extractor.  We control the horizontal and the
    #       vertical, so we can make assumptions and assertions about the
    #       results that don't apply generally.
    loose_matches = 0
    tight_matches = 0
    urls = set()
    for filename, contents in sources():
        # Ignore mentions in this file.
        if filename == __file__:
            continue
        # Ignore binary files.
        if filename.endswith((".gz", ".tar")):
            continue

        loose_matches += len(re.findall(r'https?:', contents.decode()))
        for prefix, url, suffix in re.findall(r'([\(]??)(https?://.+?)([\s\)"])',
                                              contents.decode()):
            # Trailing periods are sentence periods, so remove them.
            # NOTE: This is an assertion specific to this repository.
            if url.endswith("."):
                url = url[:-1]
            urls.add(url)

            # Some URLs can contain others, each tight match might contain
            # more than one loose match.
            tight_matches += url.count("http")

    assert loose_matches == tight_matches, "URL regex problem."

    return urls

def unique_markdown_links():
    """Return a set of internal markdown link targets from the sources."""
    targets = set()
    for filename, contents in sources():
        # Ignore binary files.
        if not filename.endswith(".md"):
            continue

        basepath = os.path.dirname(filename)
        for anchor_text, target in re.findall(r'\[(.*?)\]\((.*?)\)',
                                              contents.decode()):
            if not target.startswith("http"):
                if target.startswith("#"):
                    targets.add(filename)
                else:
                    targets.add(os.path.join(basepath, target))

    return targets

class TestSource(unittest.TestCase):
    def test_internal_links(self):
        links = unique_markdown_links()
        for target in links:
            try:
                self.assertEqual(True, os.path.exists(target))
            except Exception as e:
                raise AssertionError("Markdown link error:"
                                     " %r does not exist" % (target,)) from e

    def test_external_links(self):
        invalid = {}
        validator = LinkValidator()
        for url in unique_urls_in_sources():
            error = validator.validate(url)
            if error:
                invalid[url] = error

        for url, response in sorted(invalid.items()):
            try:
                self.assertEqual(response, validator.ROBOTS_DENIED)
            except Exception as e:
                raise AssertionError("External link error:"
                                     " %r -> %r" % (url, response,)) from e

    def test_licenses(self):
        def first_chunk(text, *, delimiter="\n\n"):
            """Return the first chunk of a file before the delimiter which
            defaults to a single empty line."""
            return text.split(delimiter)[0]

        def collapse_whitespace(text):
            """Collapse all whitespace in text down to a single space."""
            return " ".join(text.split())

        # Grab the overall license out of the LICENSE file.  By convention
        # the overall license is everything before two empty lines.
        with open("../LICENSE") as licensefile:
            license = collapse_whitespace(first_chunk(licensefile.read(),
                                                      delimiter="\n\n\n"))

        # For every code source file, check to see that the overall license
        # is included as a comment blob at the top of the file.
        for filename, contents in sources():
            # Ignore non-code files.
            if filename.endswith((".gz", ".tar", ".md", "LICENSE")):
                continue

            try:
                # Get the first chunk before a blank line.  Remove a shebang
                # line if present, then strip off all of the comment prefixes,
                # and finally collapse all whitespace for easy comparison
                # against the

                # Some URLs can contain others, each tight match license extracted above. might contain
                # more than one loose match.
                initial_comment_block = first_chunk(contents.decode())
                initial_comment_block = re.sub(r'^#!.*?$', "", initial_comment_block,
                                               count=1,
                                               flags=re.MULTILINE)
                initial_comment_block = re.sub(r'^#', "", initial_comment_block,
                                               flags=re.MULTILINE)
                file_license = collapse_whitespace(initial_comment_block)

                self.maxDiff = None
                self.assertEqual(file_license, license)
            except Exception as e:
                raise AssertionError("License error in file: " + filename) from e

if __name__ == "__main__":
    unittest.main(failfast=True)
