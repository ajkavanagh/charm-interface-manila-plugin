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


class ManilaPluginRequires(reactive.RelationBase):
    """The is the Manila 'end' of the relation.

    The auto accessors are underscored as for some reason RelationBase only
    provides these as 'calls'; i.e. they have to be used as `self._name()`.
    This class therefore provides @properties `name` and `plugin_data` that can
    be used directly.

    This side of the interface sends the manila service user authentication
    information to the plugin charm (which is a subordinate) and gets
    configuration segments for the various files that the manila charm 'owns'
    and, therefore, writes out.

    The most important property is the 'ready' property which indicates that
    the configuration data on the interface is valid and thus can be written to
    the configuration files by the manila charm.
    """
    scope = reactive.scopes.UNIT

    # These remote data fields will be automatically mapped to accessors
    # with a basic documentation string provided.
    auto_accessors = ['_name', '_configuration_data']

    @reactive.hook('{requires:manila-plugin}-relation-joined')
    def joined(self):
        hookenv.log("ManilaPlugin (principal): joined", level=hookenv.DEBUG)
        self.set_state('{relation_name}.connected')
        self.update_status()

    @reactive.hook('{requires:manila-plugin}-relation-changed')
    def changed(self):
        hookenv.log("ManilaPlugin (principal): changed", level=hookenv.DEBUG)
        self.update_status()

    @reactive.hook('{requires:manila-plugin}-relation-{broken,departed}')
    def departed(self):
        hookenv.log("ManilaPlugin (principal): broken, departed",
                    level=hookenv.DEBUG)
        self.remove_state('{relation_name}.connected')
        self.remove_state('{relation_name}.available')
        self.remove_state('{relation_name}.changed')

    def update_status(self):
        """Set the .available and .changed state if both the plugin name and
        the configuration data are available.

        Note that the .changed state can be used if the plugin changes the
        data. Thus, Manila can watched changed and then clear it using the
        method clear_changed() to update configuration files as needed.

        The interface will NOT set .changed without having .available at the
        same time.
        """
        if self._name() is not None and self._configuration_data() is not None:
            hookenv.log(
                "ManilaPlugin (principal): have _name:{} and "
                "_configuration data:{}"
                .format(self._name(), self._configuration_data(),
                        level=hookenv.DEBUG))
            self.set_state('{relation_name}.available')
            self.set_state('{relation_name}.changed')

    def clear_changed(self):
        """Provide a convenient method to clear the .changed relation"""
        self.remove_state('{relation_name}.changed')

    @property
    def name(self):
        """Returns a string of the name or None if it doesn't exist"""
        return self._name()

    @property
    def authentication_data(self):
        """Get the authentication data (if it has been set yet) or None"""
        try:
            scope = self.conversations()[0].scope
            data = self.get_local('_authentication_data', default=None,
                                  scope=scope)
        except ValueError:
            return None
        if data is None:
            return None
        return json.loads(data)["data"]

    @authentication_data.setter
    def authentication_data(self, value):
        """Set the authentication data to the plugin charm.  This is to enable
        the plugin to either 'talk' to OpenStack or to provide authentication
        data into the configuraiton sections that it needs to set (the generic
        backend needs to do this).

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

        :param value: a dictionary of data to set.
        """
        hookenv.log("ManilaPlugin (principal) Setting authentication data:{}"
                    .format(value),
                    level=hookenv.DEBUG)
        keys = {'username', 'password', 'project_domain_id', 'project_name',
                'user_domain_id', 'auth_uri', 'auth_url', 'auth_type'}
        passed_keys = set(value.keys())
        if passed_keys.difference(keys) or keys.difference(passed_keys):
            hookenv.log(
                "Setting Authentication data; there may be missing or mispelt "
                "keys: passed: {}".format(passed_keys),
                level=hookenv.WARNING)
        # need to check for each conversation whether we've sent the data, or
        # whether it is different, and then set the local & remote only if that
        # is the case.
        for conversation in self.conversations():
            try:
                existing_auth_data = self.get_local('_authentication_data',
                                                    default=None,
                                                    scope=conversation.scope)
            except ValueError:
                existing_auth_data = None
            if existing_auth_data is not None:
                # see if they are different
                existing_auth = json.loads(existing_auth_data)["data"]
                if (existing_auth.keys() == value.keys() and
                        all([v == value[k]
                             for k, v in existing_auth.items()])):
                    # the values haven't changed, so don't set them again
                    continue
            self.set_local(_authentication_data=json.dumps({"data": value}),
                           scope=conversation.scope)
            self.set_remote(_authentication_data=json.dumps({"data": value}),
                            scope=conversation.scope)

    @property
    def configuration_data(self):
        """Return the configuration_data from the plugin if it is available.

        The format of the data returned is:
        {
            "complete": <boolean>,
            '<config file>': {
                '<section>: (
                    (key, value),
                    (key, value),
                    "or string",
            )
        }

        :returns: data object that was passed.
        """
        data = self._configuration_data()
        if data is None:
            return
        hookenv.log("ManilaPlugin (principal): have configuration_data: {}"
                    .format(data), level=hookenv.DEBUG)
        return json.loads(data)["data"]
