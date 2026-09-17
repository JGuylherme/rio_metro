import unittest
import numpy as np
from shapely.geometry import box, shape
from shapely.ops import unary_union
from render_rio import depth_contours


class WaterContoursTests(unittest.TestCase):
    def test_preserves_coast_islands_and_water_outside_dem(self):
        water = box(-1, -1, 10, 10).difference(box(3, 3, 5, 5))
        z = -(np.arange(10)[:, None] + np.arange(10)[None, :]) * 2.
        original = z.copy()
        z[0, 0] = np.nan
        features = depth_contours(water, z, 0, 9, 1, 1)
        shapes = [shape(f['geometry']) for f in features]
        self.assertTrue(all(g.is_valid for g in shapes))
        union = unary_union(shapes)
        self.assertLess(union.symmetric_difference(water).area, 1e-9)
        self.assertAlmostEqual(sum(g.area for g in shapes), union.area, places=8)
        self.assertTrue(all(f['properties']['depth_min'] < 0 for f in features))
        np.testing.assert_array_equal(z[1:], original[1:])
        # Sloping bathymetry yields diagonal boundaries, not rectangular cells.
        self.assertTrue(any(abs(b[0]-a[0]) > 1e-6 and abs(b[1]-a[1]) > 1e-6
                            for g in shapes for a,b in zip(g.exterior.coords, list(g.exterior.coords)[1:])))


if __name__ == '__main__':
    unittest.main()
