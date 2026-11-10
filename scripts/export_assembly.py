"""Export purchasing BOM and vendor-neutral assembly placements for Rev F4.
Run with Python 3. Uses the actual PCB via KiCad CLI; does not change the board.
"""
import csv,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import os
PROJECT=Path(os.environ.get('AMMETER_PROJECT_DIR',str(ROOT)))
DATA=PROJECT if 'AMMETER_PROJECT_DIR' in os.environ else ROOT/'hardware'
OUT=DATA/'fabrication';OUT.mkdir(exist_ok=True)
parts=json.loads((DATA/'design.json').read_text())['parts']
parts={p['ref']:p for p in parts if p['typ']!='MOUNT'}
sourcing=json.loads((DATA/'sourcing.json').read_text())['parts']
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
KICAD_PY='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3'
subprocess.run([CLI,'pcb','export','pos','--format','csv','--units','mm','--side','both','-o',str(OUT/'kicad-positions.csv'),str(PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb')],check=True)
with (OUT/'kicad-positions.csv').open() as f:positions=list(csv.DictReader(f))
assert {p['Ref'] for p in positions}==set(parts),'Placement export differs from design manifest'
center_process=subprocess.run([KICAD_PY,str(ROOT/'scripts/export_fp_centers.py'),str(PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb')],check=True,capture_output=True,text=True)
centers=json.loads(center_process.stdout)
assert set(parts)<=set(centers),'Footprint centroid export differs from design manifest'
centers={ref:centers[ref] for ref in parts}
SMT={r for r,p in parts.items() if p['fp'].startswith(('Package_','Resistor_SMD:','Capacitor_SMD:','Inductor_SMD:'))}

def write(path,fields,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def source(ref):
 s=sourcing[ref];return s['manufacturer'],s['mpn'],s['source']

purchasing=[]
assembly=[]
for ref,p in parts.items():
 maker,mpn,url=source(ref)
 method='SMT' if ref in SMT else 'Assembler through-hole'
 if ref=='J6':method='Assembler through-hole (RTC header)'
 value='1x3 elevated female socket for customer Pololu module' if ref=='U4' else p['value']
 note=sourcing[ref]['notes'] if ref=='U4' else p['note']
 if ref in sourcing and ref!='U4':note+='; '+sourcing[ref]['notes']
 assembly.append(dict(Reference=ref,Quantity=1,Value=value,Footprint=p['fp'],Manufacturer=maker,MPN=mpn,Source=url,Assembly=method,Notes=note))
 purchasing.append(dict(Designators=ref,Quantity=1,Unit='piece',Value=value,Footprint=p['fp'],Manufacturer=maker,MPN=mpn,Source=url,Assembly=method,Notes=note))
fields=['Designators','Quantity','Unit','Value','Footprint','Manufacturer','MPN','Source','Assembly','Notes']
customer=[dict(Item='U4 module (customer fitted)',Quantity=1,Manufacturer='Pololu',MPN='U3V16F15',Source='https://www.pololu.com/product/4946',Installation='Customer solders supplied male header to module, then plugs into assembler-fitted U4 socket; component side up; disconnect USB first.')]
write(OUT/'customer-parts.csv',['Item','Quantity','Manufacturer','MPN','Source','Installation'],customer)
write(DATA/'bom.csv',fields,purchasing)
write(OUT/'bom.csv',fields,purchasing)
write(OUT/'bom-assembly.csv',['Reference','Quantity','Value','Footprint','Manufacturer','MPN','Source','Assembly','Notes'],assembly)

# KiCad absolute Y is negative. Normalize to Uno outline bottom-left:
# CAD origin (50mm,103.34mm); X increases right, Y increases upward.
# Use each part's pin-pattern center for CPL Mid X/Mid Y; pin 1 remains
# separately available in kicad-positions.csv for orientation review.
cpl=[];smt=[]
header_refs={'J1','J6','J7','J8','J9'}
for row in positions:
 ref=row['Ref'];maker,mpn,url=source(ref)
 cx,cy=centers[ref]
 x=cx-50;y=103.34-cy
 # KiCad's native header footprints are rotated to make their pin rows match
 # the Uno geometry. JLC's selected catalog models use a horizontal row at
 # zero degrees, so these single-row parts need zero in the vendor CPL.
 angle=0.0 if ref in header_refs else float(row['Rot'])%360
 # JLC OPA197IDR model at zero has pin 1 at lower left and leads top/bottom.
 # 270 degrees CCW places pin 1 at PCB pad 1 (upper left), with side leads.
 if ref=='U3':angle=270.0
 assert 0<=x<=68.58 and 0<=y<=53.34,(ref,x,y)
 cpl.append(dict(Designator=ref,**{'X (mm)':f'{x:.6f}','Y (mm)':f'{y:.6f}','Layer':row['Side'],'Rotation (deg)':f'{angle:.6f}','Assembly':'SMT' if ref in SMT else ('Assembler through-hole (RTC header)' if ref=='J6' else 'Assembler through-hole'),'MPN':mpn}))
 if ref in SMT:
  smt.append({'Designator':ref,'Mid X':f'{x:.6f}mm','Mid Y':f'{y:.6f}mm','Layer':row['Side'],'Rotation':f'{angle:.6f}'})
write(OUT/'cpl.csv',['Designator','X (mm)','Y (mm)','Layer','Rotation (deg)','Assembly','MPN'],cpl)
write(OUT/'cpl-smt.csv',['Designator','Mid X','Mid Y','Layer','Rotation'],smt)
write(OUT/'bom-smt.csv',['Designator','Quantity','Value','Package','Manufacturer','MPN'],[dict(Designator=ref,Quantity=1,Value=parts[ref]['value'],Package=parts[ref]['fp'],Manufacturer=source(ref)[0],MPN=source(ref)[1]) for ref in SMT])
assert len(smt)==len(SMT)
print(f'Exported {len(cpl)} full assembly positions and {len(smt)} SMT positions; R1 and all four header placements included; U4 is socket only, Pololu module is customer fitted.')
