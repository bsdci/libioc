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
"""Class extension to queue commands for bulk executions."""
import typing


class CommandQueue:
    """Class extension that queues command for bulk execution."""

    command_queues: typing.Dict[str, typing.List[str]]

    def clear_command_queue(self) -> None:
        """Clear the command queue."""
        command_queues: typing.Dict[str, typing.List[str]] = {}
        self.command_queues = command_queues

    def _clear_queue(self, queue_name: str) -> None:
        """Empty a specific queue."""
        self.command_queues[queue_name] = []

    def get_command_queue(self, queue_name: str="default") -> typing.List[str]:
        """Create or return the queue with the given name."""
        if queue_name not in self.command_queues.keys():
            self._clear_queue(queue_name)
        return self.command_queues[queue_name]

    def append_command_queue(
        self,
        *commands: str,
        queue_name: str="default"
    ) -> None:
        """Append commands to the queue with the selected name."""
        if queue_name not in self.command_queues.keys():
            self._clear_queue(queue_name)
        self.command_queues[queue_name] += commands

    def read_commands(self, queue_name: str="default") -> typing.List[str]:
        """Return the collected jail commands and clear the queue."""
        queue = self.get_command_queue(queue_name)
        self._clear_queue(queue_name)
        return queue
