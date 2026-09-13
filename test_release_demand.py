import copy
import unittest

from release_demand import export_demand


class ReleaseDemandTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            'points': [
                {'id': 'home', 'residents': 10, 'jobs': 0, 'popIds': ['p']},
                {'id': 'work', 'residents': 0, 'jobs': 4, 'popIds': ['p']},
                {'id': 'unused', 'residents': 1, 'jobs': 0, 'popIds': []},
            ],
            'pops': [{'id': 'p', 'residenceId': 'home', 'jobId': 'work', 'size': 4}],
        }

    def test_export_preserves_census_and_routes(self):
        original = copy.deepcopy(self.source)
        result = export_demand(self.source)
        self.assertEqual(self.source, original)
        self.assertEqual(result['pops'], original['pops'])
        self.assertEqual([p['residents'] for p in result['points']], [4, 0])
        self.assertEqual([p['jobs'] for p in result['points']], [0, 4])
        self.assertEqual(export_demand(result), result)

    def test_rejects_inconsistent_source(self):
        for field, value in [('jobs', 3), ('popIds', [])]:
            with self.subTest(field=field):
                source = copy.deepcopy(self.source)
                source['points'][1][field] = value
                with self.assertRaises(ValueError):
                    export_demand(source)


if __name__ == '__main__':
    unittest.main()
