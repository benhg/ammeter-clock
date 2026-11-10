"""Export the isolated Rev2 prototype. Requires KiCad Python and passing checks."""
from pathlib import Path
import pcbnew as p
import subprocess,json,hashlib,csv,zipfile,tempfile,os,shutil
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'hardware/rev2';OUT=PROJECT/'fabrication';OUT.mkdir(exist_ok=True)
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';BOARD=PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb'
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def call(*args):subprocess.run([CLI,*map(str,args)],check=True)
for report in ['results/summary.json','protection-results/summary.json']:
 s=json.loads((PROJECT/'simulations'/report).read_text());assert s['revision']=='2' and s['source_board_sha256']==sha(BOARD)
 assert s.get('failed_case_count',s.get('rejected'))==0
call('pcb','drc','--exit-code-violations','-o',PROJECT/'reports/board-drc.txt',BOARD)
call('sch','erc','--exit-code-violations','-o',PROJECT/'reports/schematic-erc.txt',PROJECT/'ammeter-clock/ammeter-clock.kicad_sch')
env=dict(os.environ,AMMETER_PROJECT_DIR=str(PROJECT))
subprocess.run([__import__('sys').executable,str(ROOT/'scripts/export_assembly.py')],env=env,check=True)
def read(name):
 with (OUT/name).open() as f:return list(csv.DictReader(f))
def write(name,fields,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
parts=read('bom-assembly.csv');positions=read('cpl.csv');source=json.loads((PROJECT/'sourcing.json').read_text())['parts']
assert len(parts)==len(positions)==28
assert {x['Reference'] for x in parts}=={x['Designator'] for x in positions}
write('JLCPCB-BOM-REV2.csv',['Comment','Designator','Footprint','LCSC Part #'],[{'Comment':source[x['Reference']]['mpn'],'Designator':x['Reference'],'Footprint':x['Footprint'].split(':')[-1],'LCSC Part #':source[x['Reference']]['lcsc']} for x in parts])
write('JLCPCB-CPL-REV2.csv',['Designator','Mid X','Mid Y','Layer','Rotation'],[{'Designator':x['Designator'],'Mid X':x['X (mm)']+'mm','Mid Y':x['Y (mm)']+'mm','Layer':x['Layer'],'Rotation':x['Rotation (deg)']} for x in positions])
gerbers=OUT/'gerbers-rev2';gerbers.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='ammeter-rev2-') as tmp:
 q=Path(tmp)/'ammeter-clock-rev2.kicad_pcb';b=p.LoadBoard(str(BOARD));b.GetDesignSettings().SetAuxOrigin(p.VECTOR2I(p.FromMM(50),p.FromMM(103.34)));p.SaveBoard(str(q),b)
 call('pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,B.Paste,Edge.Cuts','--use-drill-file-origin','--subtract-soldermask','-o',str(gerbers)+'/',q)
 call('pcb','export','drill','--format','excellon','--drill-origin','plot','--excellon-separate-th','--excellon-units','mm','-o',str(gerbers)+'/',q)
files=sorted(gerbers.iterdir());assert len([f for f in files if f.suffix=='.drl'])==2
with zipfile.ZipFile(OUT/'ammeter-clock-rev2-gerbers.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in files:z.write(f,f.name)
notes='''AMMETER CLOCK / KN6UBF — REV2 PROTOTYPE
Two layers, 68.58 x 53.34 mm, 1.6 mm FR4. All 28 assembler placements
are fitted from TOP: 6 SMT and 22 through-hole. Use the REV2 BOM/CPL pair.
U4 is the female socket only. Customer supplies the Pololu U3V16F15 module.
R10/J10 add the seconds output; J5 is rotated 180 degrees from Rev F4.
J10 pin1 is +, pin2 GND; both minute and second meters must be 0–100 uA.
CPL uses pin-pattern centers, origin CAD (50,103.34), X right, Y up.
Vendor-model rotation overrides: J1/J6/J7/J8/J9=0; U3=270 degrees.
Verify vendor pin1 registration, connector wire-entry orientation and polarities.
Existing F4 catalogue part choices are reused. Stock has NOT been rechecked or
reserved for this revision. Full THT assembly requires the vendor's agreement.
ERC/DRC/netlist and simulated interfaces pass. Rev2 itself has not been built;
new terminal access, stack fit, startup and seconds needle motion need bench checks.
The Pololu converter startup and actual DAC power-on state are not simulated.
'''
(OUT/'UPLOAD-INSTRUCTIONS.txt').write_text(notes)
manifest=dict(revision='2',status='PROTOTYPE_NOT_BENCH_VALIDATED',source_board_sha256=sha(BOARD),source_schematic_sha256=sha(PROJECT/'ammeter-clock/ammeter-clock.kicad_sch'),layers=2,board_mm=[68.58,53.34],origin_kicad_mm=[50,103.34],assembly_counts=dict(SMT=6,THT=22,total=28,side='top'),stock='Not reverified',files={f.name:sha(f) for f in files},assembly_files={n:sha(OUT/n) for n in ['JLCPCB-BOM-REV2.csv','JLCPCB-CPL-REV2.csv']})
(OUT/'manufacturing-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(OUT/'ammeter-clock-rev2-fabrication.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in ['ammeter-clock-rev2-gerbers.zip','JLCPCB-BOM-REV2.csv','JLCPCB-CPL-REV2.csv','bom.csv','bom-assembly.csv','cpl.csv','customer-parts.csv','UPLOAD-INSTRUCTIONS.txt','manufacturing-manifest.json']:z.write(OUT/n,n)
 for n in ['board-drc.txt','schematic-erc.txt','netlist-check.txt','shield-mechanical-check.txt','r4-wifi-compatibility-check.txt']:z.write(PROJECT/'reports'/n,'checks/'+n)
 for n in ['results/summary.json','results/seconds_corners.csv','protection-results/summary.json']:z.write(PROJECT/'simulations'/n,'simulations/'+n)
print('Rev2: 28 placements; matching Gerber/drill/CPL origins; fabrication archive complete.')
