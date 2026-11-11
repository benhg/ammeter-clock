"""Verify Developer ID signing, notarize with a Keychain profile, staple and assess."""
import argparse,json,subprocess,tempfile
from pathlib import Path

def notarize(app,profile):
    app=Path(app).resolve()
    info=subprocess.run(['codesign','-dv','--verbose=4',str(app)],capture_output=True,text=True,check=True)
    if 'Authority=Developer ID Application:' not in info.stderr or 'runtime' not in info.stderr:
        raise RuntimeError('Build with MACOS_SIGNING_IDENTITY="Developer ID Application: …" first. Development/ad-hoc signatures cannot be notarized.')
    subprocess.run(['codesign','--verify','--deep','--strict','--verbose=2',str(app)],check=True)
    with tempfile.TemporaryDirectory(prefix='clock-notary-') as tmp:
        archive=Path(tmp)/'Clock.zip'
        subprocess.run(['ditto','-c','-k','--keepParent',str(app),str(archive)],check=True)
        reply=subprocess.run(['xcrun','notarytool','submit',str(archive),'--keychain-profile',profile,'--output-format','json'],capture_output=True,text=True,check=True)
        submitted=json.loads(reply.stdout)
        (app.parent/'notarization.json').write_text(json.dumps(submitted,indent=2))
        print('Apple notarization submission: '+submitted['id'],flush=True)
        reply=subprocess.run(['xcrun','notarytool','wait',submitted['id'],'--keychain-profile',profile,'--output-format','json'],capture_output=True,text=True,check=True)
        result=json.loads(reply.stdout)
        (app.parent/'notarization.json').write_text(json.dumps(result,indent=2))
        if result.get('status')!='Accepted':raise RuntimeError('Notarization not accepted. Submission ID: '+result.get('id','unknown'))
    subprocess.run(['xcrun','stapler','staple',str(app)],check=True)
    subprocess.run(['xcrun','stapler','validate',str(app)],check=True)
    subprocess.run(['spctl','--assess','--type','execute','--verbose=2',str(app)],check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('app');p.add_argument('--profile',required=True);a=p.parse_args();notarize(a.app,a.profile)
