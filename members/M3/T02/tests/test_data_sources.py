import io
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from geo_sources import load_aoi, bbox, overpass_query, DataSourceError
from data_fetcher import osm_element_to_feature, fetch_worldpop, fetch_osm

AOI={'type':'Polygon','coordinates':[[[30,30],[30.01,30],[30.01,30.01],[30,30.01],[30,30]]]}
class FakeResponse:
    def __init__(self, data, headers=None): self.data=data; self.headers=headers or {}; self.status_code=200
    def raise_for_status(self): pass
    def iter_content(self, chunk_size=65536): yield self.data
    def close(self): pass
class FakeSession:
    def __init__(self, data, headers=None): self.data=data; self.headers=headers or {}; self.calls=[]
    def request(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        return FakeResponse(self.data,self.headers)
class Tests(unittest.TestCase):
    def test_aoi_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'aoi.json';p.write_text(json.dumps(AOI))
            self.assertEqual(load_aoi(p), AOI)
        self.assertEqual(bbox(AOI),(30,30,30.01,30.01))
        self.assertIn('way["building"]',overpass_query(AOI))
    def test_bad_aoi(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text(json.dumps({'type':'Point','coordinates':[0,0]}))
            with self.assertRaises(DataSourceError):load_aoi(p)
    def test_osm_conversion(self):
        f=osm_element_to_feature({'type':'way','id':12,'tags':{'building':'yes'},'geometry':[{'lon':1,'lat':1},{'lon':2,'lat':1},{'lon':2,'lat':2},{'lon':1,'lat':1}]})
        self.assertEqual(f['geometry']['type'],'Polygon')
        self.assertEqual(f['id'],'way/12')
    def test_osm_mock_network(self):
        payload=json.dumps({'osm3s':{'timestamp_osm_base':'2025-10-01T00:00:00Z'},'elements':[{'type':'node','id':1,'lat':30,'lon':30,'tags':{'amenity':'hospital'}}]}).encode()
        with tempfile.TemporaryDirectory() as d:
            s=FakeSession(payload); result=fetch_osm(AOI,Path(d),session=s)
            self.assertEqual(result['metadata']['exported_features'],1)
            self.assertEqual(s.calls[0][0],'POST')
            self.assertTrue(Path(d,'osm_features.geojson').exists())
    def test_worldpop_mock_network(self):
        with tempfile.TemporaryDirectory() as d:
            s=FakeSession(b'II*\x00'+b'0'*50, {'X-Total-Population':'123.4'})
            result=fetch_worldpop(AOI,Path(d),2025,session=s)
            self.assertEqual(result['metadata']['population_total_header'],'123.4')
            self.assertEqual(s.calls[0][2]['json']['year'],2025)
    def test_worldpop_refuses_json_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(DataSourceError):
                fetch_worldpop(AOI,Path(d),2025,session=FakeSession(b'{"error":"no"}'))
            self.assertFalse(Path(d,'worldpop_population_2025_100m.tif').exists())
if __name__=='__main__': unittest.main()
