import sys,unittest,contextlib,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reconcile_binius_v18 import assert_current_state,run
class ReconciliationStateTests(unittest.TestCase):
 def test_known_base_and_idempotent_output_are_allowed(self):
  for current in [('base portfolio','base packet'),('new portfolio','new packet')]:
   assert_current_state(current,('base portfolio','base packet'),('new portfolio','new packet'))
 def test_intervening_or_partial_changes_cannot_be_overwritten(self):
  for current in [('another portfolio','base packet'),('new portfolio','base packet')]:
   with self.assertRaises(ValueError):assert_current_state(current,('base portfolio','base packet'),('new portfolio','new packet'))

 def test_current_packet_reproduces_from_exact_three_version_native_evidence(self):
  with contextlib.redirect_stdout(io.StringIO()):run(check=True)
