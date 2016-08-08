Raspbian QEMU Tool Tests
========================
[//]: # (Home: https://github.com/meadowface/raspbian-qemu/tests)

A full `unittest`-based test-suite for raspbian-qemu.

Runing the Tests
----------------
No additional tools are needed to be able to run the test suite as:
```
$ cd tests
$ make
```

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
* `ssh-keygen` from [OpenSSH](http://www.openssh.com/) which is likely already installed.

On Debian-based systems you can install these additional requirements with:
```
$ sudo apt install fakeroot openssh-client
```
