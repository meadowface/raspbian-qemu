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

# Arguments to python or coverage to discover and run tests.
DISCOVER_TESTS=-m unittest discover --failfast

# Arguments to python or coverage to run the test that builds a kernel.
BUILD_KERNEL_TEST=test_tool.py TestBuildKernel.test_build_kernel

# Run the coverage tool. Make sure to not litter this directory with
# a __pycache__.
COVERAGE_TOOL=PYTHONDONTWRITEBYTECODE=1 python3-coverage

all: kernel-qemu test.img.gz test-host-keys.tar
	PYTHONDONTWRITEBYTECODE=1 python3 $(DISCOVER_TESTS)

linux:
	git clone --depth=1 https://github.com/raspberrypi/linux.git

test-linux: linux
	 ln -s linux $@

kernel-qemu: test-linux
	python3 $(BUILD_KERNEL_TEST)

test.img.gz: make-test-image
	./make-test-image

test-host-keys.tar: make-test-host-keys
	./make-test-host-keys

# Report on test coverage.  This doesn't run all since all is designed to not
# have to rebuild the kernel every time.  This will.
coverage: test-linux test.img.gz test-host-keys.tar clean
	$(COVERAGE_TOOL) run --parallel-mode $(BUILD_KERNEL_TEST)
	$(COVERAGE_TOOL) run --parallel-mode $(DISCOVER_TESTS)
	$(COVERAGE_TOOL) combine
	$(COVERAGE_TOOL) html
	@echo "Results in htmlconv/index.html"

clean:
	# Clean out any potential coverage files.
	rm -rf .coverage* htmlcov
	# Clean out any cached files from test_source.
	rm -rf .cache/urls
	# Make sure the kernel and patch need to be built/fetched.
	rm -f kernel-qemu linux/raspbian-qemu-linux-arm.patch

dist-clean: clean
	rm -rf linux test-linux busybox.deb .cache
