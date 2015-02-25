# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Registries for search module."""

from flask.ext.registry import RegistryError, ModuleAutoDiscoveryRegistry, \
    RegistryProxy
from werkzeug.utils import cached_property

from invenio.ext.registry import DictModuleAutoDiscoverySubRegistry, \
    ModuleAutoDiscoverySubRegistry
from invenio.modules.collections.models import FacetCollection
from invenio.utils.memoise import memoize

searchext = RegistryProxy('searchext', ModuleAutoDiscoveryRegistry,
                          'searchext')


class SearchServiceRegistry(ModuleAutoDiscoverySubRegistry):

    """Search Service Registry."""

    __required_plugin_API_version__ = "Search Service Plugin API 1.0"

    def register(self, item):
        """Check plugin version and instantiate search service plugin."""
        if item.__plugin_version__ != self.__required_plugin_API_version__:
            raise RegistryError(
                'Invalid plugin version {0} required {1}'.format(
                    item.__plugin_version__,
                    self.__required_plugin_API_version__
                ))
        service = getattr(item, item.__name__.split('.')[-1])
        return super(SearchServiceRegistry, self).register(service())

services = RegistryProxy('searchext.services', SearchServiceRegistry,
                         'services', registry_namespace=searchext)


class FacetsRegistry(DictModuleAutoDiscoverySubRegistry):

    """Registry for facets modules.

    Serves also modules sets and their configuration
    for specific collections.
    """

    def keygetter(self, key, original_value, new_value):
        """
        Method used to compute the key for a value being registered.

        The key is the facet name stored in facet module.

        :param key: Key if provided by the user. Defaults to None.
        :param value: Value being registered. FacetBuilder object
        """
        return new_value.name

    def valuegetter(self, value):
        """Return FacetBuilder from inside the module.

        :param value: loaded python module with FacetBuilder instance
            stored in facet property
        """
        if self.facet_plugin_checker(value):
            return value.facet

    @classmethod
    def facet_plugin_checker(cls, plugin_code):
        """Handy function to check facet plugin.

        :param plugin_code: a module with facet definition - should have facet
            variable
        """
        from invenio.modules.search.facet_builders import FacetBuilder
        if 'facet' in dir(plugin_code):
            candidate = getattr(plugin_code, 'facet')
            if isinstance(candidate, FacetBuilder):
                return candidate

    @memoize
    def get_facets_for_collection(self, collection_id):
        """Return facets set for a collection.

        :param collection_id: the collection id for requested facets set
        """
        facets_conf = FacetCollection.query\
            .filter(FacetCollection.id_collection == collection_id)\
            .order_by(FacetCollection.order)\
            .all()

        collection_facets = []
        for facet in facets_conf:
            if facet.facet_name not in self.keys():
                raise RegistryError(
                    'Facet %s is not available.' +
                    'Maybe it\'s on PACKAGES_FACETS_EXCLUDE config list'
                    % facet.facet_name)
            collection_facets.append(self.get(facet.facet_name))

        return collection_facets

    @cached_property
    def default_facets(self):
        """Return default set of facets."""
        return self.get_facets_for_collection(1)

    def get_facets_config(self, collection, qid):
        """Return facet config for the collection.

        If no configuration found returns the default facets set.
        :param collection: Collection object facets matching which are returned
        :param qid: md5 hash of search parameters generated by
            get_search_query_id() from invenio.modules.search.cache
        """
        if collection and self.get_facets_for_collection(collection.id):
            facets_set = self.get_facets_for_collection(collection.id)
        else:
            facets_set = self.default_facets

        return [facet.get_conf(collection=collection, qid=qid)
                for facet in facets_set]

facets = RegistryProxy('facets', FacetsRegistry, 'facets')

units = RegistryProxy(
    'searchext.units', DictModuleAutoDiscoverySubRegistry, 'units',
    keygetter=lambda key, value, new_value: value.__name__.split('.')[-1],
    valuegetter=lambda value: value.search_unit,
    registry_namespace=searchext,
)
