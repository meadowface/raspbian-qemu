Raspbian QEMU Tool
==================
[//]: # (https://github.com/meadowface/raspbian-qemu)

Handy Linux tool for non-privileged manipulation and [qemu-emulation](http://qemu.org) of [Raspbian](http://raspbian.org/) images. Easily manipulate Raspbian SD card images, compile an emulation kernel from source, and run them in emulation.

Quick Start
-----------
The below will work for many Debian-based systems.  Tested with **Ubuntu 16.04**, **Debian stretch (mid-2016)**, and **Debian sid (mid-2016)**.  **Debian jessie** requires [more effort to get the cross-compiler installed](README-jessie.md).

```
# Install cross-compiler. This only needs to be done once.
# See above if you are running Debian jessie.
$ sudo apt install gcc-arm-linux-gnueabihf

# Install other requirements, this only needs to be done once.
$ sudo apt install python3 patch make gcc bc parted e2fsprogs qemu-system-arm git

# Build a kernel binary.
$ git clone --depth=1 https://github.com/raspberrypi/linux.git
$ ./raspbian-qemu build-kernel linux

# Grab a Raspbian Lite image (or use one you've already downloaded).
# (The command below requires wget and funzip which are likely already on your system)
$ wget -qO- https://downloads.raspberrypi.org/raspbian_lite_latest | funzip >raspbian-jessie-lite.img

# Prep and run work.img.
$ ./raspbian-qemu prep raspbian-jessie-lite.img work.img
$ ./raspbian-qemu run --with-ssh-port=8022 work.img

# Use ansible, puppet, chef, or whatever to install and configure whatever
# software is needed, run tests, etc...

# After the emulated Raspbian boots, log in on the console in the terminal
# or `ssh -p 8022 pi@127.0.0.1`. To end emulation login into Raspbian and reboot it.

# Unprep the image and burn it to an SD card for deployment to actual hardware.
$ ./raspbian-qemu unprep work.img
$ sudo dd if=work.img of=/dev/mmcblk0 bs=4M
```

Requirements
------------
This tool uses a lot of other utilities to get things done.  All are packaged
in modern distributions, many are likely already installed on your system.

1. [python >= 3.3](https://www.python.org/)
1. [GNU patch](https://www.gnu.org/software/patch/) (for build-kernel)
1. [GNU make](https://www.gnu.org/software/make/) (for build-kernel)
1. [gcc and gcc/ARM hard-float cross-compiler](https://gcc.gnu.org/) (for build-kernel) ([not fully packaged on Debian jessie](README-jessie.md))
1. [GNU bc](http://ftp.gnu.org/gnu/bc/) (for build-kernel)
1. [GNU parted](https://www.gnu.org/software/parted/)
1. `resize2fs`, `e2fsck`, and `debugfs` from [e2fsprogs](http://e2fsprogs.sourceforge.net/)
1. `qemu-system-arm` from [QEMU](http://www.qemu.org)
1. [git](https://git-scm.com/) (not used by the tool but needed to get kernel source)

On a Debian-based systems (including Ubuntu), you can install the requirements
with:
```
$ sudo apt install gcc-arm-linux-gnueabihf    # see above for Debian jessie.
$ sudo apt install python3 patch make gcc bc parted e2fsprogs qemu-system-arm git
```

Installation
------------
1. Make sure all of the requirements are installed.  The script will let you know if a requirement is missing when it's run.
1. Place the file [raspbian-qemu](raspbian-qemu) somewhere.  Either put it in your path or use `./raspbian-qemu` to run it.

Usage
-----
1. Build a kernel.  *You only need to do this once.*  On a modern laptop (mid-2016) it takes about 3 minutes to compile.  This places a kernel image into the file `kernel-qemu` in the current directory.  Errors here are most likely caused by missing requirements (See above).

   > NOTE: The build-kernel action will clean the build directory every time
   > it is run.  So this isn't the best way to do kernel development.

   ```
   $ git clone --depth=1 https://github.com/raspberrypi/linux.git
   $ ./raspbian-qemu build-kernel linux
   ```
   > NOTE: If you already have a qemu-compatible kernel binary you want to
   > use, skip the above and copy it to `kernel-qemu` in the current directory.

1. Download and unzip an image from https://www.raspberrypi.org/downloads/raspbian/ .  Both the full version and the lite version work with this tool.
1. Prep the image (your image file might have a date-time-stamp at the beginning of the name, that changes over time, not including it below.)

   ```
   $ ./raspbian-qemu prep raspbian-jessie-lite.img work.img
   ```
1. Run the image in QEMU.  This will direct the Raspberry Pi console to the current terminal.  To end emulation login into Raspbian and reboot it.  Although not as clean, you can also quit QEMU from the monitor at any time.  To do this press **Ctrl-a**, then **'c'** to enter the monitor, then type **'quit'** and press **Enter**.

   ```
   $ ./raspbian-qemu run work.img
   ```

   > NOTE about the emulation: `qemu-system-arm` is being used to emulate the
   > `versatilepb` machine which is **limited to 256MB of RAM** even in
   > emulation. This is currently (mid-2016) the most stable and widely-
   > available emulation, utilizing QEMU v2.5.0. The QEMU project has recently
   > released v2.6.0 and v2.7.0rc1 which have initial support for a `raspi2`
   > machine type.  In experiments, that is not yet stable enough. As that
   > progresses this tool might be updated to have a mode that uses that as
   > well. See the links below in the References section for more information
   > on the new `raspi2` machine type in QEMU.
   > The current configuration of QEMU used by this tool is aimed to be
   > the most stable and widely available.


1. Make any changes to the system you want, all will persist within the image.  You can configure ssh (see below) and then use configuration management tools such as [ansible](https://www.ansible.com/) or [puppet](https://puppet.com/) to automatically configure the system.
1. If you then want to burn the image into an SD card and run it in actual Raspberry Pi hardware, first `unprep` the image.

   ```
   $ ./raspbian-qemu unprep work.img
   ```

Advanced Usage
--------------
### Grow the root partition

Raspbian images contain a minimal root partition, which can be expanded to fill the physical media once the image is burned and booted.  Since the image *is* the physical media for emulation, use `--grow-root=value` with `prep` to add `value` bytes to the image and expand the root partition to that size. `value` without an suffixes is interpreted as bytes, but you can add a `K`, `M`, and `G` for kibibytes, mibibytes, and gibibytes respectively. `unprep` will not re-shrink the root partition.

For example:
```
# Add one million bytes to the image/root partition.
$ ./raspbian-qemu prep --grow-root=1000000 work.img

# Add 500 mibibytes.
$ ./raspbian-qemu prep --grow-root=500M work.img

# Suffix is case-insensitive, add 1 gibibyte.
$ ./raspbian-qemu prep --grow-root=1g work.img
```

### Add ssh public key

This tool is not a configuration management tool but rather an enabler for
using such tools with Raspbian images.  Therefore it is handy to be able to
seed the image with an ssh authorized_key to be able to ssh in securely
without a password.  To do this use the `--add-public-key` with prep.  Multiple keys may be added to the image.  These keys are not removed when the `unprep` command is run.  The authorized key is added to the default `pi` user.  Any public keys added will remain and not be removed during `unprep`.

For example:
```
# Add the usual default public key to the image.
$ ./raspbian-qemu prep --add-public-key=~/.ssh/id_rsa.pub work.img

# Add another public key to the image.  The previous one added will still be there.
$ ./raspbian-qemu prep --add-public-key=~/.ssh/cloudaccount.pub work.img
```

### Set the host keys

Normally, host keys are generated by Raspbian on first-boot in a self-
destructing init script.  Similar to `--add-public-key`, it's handy to be able
to carry over host keys from a previous incarnation of a Raspbian image to set
the system up for configuration management.  To do this use the `extract` action to extract the host keys from an existing image to a tar file, and then use `--set-host-keys` with the `prep` action to put them in a new image.  The host keys are not removed when `unprep` is run on an image.

**NOTE: Host keys include *private keys* and should be treated with care.  The `extract` action makes sure to create a file that only the current user can read, but you should still take care not to unwittingly expose the private keys.  The same goes for an image that already has host keys set.**

To transfer host keys from one image to another:
```
# Given a prepped and booted image named version1.img, transfer the keys to version2.img with:
$ ./raspbian-qemu extract version1.img hostkeys keys.tar
$ ./raspbian-qemu prep --set-host-keys=keys.tar version2.img
```

If you'd like to create new host keys without booting first, then you can use the included [make-host-keys](make-host-keys) script.  It is not part of the main tool because it is just an example of how to create a tar file with proper permissions and really configuration management systems are a better way to manage host keys.
```
$ ./make-host-keys newkeys.tar
$ ./raspbian-qemu prep --set-host-keys=newkeys.tar work.img
```

### Run with a graphical display and/or audio

The default is to run headless without any audio or graphical windows. But if you'd like a graphical display or audio, add the switches `--with-display` or `--with-audio` respectively.  For example:

```
$ ./raspbian-qemu run --with-display --with-audio work.img
```

Will cause QEMU to open another window for a graphical display.  The console is still redirected to the serial port, so the bootup will still be in the terminal, while a lone graphical raspberry sit in the upper left of the graphics window until a desktop is loaded or a login prompt appears.

The above command will also not disable audio and use whatever QEMU is set up to use as a default audio driver.

Testing
-------
A full `unittest`-based test-suite is included in the [tests](tests) directory.

Problem & Principles
--------------------
> I want an easy and automated method for running Raspbian images in QEMU
> without requiring root or trusting un-vetted binaries.

There are many tutorials out there (some linked [below](#user-content-similar-projects--inspirations)) but they almost all require
many manual steps and root permissions to manipulate the images.
None of them include all of the best-of-breed steps.
Many of them link to a pre-compiled kernel as well without showing how to build from source.

Below are the (arbitrary) principles applied to this tool:

* **No privileges required** for image manipulation or emulating.
* **Full system emulation.**  Not just running an arm executable in a glorified chroot, but having the Raspbian system boot up as normally as possible.
* **Standalone** script.
* Usable for **build automation.**  No unavoidable prompts.
* No downloading of kernel binaries from un-vetted sources.
* Ability to round-trip image to an SD card for use on actual Raspberry Pi hardware.
* **Headless support** so it can be deployed in the cloud.

Similar Projects & Inspirations
-------------------------------

* The start of automation [here](https://github.com/dhruvvyas90/qemu-rpi-kernel/blob/master/tools/build-kernel-qemu) is what inspired fully automating the procedure. The [related post](http://dhruvvyas.com/blog/?p=49) is the by far best set of instructions I found among [many](https://www.unixmen.com/emulating-raspbian-using-qemu/) [other](http://sentryytech.blogspot.com/2013/02/faster-compiling-on-emulated-raspberry.html) [good](http://theo.cc/blog/2015/10/14/Build-Raspberry-Pi-Linux-Kernel-for-QEMU/) ones.
* [This set of instructions](https://gist.github.com/stefanozanella/4608873) for running various raspi things in `qemu-system-arm` is what finally made it click in my head that the kernel parameter `panic` and the qemu parameter `-no-reboot` could work together.
* Some interesting run-Raspberry-Pi-code-in-Docker|chroot|container projects. This is an intriguing idea for things like build farms and maybe some testing, but doesn't work directly with the SD card images or boot the system similarly enough to actual hardware.  So I didn't dig too deeply.
  * http://www.instructables.com/id/Uniform-Development-by-Docker-QEMU/?ALLSTEPS
  * http://blog.hypriot.com/post/heavily-armed-after-major-upgrade-raspberry-pi-with-docker-1-dot-5-0/
  * https://github.com/resin-io-library/resin-rpi-raspbian
  * https://lionfacelemonface.wordpress.com/2015/04/18/raspberry-pi-build-environment-in-no-time-at-all/
  * https://resin.io/blog/building-arm-containers-on-any-x86-machine-even-dockerhub/
* If just compiling something with no other release engineering is your goal, then this [Raspbian pbuilderrc](https://github.com/openBergisch/raspbian-pbuilder-draft) is worth looking at.

References
----------

* [Discussion](https://bugs.launchpad.net/ubuntu/+source/rootstock/+bug/570588) of the 256M memory limit for the `versatilepb` machine in QEMU.  A [suggestion to add swap](https://www.raspberrypi.org/forums/viewtopic.php?f=53&t=8649) to help mitigate it.
* Raspberry Pi [kernel source](https://github.com/raspberrypi/linux)
* Official [Raspberry Pi Kernel Build documentation](https://www.raspberrypi.org/documentation/linux/kernel/building.md).
* [How to figure out the kernel git commit](http://lostindetails.com/blog/post/Compiling-a-kernel-module-for-the-raspberry-pi-2) from a system binary.  Generally a nice source for information on compiling Raspberry Pi kernels.
* Feb 2016 `raspi2` machine in QEMU status from the [QEMU mailing list](http://lists.nongnu.org/archive/html/qemu-devel/2016-02/msg05684.html) and [Raspberry Pi forums](https://www.raspberrypi.org/forums/viewtopic.php?f=72&t=26561&start=125).
* What looks like the [initial QEMU raspi2 machine work](https://github.com/0xabu/qemu).
* [Some wrapping](https://github.com/simonpoole1/raspbian-live-build) around using the `raspi2` machine in QEMU.  The [qemu-run](https://github.com/simonpoole1/raspbian-live-build/blob/master/qemu-run) in particular script has a lot of very specific kernel hardware args.
* Reference for [setting audio driver](https://wiki.archlinux.org/index.php/PulseAudio#QEMU) in QEMU.
* [Good explanation](https://kashyapc.com/2016/02/11/qemu-command-line-behavior-of-serial-stdio-vs-serial-monstdio/) of `-serial mon:stdio` in QEMU.
* Using the [QEMU Monitor](https://en.wikibooks.org/wiki/QEMU/Monitor).
* The Arch Linux wiki has a [great page on QEMU](https://wiki.archlinux.org/index.php/QEMU).

License
-------
Distributed under the terms of the MIT License, see [LICENSE](LICENSE) file for details.

Future Thoughts
---------------
These are thoughts for later.  They may or may not be implemented.

* `--with-http[s]` or a more generic `--with-port-redir` switch.
* Injecting a `config.txt` into the first partition.  It's not used at all during emulation but would be handy for prepping images for runs on actual hardware. Note that this could be done with a configuration management tool since the emulated system mounts the boot partition.
* Store kernel in a `~/.raspbian-qemu` directory.
* `--noclean` switch for `build-kernel`.
* Use `-` for stdin in `image`, `--add-public-key`, and `--set-host-keys`
* A switch for `run` which would add `-net dump` to the emulation command to packet dump the network traffic. (http://blog.vmsplice.net/2011/04/how-to-capture-vm-network-traffic-using.html)