#!/usr/bin/python
#
# Copyright (c) 2011 Red Hat, Inc.
#
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

# Python
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../common/")
import testutil

from pulp.common import dateutils
from pulp.server.content.types import database, model
from pulp.server.db.model.gc_repository import RepoContentUnit
from pulp.server.managers.repo._exceptions import InvalidOwnerType
import pulp.server.managers.repo.unit_association as association_manager
from pulp.server.managers.repo.unit_association import SingleTypeCriteria, MultipleTypeCriteria, DateQueryParameter
from pulp.server.managers.repo.unit_association import OWNER_TYPE_USER, OWNER_TYPE_IMPORTER
import pulp.server.managers.content.cud as content_cud_manager

# constants --------------------------------------------------------------------

TYPE_1_DEF = model.TypeDefinition('type-1', 'Type 1', 'Test Definition One',
                                  ['key-1'], ['search-1'], [])

TYPE_2_DEF = model.TypeDefinition('type-2', 'Type 2', 'Test Definition Two',
                                  ['key-2a', 'key-2b'], [], ['type-1'])

# -- cud test cases -----------------------------------------------------------

class RepoUnitAssociationManagerTests(testutil.PulpTest):

    def clean(self):
        super(RepoUnitAssociationManagerTests, self).clean()
        database.clean()
        RepoContentUnit.get_collection().remove()


    def setUp(self):
        super(RepoUnitAssociationManagerTests, self).setUp()
        database.update_database([TYPE_1_DEF, TYPE_2_DEF])
        self.manager = association_manager.RepoUnitAssociationManager()
        self.content_manager = content_cud_manager.ContentManager()

    def test_associate_by_id(self):
        """
        Tests creating a new association by content unit ID.
        """

        # Test
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-2', OWNER_TYPE_USER, 'admin')

        # Verify
        repo_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(2, len(repo_units))

        unit_ids = [u['unit_id'] for u in repo_units]
        self.assertTrue('unit-1' in unit_ids)
        self.assertTrue('unit-2' in unit_ids)

    def test_associate_by_id_existing(self):
        """
        Tests attempting to create a new association where one already exists.
        """

        # Test
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin') # shouldn't error

        # Verify
        repo_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(1, len(repo_units))
        self.assertEqual('unit-1', repo_units[0]['unit_id'])

    def test_associate_by_id_other_owner(self):
        """
        Tests making a second association using a different owner.
        """

        # Test
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_IMPORTER, 'test-importer')

        # Verify
        repo_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(2, len(repo_units))
        self.assertEqual('unit-1', repo_units[0]['unit_id'])
        self.assertEqual('unit-1', repo_units[1]['unit_id'])

    def test_associate_invalid_owner_type(self):
        # Test
        self.assertRaises(InvalidOwnerType, self.manager.associate_unit_by_id, 'repo-1', 'type-1', 'unit-1', 'bad-owner', 'irrelevant')

    def test_associate_all(self):
        """
        Tests making multiple associations in a single call.
        """

        # Test
        ids = ['foo', 'bar', 'baz']
        self.manager.associate_all_by_ids('repo-1', 'type-1', ids, OWNER_TYPE_USER, 'admin')

        # Verify
        repo_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(len(ids), len(repo_units))
        for unit in repo_units:
            self.assertTrue(unit['unit_id'] in ids)

    def test_unassociate_by_id(self):
        """
        Tests removing an association that exists by its unit ID.
        """

        # Setup
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-2', OWNER_TYPE_USER, 'admin')

        # Test
        self.manager.unassociate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')

        # Verify
        repo_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(1, len(repo_units))
        self.assertEqual('unit-2', repo_units[0]['unit_id'])

    def test_unassociate_by_id_no_association(self):
        """
        Tests unassociating a unit where no association exists.
        """

        # Test - Make sure this does not raise an error
        self.manager.unassociate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')

    def test_unassociate_by_id_other_owner(self):
        """
        Tests that removing the association owned by one party doesn't affect another owner's association.
        """

        # Setup
        # Setup
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_IMPORTER, 'test-importer')

        # Test
        self.manager.unassociate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')

        # Verify
        repo_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(1, len(repo_units))
        self.assertEqual('unit-1', repo_units[0]['unit_id'])

    def test_unassociate_all(self):
        """
        Tests unassociating multiple units in a single call.
        """

        # Setup
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-2', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-1', 'unit-3', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-2', 'unit-1', OWNER_TYPE_USER, 'admin')
        self.manager.associate_unit_by_id('repo-1', 'type-2', 'unit-2', OWNER_TYPE_USER, 'admin')

        unit_coll = RepoContentUnit.get_collection()
        self.assertEqual(5, len(list(unit_coll.find({'repo_id' : 'repo-1'}))))

        # Test
        self.manager.unassociate_all_by_ids('repo-1', 'type-1', ['unit-1', 'unit-2'], OWNER_TYPE_USER, 'admin')

        # Verify
        self.assertEqual(3, len(list(unit_coll.find({'repo_id' : 'repo-1'}))))

        self.assertTrue(unit_coll.find_one({'repo_id' : 'repo-1', 'unit_type_id' : 'type-1', 'unit_id' : 'unit-3'}) is not None)
        self.assertTrue(unit_coll.find_one({'repo_id' : 'repo-1', 'unit_type_id' : 'type-2', 'unit_id' : 'unit-1'}) is not None)
        self.assertTrue(unit_coll.find_one({'repo_id' : 'repo-1', 'unit_type_id' : 'type-2', 'unit_id' : 'unit-2'}) is not None)

    def test_get_unit_ids(self):

        # Setup
        repo_id = 'repo-1'
        units = {'type-1': ['1-1', '1-2', '1-3'],
                 'type-2': ['2-1', '2-2', '2-3']}
        for type_id, unit_ids in units.items():
            self.manager.associate_all_by_ids(repo_id, type_id, unit_ids, OWNER_TYPE_USER, 'admin')

        # Test - No Type
        all_units = self.manager.get_unit_ids(repo_id)

        # Verify - No Type
        self.assertTrue('type-1' in all_units)
        self.assertTrue('type-2' in all_units)
        self.assertEqual(3, len(all_units['type-1']))
        self.assertEqual(3, len(all_units['type-2']))

        # Test - By Type
        type_1_units = self.manager.get_unit_ids(repo_id, 'type-1')

        # Verify - By Type
        self.assertTrue('type-1' in type_1_units)
        self.assertFalse('type-2' in type_1_units)
        for id in units['type-1']:
            self.assertTrue(id in type_1_units['type-1'], '%s not in %s' % (id, ','.join(type_1_units['type-1'])))
        for id in type_1_units['type-1']:
            self.assertTrue(id in units['type-1'])


# -- query test cases ---------------------------------------------------------

TYPE_DEF_ALPHA = model.TypeDefinition('alpha', 'Alpha', 'Test Type Alpha',
    ['key_1'], ['search-1'], [])
TYPE_DEF_BETA = model.TypeDefinition('beta', 'Beta', 'Test Type Beta',
    ['key_1'], [], [])
TYPE_DEF_GAMMA = model.TypeDefinition('gamma', 'Gamma', 'Test Type Gamma',
    ['key_1'], [], [])
TYPE_DEF_DELTA = model.TypeDefinition('delta', 'Delta', 'Test Type Delta',
    ['key_1'], [], [])
TYPE_DEF_EPSILON = model.TypeDefinition('epsilon', 'Epsilon', 'Test Type Epsilon',
    ['key_1'], [], [])

_QUERY_TYPES = [TYPE_DEF_ALPHA, TYPE_DEF_BETA, TYPE_DEF_GAMMA, TYPE_DEF_DELTA, TYPE_DEF_EPSILON]

class UnitAssociationQueryTests(testutil.PulpTest):

    def clean(self):
        super(UnitAssociationQueryTests, self).clean()
        database.clean()
        RepoContentUnit.get_collection().remove()

    def setUp(self):
        super(UnitAssociationQueryTests, self).setUp()
        database.update_database(_QUERY_TYPES)
        self.manager = association_manager.RepoUnitAssociationManager()
        self.content_manager = content_cud_manager.ContentManager()
        self._populate()

    def _populate(self):
        """
        Populates the database with units and associations with the
        following properties:

        - Units are from types: alpha, beta, gamma
        - Each unit has metadata:
          - key_1 - unique per unit per type (is the unit ID)
          - md_1 - unique per unit in a given type (simple counter)
          - md_2 - 0 or 1 depending on when it was added
          - md_3 - number of characters in the unit ID
        - All associations will have created/updated dates in ascending
          order according to alphabetical order

        - Alpha Units
          - Only associated once with repo-1
          - Association owner is type importer with ID test-importer
        - Beta Units
          - Only associated once with repo-1
          - Only associated once with repo-2 as well
          - Association owner is type user with ID admin
        - Gamma Units
          - Each associated twice with repo-1
          - One association is type importer with ID test-importer-2
          - One association is type user with ID admin-2
          - The user-created associations are older than the importer ones
        - Delta Units
          - Only associated with repo-2
          - Association owner is type importer with ID test-importer
        - Epsilon Units
          - Exist in the database but not associations
        """

        # -- test data --------

        self.units = {
            'alpha' : ['aardvark', 'anthill', 'apple',],
            'beta' : ['ball', 'balloon', 'bat', 'boardwalk'],
            'gamma' : ['garden', 'gnome'],
            'delta' : ['dog', 'dragon']
        }

        #   Generate timestamps 1 day apart in ascending order relative to now.
        #   The last entry is 1 day before now. Timestamps are already in iso8601.
        #     timestamps[x] < timestamps[x+1]

        now = datetime.datetime.now()
        self.timestamps = []
        for i in range(10, 0, -1):
            ts = now - datetime.timedelta(i)
            self.timestamps.append(dateutils.format_iso8601_datetime(ts))

        #   Assertions based on the test data
        self.repo_1_count = reduce(lambda x, y: x + len(self.units[y]), ['alpha', 'beta', 'gamma', 'gamma'], 0)
        self.repo_1_count_no_dupes = reduce(lambda x, y: x + len(self.units[y]), ['alpha', 'beta', 'gamma'], 0)
        self.repo_2_count = reduce(lambda x, y: x + len(self.units[y]), ['beta', 'delta'], 0)

        # -- add units --------

        for type_id, unit_ids in self.units.items():
            unit_ids.sort()
            for i, unit_id in enumerate(unit_ids):
                metadata = {
                    'key_1' : unit_id,
                    'md_1' : i,
                    'md_2' : i % 2,
                    'md_3' : len(unit_id),
                }
                self.content_manager.add_content_unit(type_id, unit_id, metadata)

        # -- create associations --------

        def make_association(repo_id, type_id, unit_id, owner_type, owner_id, index):
            """
            Utility to perform standard association test data stuff such as
            setting the created/updated timestamps.
            """

            association_collection = RepoContentUnit.get_collection()
            self.manager.associate_unit_by_id(repo_id, type_id, unit_id, owner_type, owner_id)
            a = association_collection.find_one({'repo_id' : repo_id, 'unit_type_id' : type_id, 'unit_id' : unit_id})
            a['created'] = self.timestamps[index]
            a['updated'] = self.timestamps[index]
            association_collection.save(a, safe=True)

        #   Alpha
        for i, unit_id in enumerate(self.units['alpha']):
            make_association('repo-1', 'alpha', unit_id, OWNER_TYPE_IMPORTER, 'test-importer', i)

        #   Beta
        for i, unit_id in enumerate(self.units['beta']):
            make_association('repo-1', 'beta', unit_id, OWNER_TYPE_USER, 'admin', i)
            make_association('repo-2', 'beta', unit_id, OWNER_TYPE_USER, 'admin', i)

        #   Gamma
        for i, unit_id in enumerate(self.units['gamma']):
            make_association('repo-1', 'gamma', unit_id, OWNER_TYPE_IMPORTER, 'test-importer-2', i+1)
            make_association('repo-1', 'gamma', unit_id, OWNER_TYPE_USER, 'admin-2', i)

        #   Delta
        for i, unit_id in enumerate(self.units['delta']):
            make_association('repo-2', 'delta', unit_id, OWNER_TYPE_IMPORTER, 'test-importer', i)

    # -- get_units tests ------------------------------------------------------

    def test_get_units_no_criteria(self):
        # Test
        units_1 = self.manager.get_units('repo-1')
        units_2 = self.manager.get_units('repo-2')

        # Verify
        self.assertEqual(len(units_1), self.repo_1_count)
        self.assertEqual(len(units_2), self.repo_2_count)

        for u in units_1 + units_2:
            self._assert_unit_integrity(u)

        self._assert_default_sort(units_1)
        self._assert_default_sort(units_2)

    def test_get_units_filter_type(self):
        # Test
        criteria = MultipleTypeCriteria(type_ids=['alpha', 'beta'])
        units = self.manager.get_units('repo-1', criteria)

        # Verify
        expected_count = reduce(lambda x, y: x + len(self.units[y]), ['alpha', 'beta'], 0)
        self.assertEqual(expected_count, len(units))

        for u in units:
            self._assert_unit_integrity(u)
            self.assertTrue(u['unit_type_id'] in ['alpha', 'beta']) # purpose of this test

        self._assert_default_sort(units)

    def test_get_units_limit(self):
        # Test
        low_criteria = MultipleTypeCriteria(limit=2)
        low_units = self.manager.get_units('repo-1', low_criteria)

        high_criteria = MultipleTypeCriteria(limit=10000)
        high_units = self.manager.get_units('repo-1', high_criteria)

        # Verify
        self.assertEqual(2, len(low_units))
        self.assertEqual(self.repo_1_count, len(high_units))

        #   Make sure the limit was applied to the front of the results
        self.assertEqual(low_units[0], high_units[0])
        self.assertEqual(low_units[1], high_units[1])

    def test_get_units_skip(self):
        # Test
        skip_criteria = MultipleTypeCriteria(skip=2)
        skip_units = self.manager.get_units('repo-1', skip_criteria)

        all_units = self.manager.get_units('repo-1')

        # Verify
        self.assertEqual(self.repo_1_count -2, len(skip_units))

        # Make sure it was the first two that were actually skipped
        for su, au in zip(skip_units, all_units[2:]):
            self.assertEqual(su, au)

    def test_get_units_sort(self):
        # Test
        order_criteria = MultipleTypeCriteria(sort=[('owner_type', association_manager.SORT_DESCENDING)]) # owner_type will produce a non-default sort
        order_units = self.manager.get_units('repo-1', order_criteria)

        # Verify
        self.assertEqual(self.repo_1_count, len(order_units))

        for i in range(0, len(order_units) - 1):
            u1 = order_units[i]
            u2 = order_units[i+1]
            self.assertTrue(u1['owner_type'] >= u2['owner_type'])

    def test_get_units_filter_created(self):
        # Test
        after_param = DateQueryParameter(self.timestamps[0], DateQueryParameter.AFTER)
        after_criteria = MultipleTypeCriteria(first_associated=after_param)
        after_units = self.manager.get_units('repo-1', after_criteria)

        before_param = DateQueryParameter(self.timestamps[1], DateQueryParameter.BEFORE)
        before_criteria = MultipleTypeCriteria(first_associated=before_param)
        before_units = self.manager.get_units('repo-1', before_criteria)

        after_equal_param = DateQueryParameter(self.timestamps[1], DateQueryParameter.AFTER_OR_EQUAL)
        after_equal_criteria = MultipleTypeCriteria(first_associated=after_equal_param)
        after_equal_units = self.manager.get_units('repo-1', after_equal_criteria)

        before_equal_param = DateQueryParameter(self.timestamps[1], DateQueryParameter.BEFORE_OR_EQUAL)
        before_equal_criteria = MultipleTypeCriteria(first_associated=before_equal_param)
        before_equal_units = self.manager.get_units('repo-1', before_equal_criteria)

        # Verify

        # The first association in each type/owner combination will be timestamps[0],
        # the second timestamps[1]. There are 4 such type/owner combinations.

        self.assertEqual(self.repo_1_count - 4, len(after_units))
        self.assertEqual(4, len(before_units))
        self.assertEqual(self.repo_1_count - 4, len(after_equal_units))
        self.assertEqual(8, len(before_equal_units))

    def test_get_units_remove_duplicates(self):
        # Test
        criteria = MultipleTypeCriteria(remove_duplicates=True)
        units = self.manager.get_units('repo-1', criteria)

        # Verify

        # The gamma units are associated twice, so they should only be returned once.
        self.assertEqual(self.repo_1_count - len(self.units['gamma']), len(units))

        # The gamma user associations were created at an earlier date, so all of
        # the gamma associations should be of owner type user.
        non_user_gamma_units = [u for u in units if u['unit_type_id'] == 'gamma' and u['owner_type'] != OWNER_TYPE_USER]
        self.assertEqual(0, len(non_user_gamma_units))

    # -- get_units_by_type tests ----------------------------------------------

    # -- utilities ------------------------------------------------------------

    def _assert_unit_integrity(self, unit):
        """
        Makes sure all of the expected fields are present in the unit and that
        it is assembled correctly. This call has a limited concept of what the
        values should be but will do some tests were possible.

        This call will have to change if the returned structure of the units is
        changed.
        """

        self.assertTrue(unit['repo_id'] is not None)
        self.assertTrue(unit['unit_type_id'] is not None)
        self.assertTrue(unit['unit_id'] is not None)
        self.assertTrue(unit['owner_type'] is not None)
        self.assertTrue(unit['owner_id'] is not None)
        self.assertTrue(unit['created'] is not None)
        self.assertTrue(unit['updated'] is not None)

        self.assertTrue(unit['metadata'] is not None)
        self.assertTrue(unit['metadata']['key_1'] is not None)
        self.assertTrue(unit['metadata']['md_1'] is not None)
        self.assertTrue(unit['metadata']['md_2'] is not None)
        self.assertTrue(unit['metadata']['md_3'] is not None)

    def _assert_default_sort(self, units):
        """
        Asserts that units are sorted first by type, then by created within
        each type.
        """

        for i in range(0, len(units) - 1):
            u1 = units[i]
            u2 = units[i+1]
            self.assertTrue(u1['unit_type_id'] <= u2['unit_type_id'])

        units_by_type = {}
        for u in units:
            x = units_by_type.setdefault(u['unit_type_id'], [])
            x.append(u)

        for units_list in units_by_type.values():
            for i in range(0, len(units_list) - 1):
                u1 = units_list[i]
                u2 = units_list[i+1]
                self.assertTrue(u1['created'] <= u2['created'])