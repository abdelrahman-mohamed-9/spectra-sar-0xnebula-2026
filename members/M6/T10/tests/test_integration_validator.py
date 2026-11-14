import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration_validator import TASK_FILES, check_local, check_live_api, check_database, check_evidence, report, Result, render_md

class Tests(unittest.TestCase):
    def test_missing_task_fail(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(len(check_local(Path(td))),9)
            self.assertTrue(all(x.status=='FAIL' for x in check_local(Path(td))))
    def test_all_required_files_pass(self):
        with tempfile.TemporaryDirectory() as td:
            for t,files in TASK_FILES.items():
                for f in files:
                    path=Path(td)/t/f;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('ok')
            self.assertTrue(all(x.status=='PASS' for x in check_local(Path(td))))
    def test_api_without_url_blocked(self): self.assertEqual(check_live_api(None).status,'BLOCKED')
    def test_api_unsafe_url_rejected(self): self.assertEqual(check_live_api('http://example.org').status,'FAIL')
    def test_db_no_config_blocked(self): self.assertEqual(check_database(None).status,'BLOCKED')
    def test_no_evidence_blocked(self): self.assertEqual(len(check_evidence(None,None)),8)
    def test_manifest_malformed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'manifest.json';p.write_text('oops')
            self.assertEqual(check_evidence(p,None)[0].status,'FAIL')
    def test_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'proof.txt').write_text('provider scene record checked')
            sha=hashlib.sha256((root/'proof.txt').read_bytes()).hexdigest()
            m=root/'manifest.json';m.write_text(json.dumps({'records':{'e2e.M1':{'path':'proof.txt','sha256':sha}}}))
            self.assertEqual(check_evidence(m,root)[0].status,'PASS')
            (root/'proof.txt').write_text('tampered')
            self.assertEqual(check_evidence(m,root)[0].status,'FAIL')
    def test_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'root';root.mkdir();m=Path(td)/'manifest.json'
            m.write_text(json.dumps({'records':{'e2e.M1':{'path':'../outside','sha256':'0'*64}}}))
            self.assertEqual(check_evidence(m,root)[0].status,'FAIL')
    def test_report_blocked(self):self.assertEqual(report([Result('a','PASS',''),Result('b','BLOCKED','')])['overall'],'BLOCKED')
    def test_report_failed(self):self.assertEqual(report([Result('a','FAIL','')])['overall'],'FAIL')
    def test_report_success(self):self.assertEqual(report([Result('a','PASS','')])['overall'],'PASS')
    def test_md_render(self):self.assertIn('PASS',render_md(report([Result('a','PASS','fine')])) )

if __name__=='__main__':unittest.main()
