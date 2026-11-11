"""Build on each target OS; PyInstaller does not cross-compile."""
from pathlib import Path
import platform
import os
import json
import subprocess
import sys
import tarfile
import zipfile
from download_cli import download

ROOT = Path(__file__).resolve().parents[2]

def main():
    output = ROOT/'dist-clock'
    output.mkdir(exist_ok=True)
    # Desktop/iCloud metadata can invalidate signatures during a build.
    staging=Path.home()/'Library/Caches/KN6UBFClockSetup/dist' if platform.system()=='Darwin' else output
    staging.mkdir(parents=True,exist_ok=True)
    binary = ROOT/'.tools/package-bin'
    download(binary)
    args = [sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
            '--name','KN6UBF Clock Setup','--distpath',str(staging),
            '--workpath',str(ROOT/'.build-clock'),'--specpath',str(ROOT/'.build-clock'),
            '--hidden-import','serial','--collect-submodules','serial',
            '--add-data',f'{ROOT/"firmware/AmmeterClock"}:firmware/AmmeterClock',
            '--add-binary',f'{binary/("arduino-cli.exe" if platform.system()=="Windows" else "arduino-cli")}:bin',
            '--add-data',f'{binary/"ARDUINO-CLI-LICENSE.txt"}:bin',
            '--add-data',f'{ROOT/"tools/clock_setup/licenses"}:licenses']
    if platform.system() in ('Darwin','Windows'): args += ['--windowed']
    if platform.system()=='Darwin': args += ['--osx-bundle-identifier','cloud.glick.kn6ubf-clock-setup']
    if platform.system()=='Darwin' and os.environ.get('MACOS_SIGNING_IDENTITY'):
        args += ['--codesign-identity',os.environ['MACOS_SIGNING_IDENTITY']]
    args += [str(ROOT/'tools/clock_setup/native_app.py')]
    subprocess.run(args,check=True,cwd=ROOT)
    name = 'KN6UBF Clock Setup'
    system = platform.system()
    arch = 'arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64'
    artifact = f'clock-setup-{dict(Darwin="macOS",Windows="Windows",Linux="Linux")[system]}-{arch}'
    if system == 'Darwin':
        target=staging/(name+'.app')
        # Remove only Finder/resource-fork metadata from build output. Never
        # remove quarantine flags or bypass Gatekeeper.
        subprocess.run(['chflags','-R','nohidden',str(target)],check=True)
        for attribute in ('com.apple.FinderInfo','com.apple.ResourceFork'):
            subprocess.run(['xattr','-r','-d',attribute,str(target)],check=True)
        identity=os.environ.get('MACOS_SIGNING_IDENTITY','-')
        signing=['codesign','--force','--sign',identity]
        if identity!='-':signing+=['--options','runtime','--timestamp']
        subprocess.run(signing+[str(target)],check=True)
        subprocess.run(['codesign','--verify','--deep','--strict',str(target)],check=True)
        if os.environ.get('MACOS_NOTARY_PROFILE'):
            subprocess.run([sys.executable,str(ROOT/'tools/clock_setup/notarize.py'),str(target),'--profile',os.environ['MACOS_NOTARY_PROFILE']],check=True)
        subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(target),str(output/(artifact+'.zip'))],check=True)
    elif system == 'Windows':
        target=output/name
        with zipfile.ZipFile(output/(artifact+'.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(target.rglob('*')):
                if file.is_file(): archive.write(file,file.relative_to(output))
    else:
        target=output/name
        with tarfile.open(output/(artifact+'.tar.gz'),'w:gz') as archive: archive.add(target,arcname=name)
    executable = target/'Contents/MacOS'/name if system=='Darwin' else target/(name+'.exe' if system=='Windows' else name)
    (output/'build-result.json').write_text(json.dumps(dict(executable=str(executable),app=str(target))))
    print('SMOKE_EXECUTABLE='+str(executable))

if __name__=='__main__': main()
