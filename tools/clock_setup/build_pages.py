"""Build the static Pages site from the same UI used by the desktop app."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]

def main():
    source=ROOT/'tools/clock_setup'; output=ROOT/'_site-clock'
    output.mkdir(exist_ok=True)
    for name in ('index.html','app.js','web_serial.js','style.css'):
        shutil.copyfile(source/name,output/name)
    (output/'.nojekyll').touch()
    print(output)

if __name__=='__main__':main()
