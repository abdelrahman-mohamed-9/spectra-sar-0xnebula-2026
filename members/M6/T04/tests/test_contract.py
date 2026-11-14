import pathlib
import unittest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load((ROOT / 'api-contract.yaml').read_text())

    def test_openapi_version(self):
        self.assertEqual(self.doc['openapi'], '3.1.0')

    def test_required_endpoints(self):
        routes = self.doc['paths']
        for route, method in [('/api/v1/runs', 'post'), ('/api/v1/runs/{run_id}', 'get'),
                              ('/api/v1/runs/{run_id}/results', 'get'),
                              ('/api/v1/runs/{run_id}/lineage', 'get'),
                              ('/api/v1/assets/{asset_id}', 'get'), ('/health/ready','get')]:
            with self.subTest(route=route):
                self.assertIn(method, routes[route])

    def test_all_internal_refs_resolve(self):
        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == '$ref':
                        self.assertTrue(v.startswith('#/'))
                        target = self.doc
                        for token in v[2:].split('/'):
                            target = target[token.replace('~1','/').replace('~0','~')]
                        self.assertIsNotNone(target)
                    else:
                        walk(v)
            elif isinstance(node, list):
                for item in node: walk(item)
        walk(self.doc)

    def test_request_rejects_extra_fields(self):
        create = self.doc['components']['schemas']['CreateRunRequest']
        self.assertFalse(create['additionalProperties'])
        self.assertIn('scene_before_id', create['required'])
        self.assertIn('scene_after_id', create['required'])

    def test_security_and_health(self):
        self.assertEqual(self.doc['security'], [{'bearerAuth': []}])
        self.assertEqual(self.doc['paths']['/health/ready']['get']['security'], [])

    def test_result_confidence(self):
        fields = self.doc['components']['schemas']['ResultResponse']['properties']['change']['properties']
        self.assertIn('not_provided', fields['confidence_interpretation']['enum'])

    def test_no_internal_uri_in_public_asset(self):
        fields = self.doc['components']['schemas']['AssetResponse']['properties']
        self.assertNotIn('storage_uri', fields)

if __name__ == '__main__':
    unittest.main()
