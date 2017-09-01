# Copyright (c) 2014-2017, iocage
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
from timeit import default_timer as timer
import libiocage.lib.errors

EVENT_STATUS = (
    "pending",
    "done",
    "failed"
)


class IocageEvent:
    """
    IocageEvent

    Base class for all other iocage events
    """

    HISTORY = []

    PENDING_COUNT = 0

    def __init__(self, message=None, **kwargs):
        """
        Initializes an IocageEvent
        """

        for event in IocageEvent.HISTORY:
            if event.__hash__() == self.__hash__():
                return event

        self.identifier = None
        self._started_at = None
        self._stopped_at = None
        self._pending = False
        self.skipped = False
        self.done = True
        self.error = None

        self.data = kwargs
        self.number = len(IocageEvent.HISTORY) + 1
        self.parent_count = IocageEvent.PENDING_COUNT

        self.message = message

        if self not in IocageEvent.HISTORY:
            IocageEvent.HISTORY.append(self)

    @property
    def state(self):
        return self.get_state()

    def get_state_string(self,
                         error="failed",
                         skipped="skipped",
                         done="done",
                         pending="pending"):

        if self.error is not None:
            return error

        if self.skipped is True:
            return skipped

        if self.done is True:
            return done

        return pending

    @property
    def type(self):
        """
        The type of event

        The event type is obtained from an IocageEvent's class name
        """
        return type(self).__name__

    @property
    def pending(self):
        return self._pending

    @pending.setter
    def pending(self, state):
        current = self._pending
        new_state = (state is True)

        if current == new_state:
            return

        if new_state is True:
            if self._started_at is not None:
                raise libiocage.lib.errors.EventAlreadyFinished(event=self)
            self._started_at = timer()
        if new_state is False:
            self._stopped_at = timer()

        self._pending = new_state
        IocageEvent.PENDING_COUNT += 1 if (state is True) else -1

    @property
    def duration(self):
        if (self._started_at is None) or (self._stopped_at is None):
            return None
        return self._stopped_at - self._started_at

    def _update_message(self, **kwargs):
        if "message" in kwargs:
            self.message = kwargs["message"]

    def begin(self, **kwargs):
        self._update_message(**kwargs)
        self.pending = True
        self.done = False
        self.parent_count = IocageEvent.PENDING_COUNT - 1
        return self

    def end(self, **kwargs):
        self._update_message(**kwargs)
        self.done = True
        self.pending = False
        self.done = True
        self.parent_count = IocageEvent.PENDING_COUNT
        return self

    def step(self, **kwargs):
        self._update_message(**kwargs)
        self.parent_count = IocageEvent.PENDING_COUNT
        return self

    def skip(self, **kwargs):
        self._update_message(**kwargs)
        self.skipped = True
        self.pending = False
        self.parent_count = IocageEvent.PENDING_COUNT
        return self

    def fail(self, exception=True, **kwargs):
        self._update_message(**kwargs)
        self.error = exception
        self.pending = False
        self.parent_count = IocageEvent.PENDING_COUNT
        return self

    def __hash__(self):
        identifier = "generic" if self.identifier is None else self.identifier
        return hash((self.type, identifier))


# Jail


class JailEvent(IocageEvent):

    def __init__(self, jail, **kwargs):
        try:
            self.identifier = jail.humanreadable_name
        except:
            self.identifier = None

        IocageEvent.__init__(self, jail=jail, **kwargs)


class JailLaunch(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)


class JailVnetConfiguration(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)


class JailZfsShareMount(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)


class JailServicesStart(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)


class JailDestroy(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)


class JailNetworkTeardown(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)


class JailMountTeardown(JailEvent):

    def __init__(self, jail, **kwargs):
        JailEvent.__init__(self, jail, **kwargs)

# Release


class ReleaseEvent(IocageEvent):

    def __init__(self, release, **kwargs):
        try:
            self.identifier = release.name
        except:
            self.identifier = None

        IocageEvent.__init__(self, release=release, **kwargs)


class FetchRelease(ReleaseEvent):

    def __init__(self, release, **kwargs):
        ReleaseEvent.__init__(self, release, **kwargs)


class ReleasePrepareStorage(FetchRelease):

    def __init__(self, release, **kwargs):
        FetchRelease.__init__(self, release, **kwargs)


class ReleaseDownload(FetchRelease):

    def __init__(self, release, **kwargs):
        FetchRelease.__init__(self, release, **kwargs)


class ReleaseExtraction(FetchRelease):

    def __init__(self, release, **kwargs):
        FetchRelease.__init__(self, release, **kwargs)


class ReleaseCopyBase(FetchRelease):

    def __init__(self, release, **kwargs):
        FetchRelease.__init__(self, release, **kwargs)


class ReleaseConfiguration(FetchRelease):

    def __init__(self, release, **kwargs):
        FetchRelease.__init__(self, release, **kwargs)


class ReleaseUpdate(ReleaseEvent):

    def __init__(self, release, **kwargs):
        ReleaseEvent.__init__(self, release, **kwargs)


class ReleaseUpdateDownload(ReleaseEvent):

    def __init__(self, release, **kwargs):
        ReleaseUpdate.__init__(self, release, **kwargs)


class RunReleaseUpdate(ReleaseUpdate):

    def __init__(self, release, **kwargs):
        ReleaseUpdate.__init__(self, release, **kwargs)


class ExecuteReleaseUpdate(ReleaseUpdate):

    def __init__(self, release, **kwargs):
        ReleaseUpdate.__init__(self, release, **kwargs)
