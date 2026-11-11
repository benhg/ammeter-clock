import sys,json,tempfile,unittest,subprocess,contextlib,io
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/clock_setup'))
import notarize

class NotarizationTests(unittest.TestCase):
 def test_resume_retries_locked_keychain_without_resubmitting(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=Path(tmp)/'Clock.app';resources=app/'Contents/_CodeSignature/CodeResources';resources.parent.mkdir(parents=True);resources.write_bytes(b'signed resources')
   record=app.parent/'notarization.json';record.write_text(json.dumps(dict(id='existing')))
   calls=[];replies=[subprocess.TimeoutExpired('notarytool',60),None,'In Progress','Accepted']
   def run(args,**kwargs):
    calls.append(args)
    if args[:2]==['codesign','-dv']:return subprocess.CompletedProcess(args,0,'','Authority=Developer ID Application: test\nruntime')
    if args[:3]==['xcrun','notarytool','info']:
     status=replies.pop(0)
     if isinstance(status,Exception):raise status
     return subprocess.CompletedProcess(args,69 if status is None else 0,json.dumps(dict(id='existing',status=status)) if status else '','')
    return subprocess.CompletedProcess(args,0,'','')
   with patch.object(notarize.subprocess,'run',side_effect=run),patch.object(notarize.time,'sleep') as sleep,contextlib.redirect_stdout(io.StringIO()):
    notarize.notarize(app,'profile','existing')
   self.assertEqual(sleep.call_count,3);self.assertEqual(json.loads(record.read_text())['status'],'Accepted')
   self.assertFalse(any('submit' in call for call in calls));self.assertTrue(any(call[:3]==['xcrun','stapler','validate'] for call in calls))
 def test_resume_rejects_changed_app(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=Path(tmp)/'Clock.app';resources=app/'Contents/_CodeSignature/CodeResources';resources.parent.mkdir(parents=True);resources.write_bytes(b'changed')
   (app.parent/'notarization.json').write_text(json.dumps(dict(id='existing',resources_sha256='wrong')))
   def run(args,**kwargs):return subprocess.CompletedProcess(args,0,'','Authority=Developer ID Application: test runtime')
   with patch.object(notarize.subprocess,'run',side_effect=run),self.assertRaisesRegex(RuntimeError,'changed'):notarize.notarize(app,'profile','existing')
if __name__=='__main__':unittest.main()
