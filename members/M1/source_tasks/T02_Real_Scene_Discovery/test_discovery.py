"""Local logic tests only; fake metadata here are NOT real satellite observations."""
import datetime as dt
import unittest
import discover_scenes as d

class TestDiscovery(unittest.TestCase):
    def test_nisar_name_parser(self):
        name = 'NISAR_L2_PR_GCOV_023_105_A_017_4005_DHDH_A_20260621T111906_20260621T111941_P05023_N_F_J_001.h5'
        x = d.parse_gcov_granule_name(name)
        self.assertEqual(x['track'], '105')
        self.assertEqual(x['frame'], '017')
        self.assertEqual(x['polarization_code'], 'DHDH')

    def test_pair_with_matching_metadata(self):
        base = {'name_metadata': {'track':'105','frame':'017','direction':'A','mode':'4005','polarization_code':'DHDH'}, 'maturity':'PROVISIONAL'}
        a = dict(base, granule_id='TEST_BEFORE', acquisition_start_utc='2026-08-12T12:00:00Z')
        b = dict(base, granule_id='TEST_AFTER', acquisition_start_utc='2026-08-14T12:00:00Z')
        out = d.pair_gcov([a,b])
        self.assertEqual(len(out),1)
        self.assertTrue(out[0]['known_flood_event_window'])

    def test_reject_mixed_maturities(self):
        base = {'name_metadata': {'track':'105','frame':'017','direction':'A','mode':'4005','polarization_code':'DHDH'}}
        a = dict(base, granule_id='TEST_BEFORE', maturity='PROVISIONAL', acquisition_start_utc='2026-09-01T12:00:00Z')
        b = dict(base, granule_id='TEST_AFTER', maturity='VALIDATED', acquisition_start_utc='2026-11-01T12:00:00Z')
        self.assertEqual(d.pair_gcov([a,b]),[])

    def test_nonmatching_polarization(self):
        a = {'name_metadata': {'track':'105','frame':'017','direction':'A','mode':'4005','polarization_code':'DHDH'}, 'maturity':'PROVISIONAL','acquisition_start_utc':'2026-09-01T12:00:00Z'}
        b = {'name_metadata': dict(a['name_metadata'],polarization_code='DVVV'), 'maturity':'PROVISIONAL','acquisition_start_utc':'2026-09-20T12:00:00Z'}
        self.assertEqual(d.pair_gcov([a,b]),[])

if __name__ == '__main__': unittest.main()
