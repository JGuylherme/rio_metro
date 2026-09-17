import unittest
import geopandas as gpd
from shapely.geometry import box
from census_demand import unique_census, text
from census_workers import municipal_series
from map_settings import ROOT


class CensusTests(unittest.TestCase):
    def test_multipart_tract_keeps_one_population_count(self):
        frame = gpd.GeoDataFrame({'CD_SETOR': ['1', '1', '2'], 'CD_MUN': ['a', 'a', 'b'],
                                  'v0001': [100, 100, 50]},
                                 geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(3, 0, 4, 1)])
        result = unique_census(frame)
        self.assertEqual(result.v0001.sum(), 150)
        self.assertEqual(result.geometry.area.sum(), 3)
        frame.loc[1, 'v0001'] = 99
        with self.assertRaises(ValueError):
            unique_census(frame)

    def test_missing_bairro_uses_territorial_fallback(self):
        self.assertEqual(text('.', 'municipality-a'), 'municipality-a')
        self.assertEqual(text(None, 'municipality-b'), 'municipality-b')

    def test_official_municipal_series_is_unambiguous(self):
        source = ROOT / 'sources' / 'census_commuting_2022.json'
        local = municipal_series(source, 12167)
        self.assertEqual(len(local), 92)
        self.assertGreater(local['3304557'], local['3303302'])
        with self.assertRaises(ValueError):
            municipal_series(source)


if __name__ == '__main__':
    unittest.main()
