import importlib.util,subprocess,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('diagnostic',Path(__file__).resolve().parents[1]/'native_diagnostic.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DiagnosticTests(unittest.TestCase):
 def test_timeout_is_evidence_not_an_exception(self):
  def timeout(*a,**kw):raise subprocess.TimeoutExpired(a[0],240,output=b'partial out',stderr=b'partial err')
  r=m.capture(['lean'],'/tmp',runner=timeout)
  self.assertEqual(r['status'],'timeout');self.assertIn('partial out',r['output'])
 def test_error_is_recorded(self):
  def missing(*a,**kw):raise FileNotFoundError('missing lean')
  self.assertEqual(m.capture(['lean'],'/tmp',runner=missing)['status'],'unavailable')
 def test_compiler_error_is_a_completed_diagnostic(self):
  def failed(*a,**kw):return subprocess.CompletedProcess(a[0],1,'type mismatch','')
  self.assertEqual(m.capture(['lean'],'/tmp',runner=failed)['returncode'],1)
if __name__=='__main__':unittest.main()
