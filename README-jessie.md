Installing an arm-linux-gnueabihf cross-compiler on Debian jessie
=================================================================
[//]: # (https://github.com/meadowface/raspbian-qemu)

Why
---
Debian jessie was released before the full maturation of the cross-compiler packages in Debian-based systems.  But there is enough there that building your own is easy and takes about 15-30min on a modern (mid-2016) machine.

>NOTE: If you are using a release newer than jessie you do not need to do the below, simply install the package `gcc-arm-linux-gnueabihf`.

How
---
These instructions are derived and simplified from the debian wiki page: https://wiki.debian.org/CrossCompiling#Building_your_own_cross-toolchain

1. Add the `armhf` architecture to the system and install build-dependencies.

    ```
    $ sudo dpkg --add-architecture armhf
    $ sudo apt update
    $ sudo apt install cross-gcc-dev debhelper gcc-4.9-source libc6-dev:armhf linux-libc-dev:armhf libgcc1:armhf binutils-arm-linux-gnueabihf bison flex libtool gdb sharutils netbase libcloog-isl-dev libmpc-dev libmpfr-dev libgmp-dev systemtap-sdt-dev autogen expect chrpath zlib1g-dev zip build-essential dpkg-dev lsb-release
   ```
1. Use the `cross-gcc-dev` tools to generate a source directory for the cross-compiler and then build it.  The `dpkg-buildpackage` command takes awhile.

    ```
    $ TARGET_LIST="armhf" cross-gcc-gensource 4.9
    $ cd cross-gcc-packages-amd64/cross-gcc-4.9-armhf
    $ time dpkg-buildpackage
    ```
1. Install just the C preprocessor and the C compiler, we don't need C++ or Fortran for the kernel.  Then install any dependencies they might need.  It's usual for the first command to show some errors.

    ```
    $ sudo dpkg -i gcc-4.9-arm-linux-gnueabihf_4.9.2-10_amd64.deb cpp-4.9-arm-linux-gnueabihf_4.9.2-10_amd64.deb
    $ sudo apt install -f
    ```
1. Newer releases than jessie have a "symlink package" (`gcc-arm-linux-ggnueabihf`), for jessie we'll make the one symlink we need to compile the kernel.

    ```
    $ sudo ln -s arm-linux-gnueabihf-gcc-4.9 /usr/bin/arm-linux-gnueabihf-gcc
    ```
