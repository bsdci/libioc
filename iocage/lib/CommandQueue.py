import typing


class CommandQueue:

    shell_variable_nic_name: str
    command_queue: typing.List[str]
    env_variables: typing.List[str]

    def clear(self) -> None:
        """Clear the command queue."""
        self.command_queue: typing.List[str] = []
        self.env_variables: typing.List[str]

    def merge_env(
        self,
        env_variables: typing.Dict[str, str]
    ) -> typing.Dict[str, str]:
        """Merge existing env variables with the newly set ones."""
        output: typing.Dict[str, str] = {}
        for key, value in env_variables.items():
            output[key] = value
        for key, value in self.env_variables.items():
            output[key] = value

    def read_commands(self) -> None:
        """Return the collected jail commands and clear the queue."""
        queue = self.command_queue
        self.command_queue = []
        return queue
