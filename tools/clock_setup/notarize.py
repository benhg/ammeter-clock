"""Verify Developer ID signing, notarize, staple and assess; resumable after lock/network loss."""
import argparse,json,subprocess,tempfile,time,hashlib
from pathlib import Path

def notarize(app,profile,resume=None):
    app=Path(app).resolve();record=app.parent/'notarization.json'
    info=subprocess.run(['codesign','-dv','--verbose=4',str(app)],capture_output=True,text=True,check=True)
    if 'Authority=Developer ID Application:' not in info.stderr or 'runtime' not in info.stderr:
        raise RuntimeError('Build with MACOS_SIGNING_IDENTITY="Developer ID Application: …" first. Development/ad-hoc signatures cannot be notarized.')
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    digest=hashlib.sha256((app/'Contents/_CodeSignature/CodeResources').read_bytes()).hexdigest()
    if resume:
        previous=json.loads(record.read_text()) if record.exists() else {}
        if previous.get('id')!=resume:raise RuntimeError('Resume ID does not match this app’s submission record')
        if previous.get('resources_sha256',digest)!=digest:raise RuntimeError('The app changed since submission; submit the new build instead')
        submitted=dict(previous,resources_sha256=digest)
    else:
        with tempfile.TemporaryDirectory(prefix='clock-notary-') as tmp:
            archive=Path(tmp)/'Clock.zip'
            subprocess.run(['ditto','-c','-k','--keepParent',str(app),str(archive)],check=True)
            reply=subprocess.run(['xcrun','notarytool','submit',str(archive),'--keychain-profile',profile,'--output-format','json'],capture_output=True,text=True,check=True)
            submitted=dict(json.loads(reply.stdout),resources_sha256=digest)
    record.write_text(json.dumps(submitted,indent=2))
    print('Apple notarization submission: '+submitted['id'],flush=True)
    deadline=time.monotonic()+86400;last=None
    while True:
        try:
            reply=subprocess.run(['xcrun','notarytool','info',submitted['id'],'--keychain-profile',profile,'--output-format','json'],capture_output=True,text=True,timeout=60)
            result=json.loads(reply.stdout) if reply.returncode==0 else {}
        except (subprocess.TimeoutExpired,json.JSONDecodeError):result={}
        status=result.get('status','Waiting for Keychain or Apple connectivity')
        if status!=last:print(status,flush=True);last=status
        if result:
            result['resources_sha256']=digest;record.write_text(json.dumps(result,indent=2))
        if status=='Accepted':break
        if status in ('Invalid','Rejected'):raise RuntimeError('Apple rejected submission '+submitted['id']+'; inspect its notary log')
        if time.monotonic()>=deadline:raise RuntimeError('Notarization still pending; resume with --resume-id '+submitted['id'])
        time.sleep(30)
    if hashlib.sha256((app/'Contents/_CodeSignature/CodeResources').read_bytes()).hexdigest()!=digest:raise RuntimeError('The app changed while notarization was pending')
    subprocess.run(['xcrun','stapler','staple',str(app)],check=True)
    subprocess.run(['xcrun','stapler','validate',str(app)],check=True)
    subprocess.run(['spctl','--assess','--type','execute','--verbose=2',str(app)],check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('app');p.add_argument('--profile',required=True);p.add_argument('--resume-id');a=p.parse_args();notarize(a.app,a.profile,a.resume_id)
