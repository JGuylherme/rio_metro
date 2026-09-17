import copy
import unittest
from special_demand import add_special_demand, capacity, validate_catalog
from release_demand import export_demand


class SpecialDemandTests(unittest.TestCase):
    def setUp(self):
        self.base = {'points': [
            {'id': 'home', 'location': [-43.3, -22.9], 'residents': 10, 'jobs': 0, 'popIds': ['work']},
            {'id': 'job', 'location': [-43.2, -22.9], 'residents': 0, 'jobs': 10, 'popIds': ['work']},
        ], 'pops': [{'id': 'work', 'residenceId': 'home', 'jobId': 'job', 'size': 10,
                    'drivingSeconds': 600, 'drivingDistance': 8000}]}
        self.site = {'id': 'AIR_TEST', 'name': 'Test', 'category': 'airports', 'location': [-43.25, -22.85],
                     'source_count': 36600, 'source_year': 2024, 'source_url': 'https://example.org/source',
                     'basis': 'annual', 'days_per_year': 366, 'factors': {'two_legs_per_pop': .5},
                     'assumptions': 'Arrivals plus departures; round-trip equivalents',
                     'max_distance_m': 30000, 'decay_seconds': 1200}
        self.router = lambda destination, origins: [(10000, 900)] * len(origins)

    def test_special_flows_preserve_workers_and_balance_export(self):
        original = copy.deepcopy(self.base)
        result, audit = add_special_demand(self.base, {'sites': [self.site]}, self.router)
        self.assertEqual(self.base, original)
        self.assertEqual(result['pops'][0], original['pops'][0])
        self.assertEqual(result['points'][0]['residents'], 60)
        self.assertEqual(result['points'][1]['jobs'], 10)
        self.assertEqual(audit['special_trip_equivalents'], 50)
        self.assertEqual(audit['suggested_registry_tags'], ['airports'])
        self.assertEqual(export_demand(result), result)
        repeat, _ = add_special_demand(self.base, {'sites': [self.site]}, self.router)
        self.assertEqual(result, repeat)
        with self.assertRaises(ValueError):
            add_special_demand(result, {'sites': [self.site]}, self.router)

    def test_unreachable_or_out_of_catchment_fails(self):
        for route in (None, (50000, 3000)):
            with self.subTest(route=route), self.assertRaises(ValueError):
                add_special_demand(self.base, {'sites': [self.site]}, lambda d, o: [route])

    def test_rejects_ferry_origins_on_wrong_side(self):
        site = {**self.site, 'origin_municipalities': ['3303302']}
        catalog = {'sites': [site], 'origin_metadata': [{'id': 'home', 'municipality_code': '3304557'}]}
        with self.assertRaises(ValueError):
            add_special_demand(self.base, catalog, self.router)

    def test_rejects_duplicate_and_missing_provenance(self):
        with self.assertRaises(ValueError):
            validate_catalog({'sites': [self.site, self.site]})
        with self.assertRaises(ValueError):
            validate_catalog({'sites': [{**self.site, 'source_url': ''}]})

    def test_enrollment_is_not_divided_by_calendar_days(self):
        site = {**self.site, 'basis': 'enrollment', 'source_count': 1000, 'factors': {'attendance': .9}}
        self.assertEqual(capacity(site), 900)

    def test_period_uses_observed_days_and_beds_use_daily_occupancy(self):
        site = {**self.site, 'basis': 'period', 'source_count': 60800,
                'period_start': '2025-01-01', 'period_end': '2025-10-31'}
        self.assertEqual(capacity(site), 100)
        with self.assertRaises(ValueError):
            capacity({**site, 'period_end': '2024-12-31'})
        self.assertEqual(capacity({**self.site, 'basis': 'beds', 'source_count': 400,
                                  'factors': {'occupancy_assumed': .8}}), 320)

    def test_rejects_double_counted_campus_allocation(self):
        a = {**self.site, 'allocation_group': 'students', 'factors': {'campus_share_assumed': .7}}
        b = {**a, 'id': 'AIR_OTHER'}
        with self.assertRaises(ValueError):
            validate_catalog({'sites': [a, b]})
        validate_catalog({'sites': [a, {**b, 'factors': {'campus_share_assumed': .3}}]})

    def test_shared_beach_total_is_partitioned_once(self):
        a={**self.site,'allocation_group':'beaches','allocation_share_key':'beach_share_assumed',
           'factors':{'beach_share_assumed':.65}}
        b={**a,'id':'AIR_SECOND','factors':{'beach_share_assumed':.35}}
        validate_catalog({'sites':[a,b]})
        self.assertEqual(capacity(a)+capacity(b),100)
        with self.assertRaises(ValueError):
            validate_catalog({'sites':[a,{**b,'factors':{'beach_share_assumed':.5}}]})


if __name__ == '__main__':
    unittest.main()
