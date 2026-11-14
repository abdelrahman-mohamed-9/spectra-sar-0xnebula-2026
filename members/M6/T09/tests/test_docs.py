import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class DocsTests(unittest.TestCase):
    def test_docs_links(self): self.assertEqual([],load('check_docs').check())
    def test_reject_unsafe_archive(self):
        m=load('assemble_member6')
        with self.assertRaises(ValueError): m.normalize('T01/../../bad.txt',1) if False else self._normalize_parts(m)
    def _normalize_parts(self,m):
        # validate unsafe path using real plan, not just prefix matching
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            for n in range(1,9):
                with zipfile.ZipFile(base/f'SPECTRA-SAR_M6_Phase1_T{n:02d}.zip','w') as z:
                    z.writestr(f'T{n:02d}/ok.txt','safe')
                    if n==1: z.writestr('T01/../../evil.txt','unsafe')
            return m.plan(base,base/'repo')
    def test_canonical_archive_plan(self):
        m=load('assemble_member6')
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            for n in range(1,9):
                with zipfile.ZipFile(base/f'SPECTRA-SAR_M6_Phase1_T{n:02d}.zip','w') as z:
                    pref=f'SPECTRA-SAR/M6/Phase-1/T{n:02d}/' if n in [2,3,5] else f'T{n:02d}/'
                    z.writestr(pref+'README.md','hi')
            steps=m.plan(base,base/'repo')
            self.assertEqual(8,len(steps))
            self.assertTrue(all('/M6/Phase-1/T' in str(s[-1]) for s in steps))

if __name__=='__main__':unittest.main()
