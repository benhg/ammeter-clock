"""Configure an ephemeral GitHub runner, never a user's login keychain."""
import base64,os,secrets,subprocess
from pathlib import Path

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise RuntimeError('This helper is only for ephemeral GitHub Actions runners')
    names=['APPLE_CERTIFICATE_P12_BASE64','APPLE_CERTIFICATE_PASSWORD','APPLE_ID','APPLE_TEAM_ID','APPLE_APP_SPECIFIC_PASSWORD','MACOS_SIGNING_IDENTITY']
    missing=[n for n in names if not os.environ.get(n)]
    if missing:raise RuntimeError('Signed macOS releases require GitHub secrets: '+', '.join(missing))
    root=Path(os.environ['RUNNER_TEMP']);keychain=root/'clock-signing.keychain-db';certificate=root/'clock-signing.p12';password=secrets.token_urlsafe(32)
    def run(args):
        result=subprocess.run(args,capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Signing setup failed at '+args[0]+' '+args[1]+'. Check certificate and notarization credentials.')
    certificate.write_bytes(base64.b64decode(os.environ['APPLE_CERTIFICATE_P12_BASE64'],validate=True));certificate.chmod(0o600)
    try:
        run(['security','create-keychain','-p',password,str(keychain)])
        run(['security','set-keychain-settings','-lut','21600',str(keychain)])
        run(['security','unlock-keychain','-p',password,str(keychain)])
        run(['security','import',str(certificate),'-k',str(keychain),'-P',os.environ['APPLE_CERTIFICATE_PASSWORD'],'-T','/usr/bin/codesign'])
        run(['security','set-key-partition-list','-S','apple-tool:,apple:,codesign:','-s','-k',password,str(keychain)])
        run(['security','list-keychains','-d','user','-s',str(keychain)])
        run(['xcrun','notarytool','store-credentials','clock-notary','--apple-id',os.environ['APPLE_ID'],'--team-id',os.environ['APPLE_TEAM_ID'],'--password',os.environ['APPLE_APP_SPECIFIC_PASSWORD']])
        with open(os.environ['GITHUB_ENV'],'a') as f:f.write('MACOS_NOTARY_PROFILE=clock-notary\nMACOS_SIGNING_IDENTITY='+os.environ['MACOS_SIGNING_IDENTITY']+'\n')
    finally:certificate.unlink(missing_ok=True)

if __name__=='__main__':main()
