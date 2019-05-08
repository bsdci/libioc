# Copyright (c) 2017-2019, Stefan Grönke
# Copyright (c) 2014-2018, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Collection of ioc Python decorators."""
import functools
import time

import libioc.helpers


def json(fn):
    """Return the functions output as JSON string."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):  # noqa: T484
        return libioc.helpers.to_json(fn(*args, **kwargs))
    return wrapped


def timeit(fn):
    """Measure and print the functions execution time."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):  # noqa: T484
        startTime = time.time()
        try:
            output = fn(*args, **kwargs)
            error = None
        except Exception as err:
            error = err
        elapsedTime = (time.time() - startTime) * 1000
        print(f"function [{fn.__qualname__}] finished in {elapsedTime} ms")
        if error is not None:
            raise error
        return output
    return wrapped
