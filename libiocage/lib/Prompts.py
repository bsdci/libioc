import libiocage.lib.errors
import libiocage.lib.helpers


class Prompts:
    def __init__(self, host=None, logger=None):
        self.logger = logger
        libiocage.lib.helpers.init_host(self, host)

    def release(self):
        default = None
        available_releases = self.host.distribution.releases
        for i, available_release in enumerate(available_releases):
            if available_release.name == self.host.release_version:
                default = i
                print(
                    f"[{i}] \033[1m{available_release.annotated_name}\033[0m"
                )
            else:
                print(f"[{i}] {available_release.annotated_name}")

        if default is not None:
            default_release = available_releases[default]
            selection = input(
                # f"Release ({default_release.name}) [{default}]: "
                "\nType the number of the desired RELEASE\n"
                "Press [Enter] to fetch the default selection"
                f" ({default_release.name}) [{default}]: "
            )
        else:
            default_release = None
            selection = input("Your selection: ")

        if selection == "":
            if default_release is None:
                raise libiocage.lib.errors.DefaultReleaseNotFound(
                    host_release_name=self.host.release_version,
                    logger=self.logger
                )
            return default_release
        else:
            return available_releases[int(selection)]
