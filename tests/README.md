Raspbian QEMU Tool Tests
========================
[//]: # (https://github.com/meadowface/raspbian-qemu/tests)

A full `unittest`-based test-suite for `raspbian-qemu`.

Runing the Tests
----------------
No additional tools are needed to be able to run the test suite as:
```
$ cd tests
$ make
```

> If [Xvfb](https://en.wikipedia.org/wiki/Xvfb) and [xtrace](https://alioth.debian.org/projects/xtrace/) are both installed, then the code will test the `--with-display` switch to `run`, otherwise that test is skipped.

### Coverage
The [Makefile](Makefile) target `coverage` will use a system-wide version of [coverage.py](https://bitbucket.org/ned/coveragepy) to generate a coverage report in `tests/htmlcov/index.html`.  By default it assumes a system-wide installed coverage.py of at least v3.7.1 which is included in Debian >= jessie and and Ubuntu >= trusty as the package `python3-coverage`.  To change this, edit the `COVERAGE_TOOL` variable in the [Makefile](Makefile).

### Test Image

Most of the test suite does not use a full Raspbian image, but rather a minimal image created specifically for testing.  This image requires root privileges to create, and is small, so it is included in the repo as [test.img.gz](test.img.gz).  **Since it is included already you do not need to make it to run the test suite.** If you want to alter or re-create the image, use the included [make-test-image](make-test-image) script, which requires the following in addition to the requirements of the tool:

* [fakeroot](https://alioth.debian.org/projects/fakeroot/)
* [wget](https://www.gnu.org/software/wget/)

On Debian-based systems you can install these additional requirements with:
```
$ sudo apt install fakeroot wget
```

### Test host keys

Also included in the repo as [test-host-keys.tar](test-host-keys.tar) is a fun set of test "host keys" which are really just random data in the host key format.  **Since they are included already you do not need to make them to run the test suite.**  But if you want to produce similar keys, use the [make-test-host-keys](make-test-host-keys) script which requires the following in addition to the requirements of the tool:

* [fakeroot](https://alioth.debian.org/projects/fakeroot/)

On Debian-based systems you can install these additional requirements with:
```
$ sudo apt install fakeroot
```

> NOTE: The files produced by this tool **are not functional hostkeys**.  They are just random bytes made to look like host keys.  If you need functional host keys, see the [make-host-keys](../make-host-keys) script.