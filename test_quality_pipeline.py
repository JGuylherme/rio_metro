import unittest
import json
from pathlib import Path
import numpy as np
from quality_od import fit_sparse,round_transport,bounded_jobs
from prepare_quality_sources import activity


class QualityTests(unittest.TestCase):
    def test_proposed_answers_follow_official_schema_without_review_stamp(self):
        import jsonschema
        root=Path(__file__).resolve().parent
        draft=json.loads((root/'data-quality.proposed.json').read_text())
        jsonschema.validate(draft,json.loads((root/'sources/registry_data_quality_schema.json').read_text()))
        self.assertEqual(draft['provenance']['method'],'self-reported')
        self.assertIsNone(draft['provenance']['reviewed_by'])

    def test_both_integer_margins_and_structural_zeros(self):
        rows=np.array([0,0,1,1,2,2]);cols=np.array([0,1,1,2,0,2])
        rt=np.array([13,7,11]);ct=np.array([8,12,11])
        v=fit_sparse(rows,cols,[1,5,2,4,3,9],rt,ct)
        result=round_transport(rows,cols,v,rt,ct)
        np.testing.assert_array_equal(np.bincount(rows,weights=result),rt)
        np.testing.assert_array_equal(np.bincount(cols,weights=result),ct)
        self.assertTrue(np.all(abs(result-v)<1+1e-8))

    def test_zero_rows_and_columns(self):
        rr,cc=np.indices((3,3));rr=rr.ravel();cc=cc.ravel()
        rt=[0,6,4];ct=[3,0,7]
        v=fit_sparse(rr,cc,np.ones(9),rt,ct)
        out=round_transport(rr,cc,v,rt,ct)
        np.testing.assert_array_equal(np.bincount(rr,weights=out),rt)
        np.testing.assert_array_equal(np.bincount(cc,weights=out),ct)

    def test_incompatible_margins_rejected(self):
        with self.assertRaises(ValueError):fit_sparse([0],[0],[1],[2],[3])
        with self.assertRaises(ValueError):fit_sparse([0],[0],[1],[5000000],[5000001])

    def test_unsupported_positive_origin_rejected(self):
        with self.assertRaises(ValueError):fit_sparse([0],[0],[1],[1,1],[2])

    def test_containment_bounds(self):
        diagonal=np.array([70,20,10]);off=np.array([10,20,30])
        result=bounded_jobs(np.array([140,10,10]),diagonal,off)
        self.assertEqual(result.sum(),160)
        self.assertTrue(np.all(result>=diagonal))
        self.assertTrue(np.all(result<=diagonal+off.sum()-off))

    def test_unknown_activity_is_not_agriculture(self):
        self.assertEqual(activity('0000000'),'other')
        self.assertEqual(activity('8610101'),'health')
        self.assertEqual(activity('4711302'),'retail')


if __name__=='__main__':unittest.main()
