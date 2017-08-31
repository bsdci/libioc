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


class BridgeSet(set):
    def __init__(self, jail_config=None):
        self.jail_config = jail_config
        set.__init__(self)

    def add(self, value, notify=True):
        set.add(self, value)
        if notify:
            try:
                self.jail_config.update_special_property("interfaces")
            except:
                pass

    def remove(self, value, notify=True):
        set.remove(self, value)
        if notify:
            try:
                self.jail_config.update_special_property("interfaces")
            except:
                pass


class JailConfigInterfaces(dict):
    def __init__(self, value, jail_config=None, property_name="interfaces"):
        dict.__init__(self, {})
        dict.__setattr__(self, 'jail_config', jail_config)
        dict.__setattr__(self, 'property_name', property_name)
        self.read(value)

    def read(self, value):
        nic_pairs = value.replace(",", " ").split(" ")
        for nic_pair in nic_pairs:
            jail_if, bridge_if = nic_pair.split(":", maxsplit=1)
            self.add(jail_if, bridge_if, notify=False)

    def add(self, jail_if, bridges=None, notify=True):

        if bridges is None or bridges == [] or bridges == "":
            return

        if isinstance(bridges, str):
            bridges = [bridges]

        try:
            prop = dict.__getitem__(self, jail_if)
        except:
            prop = self.__empty_prop(jail_if)

        for bridge_if in bridges:
            prop.add(bridge_if, notify=False)

        if notify:
            self.__notify()

    def __setitem__(self, key, values):

        try:
            dict.__delitem__(self, key)
        except:
            pass

        self.add(key, values)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self):
        try:
            self.jail_config.update_special_property(self.property_name)
        except:
            pass

    def __empty_prop(self, key):

        prop = BridgeSet(self.jail_config)
        dict.__setitem__(self, key, prop)
        return prop

    def __str__(self):
        out = []
        for jail_if in self:
            for bridge_if in self[jail_if]:
                out.append(f"{jail_if}:{bridge_if}")
        return " ".join(out)
