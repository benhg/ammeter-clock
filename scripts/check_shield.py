"""Verify actual PCB header positions and signals against official Uno R3 CAD.
Run with KiCad 8 bundled Python. Does not establish physical stack height.
"""
import json,math
from pathlib import Path
import pcbnew as pcb
root=Path(__file__).resolve().parents[1]
import os
PROJECT=Path(os.environ.get("AMMETER_PROJECT_DIR",str(root)))
DATA=PROJECT if "AMMETER_PROJECT_DIR" in os.environ else root/"hardware"
m=json.loads((root/'hardware/uno-r3-mechanical.json').read_text())
b=pcb.LoadBoard(str(PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb'))
fps={fp.GetReference():fp for fp in b.GetFootprints()}
maprefs={'POWER':'J1','AD':'J7','IOL':'J8','IOH':'J9'}
used={'POWER':{'5':'+5V','6':'GND','7':'GND'},'AD':{'5':'SDA','6':'SCL'},'IOL':{'3':'BTN_H','4':'BTN_M'},'IOH':{'7':'GND','9':'SDA','10':'SCL'}}
count=0;max_error=0
for header,ref in maprefs.items():
 pads={p.GetNumber():p for p in fps[ref].Pads()}
 assert len(pads)==len(m['headers'][header]),ref
 for entry in m['headers'][header]:
  p=pads[entry['pad']];pos=p.GetPosition();xy=(pcb.ToMM(pos.x),pcb.ToMM(pos.y));target=tuple(50+x for x in entry['position_mm'])
  err=math.dist(xy,target);assert err<.001,(ref,entry['pad'],xy,target)
  max_error=max(max_error,err);count+=1
  expected=used[header].get(entry['pad'])
  assert p.GetNetname()==('/'+expected if expected else ''),(ref,entry['pad'],p.GetNetname(),expected)
for i,(x,y,diameter) in enumerate(m['holes'],1):
 fp=fps['H'+str(i)];pos=fp.GetPosition();assert math.dist((pcb.ToMM(pos.x),pcb.ToMM(pos.y)),(50+x,50+y))<.001
 pad=list(fp.Pads())[0];assert pad.GetAttribute()==pcb.PAD_ATTRIB_NPTH
 assert abs(pcb.ToMM(pad.GetDrillSize().x)-diameter)<.001
# The famous offset is 4.064mm, not the normal 2.54mm grid spacing.
p7=next(p for p in fps['J8'].Pads() if p.GetNumber()=='8').GetPosition()
p8=next(p for p in fps['J9'].Pads() if p.GetNumber()=='1').GetPosition()
assert abs(pcb.ToMM(p7.x-p8.x)-4.064)<.001
assert len([z for z in b.Zones() if z.GetIsRuleArea()])==6,'USB, jack and both ICSP exclusion areas required'
result=f'PASS: all {count} Uno R3 header pins, four 3.2mm mounting holes, pin assignments and 4.064mm header offset match official CAD. Maximum coordinate error {max_error:.6f}mm. Four underside connector keepouts plus two-layer R4 antenna keepout present. Physical stacking clearance remains untested.\n'
(PROJECT/'reports/shield-mechanical-check.txt').write_text(result);print(result,end='')
