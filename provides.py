# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

import charmhelpers.core.hookenv as hookenv
import charms.reactive as reactive


class ManilaPluginProvides(reactive.RelationBase):
    """This is the subordinate end of the relation.  i.e. the configuration
    provider to the manila plugin.

    The purpose of the provides side of the interface is to provide the manila
    charm with configuration information to correctly link to whatever the
    plugin wants to do.  e.g. for a backend, to configure manila to use the
    appropriate backend.

    The manila charm provides the service user manila, and other authentication
    information that it can use to configure other services in the OpenStack
    system.
    """
    scope = reactive.scopes.GLOBAL

    # These remote data fields will be automatically mapped to accessors
    # with a basic documentation string provided.
    auto_accessors = ['_authentication_data']

    @reactive.hook('{provides:manila-plugin}-relation-joined')
    def joined(self):
        hookenv.log("ManilaPlugin (subordinate): joined", level=hookenv.DEBUG)
        self.set_state('{relation_name}.connected')
        self.update_status()

    @reactive.hook('{provides:manila-plugin}-relation-changed')
    def changed(self):
        """This hook is used to indicate that something has changed on the
        interface and that interested parties should recheck the properties
        exposed to see if they need to do anything.

        The handler should clear the state after it has been consumed so that
        the next change gets registered too.
        """
        hookenv.log("ManilaPlugin (subordinate): changed", level=hookenv.DEBUG)
        self.update_status()

    @reactive.hook('{provides:manila-plugin}-relation-{broken,departed}')
    def departed(self):
        hookenv.log("ManilaPlugin (subordinate): broken, departed",
                    level=hookenv.DEBUG)
        self.remove_state('{relation_name}.changed')
        self.remove_state('{relation_name}.available')
        self.remove_state('{relation_name}.connected')

    def update_status(self):
        """Set the .available and .changed state if both the plugin name and
        the authentication data are available.

        Note that the .changed state can be used if the plugin changes the
        data. Thus, a subordinate charm (e.g. generic backend) can watched
        changed and then clear it using the method clear_changed() to update
        configuration files as needed.

        The interface will NOT set .changed without having .available at the
        same time.
        """
        hookenv.log("ManilaPlugin (subordinate): update_status() called, "
                    "self._authentication_data(): {}"
                    .format(self._authentication_data()),
                    level=hookenv.DEBUG)
        if self._authentication_data() is not None:
            hookenv.log("ManilaPlugin (subordinate): update-status->available",
                        level=hookenv.DEBUG)
            self.set_state('{relation_name}.available')
            self.set_state('{relation_name}.changed')

    def clear_changed(self):
        """Provide a convenient method to clear the .changed relation"""
        self.remove_state('{relation_name}.changed')

    @property
    def name(self):
        """Returns the name if it has been set"""
        scope = self.conversations()[0].scope
        return self.get_local('_name', default=None, scope=scope)

    @name.setter
    def name(self, name):
        """Set the name plugin -- this is for logs, and to distinguish between
        multiple plugins.

        :param name: a string indicating the name of the plugin (or None)
        """
        scope = self.conversations()[0].scope
        self.set_local(_name=name, scope=scope)
        self.set_remote(_name=name, scope=scope)

    @property
    def authentication_data(self):
        """Return authentication data provided by the Manila charm, or None if
        the data has not yet been set.

        The authentication data is set when the Manila charm has received it
        over its identity interface; thus this may return None until that data
        has become available.  This means that the configuration data may be
        delayed until this is available.

        The authentication data format is:
        {
            'username': <value>
            'password': <value>
            'project_domain_id': <value>
            'project_name': <value>
            'user_domain_id': <value>
            'auth_uri': <value>
            'auth_url': <value>
            'auth_type': <value>  # 'password', typically
        }

        :returns: data object that was passed.
        """
        data = self._authentication_data()
        if data is None:
            return None
        return json.loads(data)["data"]

    @property
    def configuration_data(self):
        """Get the configuration data (if it has been set yet) or None"""
        scope = self.conversations()[0].scope
        data = self.get_local('_configuration_data', default=None, scope=scope)
        if data is None:
            return
        hookenv.log("ManilaPlugin (subordinate): have config: {}"
                    .format(data) , level=hookenv.DEBUG)
        return json.loads(data)["data"]

    @configuration_data.setter
    def configuration_data(self, data):
        """

        NOTE that the data is wrapped in a dictionary, converted to JSON and
        then placed in the juju remote variable.  The other 'end' unpacks this
        and provides the original data to Manila charm.

        If complete is False (or missing) then the configuration data is only
        partially complete OR the subordinate charm is not ready yet -- e.g. it
        still has to configure something.

        The format of the data is:
        {
            "complete": <boolean>,
            '<config file>': {
                '<section>: (
                    (key, value),
                    (key, value),
            )
        }

        Thus data has to be JSONable.

        :param data: object that describes the plugin data to be sent.
        """
        scope = self.conversations()[0].scope
        self.set_local(_configuration_data=json.dumps({"data": data}),
                       scope=scope)
        self.set_remote(_configuration_data=json.dumps({"data": data}),
                        scope=scope)
