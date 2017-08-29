EVENT_STATUS = (
    "pending",
    "done",
    "failed"
)


class Iocage:
    """
    IocageEvent

    Base class for all other iocage events
    """

    def __init__(self, action, **kwargs):
        self.action = action
        self.data = kwargs


class Jail(Iocage):

    def __init__(self, action, jail, **kwargs):
        super().__init__(action=action, jail=jail, **kwargs)


class JailStarted(Jail):

    def __init__(self, jail, **kwargs):
        super().__init__("Started", jail, **kwargs)


class JailVnetConfigured(Jail):

    def __init__(self, jail, **kwargs):
        super().__init__("Configuring VNET", jail, **kwargs)


class JailZfsShareMounted(Jail):

    def __init__(self, jail, **kwargs):
        super().__init__("Mounting ZFS shares", jail, **kwargs)


class JailServicesStarted(Jail):

    def __init__(self, jail, **kwargs):
        super().__init__("Starting services", jail, **kwargs)
