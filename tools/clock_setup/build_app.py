"""Build on each target OS; PyInstaller does not cross-compile."""
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import zipfile
from download_cli import download

ROOT = Path(__file__).resolve().parents[2]

def main():
    output = ROOT/'dist-clock'
    binary = ROOT/'.tools/package-bin'
    download(binary)
    args = [sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
            '--name','KN6UBF Clock Setup','--distpath',str(output),
            '--workpath',str(ROOT/'.build-clock'),'--specpath',str(ROOT/'.build-clock'),
            '--hidden-import','serial','--collect-submodules','serial',
            '--add-data',f'{ROOT/"firmware/AmmeterClock"}:firmware/AmmeterClock',
            '--add-data',f'{binary}:bin']
    for name in ('index.html','app.js','web_serial.js','style.css'):
        args += ['--add-data',f'{ROOT/"tools/clock_setup"/name}:tools/clock_setup']
    if platform.system() in ('Darwin','Windows'): args += ['--windowed']
    if platform.system()=='Darwin': args += ['--osx-bundle-identifier','cloud.glick.kn6ubf-clock-setup']
    args += [str(ROOT/'tools/clock_setup/app.py')]
    subprocess.run(args,check=True,cwd=ROOT)
    name = 'KN6UBF Clock Setup'
    system = platform.system()
    arch = 'arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64'
    artifact = f'clock-setup-{dict(Darwin="macOS",Windows="Windows",Linux="Linux")[system]}-{arch}'
    if system == 'Darwin':
        target=output/(name+'.app')
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
    print('SMOKE_EXECUTABLE='+str(executable))

if __name__=='__main__': main()
