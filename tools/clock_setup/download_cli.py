"""Fetch a pinned official Arduino CLI and verify its release checksum."""
import hashlib
import io
from pathlib import Path
import platform
import tarfile
import urllib.request
import zipfile

VERSION = '1.5.1'

def download(destination):
    system, arch = platform.system(), platform.machine().lower()
    suffix = {'Windows':'Windows_64bit.zip','Linux':'Linux_64bit.tar.gz',
              'Darwin':'macOS_ARM64.tar.gz' if arch in ('arm64','aarch64') else 'macOS_64bit.tar.gz'}[system]
    name = f'arduino-cli_{VERSION}_{suffix}'
    base = f'https://github.com/arduino/arduino-cli/releases/download/v{VERSION}/'
    def get(url):
        with urllib.request.urlopen(url,timeout=120) as response: return response.read()
    checksums = get(base+f'{VERSION}-checksums.txt').decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1].lstrip('*') == name)
    data = get(base+name)
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Arduino CLI checksum mismatch')
    executable = 'arduino-cli.exe' if system == 'Windows' else 'arduino-cli'
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            member = next(n for n in archive.namelist() if Path(n).name == executable)
            binary = archive.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
            member = next(m for m in archive.getmembers() if m.isfile() and Path(m.name).name == executable)
            binary = archive.extractfile(member).read()
    destination = Path(destination); destination.mkdir(parents=True,exist_ok=True)
    target = destination / executable; target.write_bytes(binary); target.chmod(0o755)
    # Ship vendor license alongside its executable.
    (destination/'ARDUINO-CLI-LICENSE.txt').write_bytes(get('https://raw.githubusercontent.com/arduino/arduino-cli/v'+VERSION+'/LICENSE.txt'))
    print(f'Verified Arduino CLI {VERSION}: {target}')

if __name__ == '__main__':
    import sys
    download(sys.argv[1] if len(sys.argv)>1 else '.tools/package-bin')
