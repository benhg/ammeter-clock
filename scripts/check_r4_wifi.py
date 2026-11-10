"""Compare Rev F PCB to extracted official Arduino R4 WiFi CAD coordinates.
Run using KiCad 8 bundled Python. Does not certify stack height or RF performance.
"""
from pathlib import Path
import json,math,pcbnew as pcb
ROOT=Path(__file__).resolve().parents[1]
import os
PROJECT=Path(os.environ.get("AMMETER_PROJECT_DIR",str(ROOT)))
DATA=PROJECT if "AMMETER_PROJECT_DIR" in os.environ else ROOT/"hardware"
m=json.loads((ROOT/'hardware/uno-r4-wifi-mechanical.json').read_text())
b=pcb.LoadBoard(str(PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb'))
fps={f.GetReference():f for f in b.GetFootprints()}
def pos(p):return [pcb.ToMM(p.GetPosition().x),pcb.ToMM(p.GetPosition().y)]
def pad(ref,num):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(num))
source={h:{int(p['pin']):p for p in pins} for h,pins in m['headers'].items()}
assignments=[('J1',i,'JANALOG',i) for i in range(1,9)]+[('J7',i,'JANALOG',i+8) for i in range(1,7)]+[('J8',i,'JDIGITAL',i) for i in range(1,9)]+[('J9',i,'JDIGITAL',i+8) for i in range(1,11)]
errors=[math.dist(pos(pad(ref,n)),source[h][i]['xy_shield_mm']) for ref,n,h,i in assignments]
assert max(errors)<.001,max(errors)
for xy in m['holes_xy_shield_mm']:assert min(math.dist(pos(next(iter(fps['H'+str(i)].Pads()))),xy) for i in range(1,5))<.001
for ref,n,net in [('J1',5,'+5V'),('J1',6,'GND'),('J1',7,'GND'),('J7',5,'SDA'),('J7',6,'SCL'),('J9',9,'SDA'),('J9',10,'SCL'),('J8',3,'BTN_H'),('J8',4,'BTN_M')]:assert pad(ref,n).GetNetname()=='/'+net
# R4 power-header pin 1 is BOOT/MD, not R3 reserved: leave it electrically open.
assert pad('J1',1).GetNetCode()==0
# R4 ESP header footprint is fully inside expanded bottom exclusion.
d=json.loads((DATA/'design.json').read_text())
ko={x[0]:x[1:] for x in d['keepouts']}
x0,y0,x1,y1=ko['ICSP USB / R4 ESP header'];a,c,e,f=m['component_bounds_shield_mm']['J6']
assert x0<=a and y0<=c and x1>=e and y1>=f
x0,y0,x1,y1=ko['R4 WiFi antenna']
for fp in b.GetFootprints():
 for p in fp.Pads():
  if p.GetAttribute()==pcb.PAD_ATTRIB_NPTH:continue
  x,y=pos(p);assert not(x0<=x<=x1 and y0<=y<=y1),(fp.GetReference(),p.GetNumber())
# R4 barrel jack extends past the rectangular native keepout at a mounting hole.
# Check actual electrical pads under its full CAD bounds, excluding board features.
a,c,e,f=m['component_bounds_shield_mm']['J5']
for fp in b.GetFootprints():
 for p in fp.Pads():
  if p.GetAttribute()==pcb.PAD_ATTRIB_NPTH:continue
  x,y=pos(p);assert not(a<=x<=e and c<=y<=f),(fp.GetReference(),p.GetNumber())
result=f'PASS: 32 R4 WiFi shield header coordinates and four mounting holes match (max error {max(errors):.6f} mm). Used signals map to 5V/GND, Wire SDA/SCL, D2/D3. BOOT/MD contact left unconnected. ESP header covered by expanded exclusion; antenna region has no component pads. Physical stack height and WiFi RF behavior require bench verification.\n'
(PROJECT/'reports/r4-wifi-compatibility-check.txt').write_text(result);print(result,end='')
