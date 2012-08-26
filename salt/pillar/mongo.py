"""
Read pillar data from a mongodb collection.

This module will load a node-specific pillar dictionary from a mongo
collection. It uses the node's id for lookups and can load either the whole
document, or just a specific field from that
document as the pillar dictionary.

Salt Master Mongo Configuration
===============================

The module shares the same base mongo connection variables as
:py:mod:`salt.returners.mongo_return`. These variables go in your master
config file.

   * ``mongo.db`` - The mongo database to connect to. Defaults to ``'salt'``.
   * ``mongo.host`` - The mongo host to connect to. Supports replica sets by
     specifying all hosts in the set, comma-delimited. Defaults to ``'salt'``.
   * ``mongo.port`` - The port that the mongo database is running on. Defaults
     to ``27017``.
   * ``mongo.user`` - The username for connecting to mongo. Only required if
     you are using mongo authentication. Defaults to ``''``.
   * ``mongo.password`` - The password for connecting to mongo. Only required
     if you are using mongo authentication. Defaults to ``''``.


Configuring the Mongo ext_pillar
================================

The Mongo ext_pillar takes advantage of the fact that the Salt Master
configuration file is yaml. It uses a sub-dictionary of values to adjust
specific features of the pillar. This is the explicit single-line dictionary
notation for yaml. One may be able to get the easier-to-read multine dict to
work correctly with some experimentation.

.. code-block:: yaml

  ext_pillar:
    - mongo: {collection: vm, id_field: name, re_pattern: \.example\.com, field: pillar}

In the example above, we've decided to use the ``vm`` collection in the
database to store the data. Minion ids are stored in the ``name`` field on
documents in that collection. And, since minon ids are FQDNs in most cases,
we'll need to trim the domain name in order to find the minon by hostname in
the collection. When we find a minion, return only the ``pillar`` field, as
that will contain the dictionary of values for this node.


Module Documentation
====================
"""

# Import python libs
import logging
import re

try:
    import pymongo
    has_pymongo = True
except ImportError:
    has_pymongo = False


__opts__ = {'mongo.db': 'salt',
            'mongo.host': 'salt',
            'mongo.password': '',
            'mongo.port': 27017,
            'mongo.user': ''}


def __virtual__():
    if not has_pymongo:
        return False
    return 'mongo'

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(collection='pillar', id_field='_id', re_pattern=None,
               re_replace='', fields=None):
    """
    Connect to a mongo database and read per-node pillar information.

    Parameters:
        * `collection`: The mongodb collection to read data from. Defaults to
          ``'pillar'``.
        * `id_field`: The field in the collection that represents an individual
          minon id. Defaults to ``'_id'``.
        * `re_pattern`: If your naming convention in the collection is shorter
          than the minion id, you can use this to trim the name.
          `re_pattern` will be used to match the name, and `re_replace` will
          be used to replace it. Backrefs are supported as they are in the
          Python standard library. If ``None``, no mangling of the name will
          be performed - the collection will be searched with the entire
          minion id. Defaults to ``None``.
        * `re_replace`: Use as the replacement value in node ids matched with
          `re_pattern`. Defaults to ''.
        * `fields`: The specific fields in the document to use for the pillar
          data. If ``None``, will use the entire document. If using the
          entire document, the ``_id`` field will be converted to string. Be
          careful with other fields in the document as they must be string
          serializable. Defaults to ``None``.
    """
    conn = pymongo.Connection(__opts__['mongo.host'], __opts__['mongo.port'])
    db = conn[__opts__['mongo.db']]

    user = __opts__.get('mongo.user')
    password = __opts__.get('mongo.password')

    if user and password:
        db.authenticate(user, password)

    # Do the regex string replacement on the minion id
    minion_id = __opts__['id']
    if re_pattern:
        minion_id = re.sub(re_pattern, re_replace, minion_id)

    log.info("ext_pillar.mongo: looking up pillar def for {'%s': '%s'} "
             "in mongo" % (id_field, minion_id))


    pillar = db[collection].find_one({id_field: minion_id}, fields=fields)
    if pillar:
        if fields:
            log.debug("ext_pillar.mongo: found document, returning fields '%s'"
                      % fields)
        else:
            log.debug("ext_pillar.mongo: found document, returning whole doc")
        if '_id' in pillar:
            # Converting _id to a string
            # will avoid the most common serialization error cases, but DBRefs
            # and whatnot will still cause problems.
            pillar['_id'] = str(pillar['_id'])
        return pillar
    else:
        # If we can't find the minion the database it's not necessarily an
        # error.
        log.debug("ext_pillar.mongo: no document found in collection %s" %
                  collection)
        return {}
