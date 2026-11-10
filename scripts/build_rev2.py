"""Fork the verified F4 board into Rev2; run once, never overwrite the F4 source.
Run with KiCad Python. Routing is completed separately by route_rev2.py.
"""
from pathlib import Path
import json,re,uuid,shutil,hashlib,copy
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'hardware/rev2';PROJECT=OUT/'ammeter-clock'
source=ROOT/'ammeter-clock';target=PROJECT/'ammeter-clock.kicad_pcb'
assert not target.exists(),'Rev2 exists; edit it instead of rebuilding over your changes'
for name in ['ammeter-clock.kicad_pcb','ammeter-clock.kicad_sch','ammeter-clock.kicad_pro','AmmeterClock.kicad_sym','sym-lib-table','fp-lib-table']:
 shutil.copy2(source/name,PROJECT/name)
shutil.copytree(source/'AmmeterClock.pretty',PROJECT/'AmmeterClock.pretty',dirs_exist_ok=True)
design=json.loads((ROOT/'hardware/design.json').read_text());design['revision']='2';design['based_on']='F4';design['source_f4_sha256']=hashlib.sha256((source/'ammeter-clock.kicad_pcb').read_bytes()).hexdigest()
parts={x['ref']:x for x in design['parts']};uid=lambda:str(uuid.uuid4())
for old,new,net1,net2,xy,sch,rot in [('R3','R10','SEC_DAC','SEC_OUT',[86,56],[185.42,260.35],0),('J3','J10','SEC_OUT','GND',[53,56],[327.66,260.35],0)]:
 item=copy.deepcopy(parts[old]);item.update(ref=new,nets={'1':net1,'2':net2},xy=xy,sch=sch,rot=rot,uuid=uid())
 if new=='J10':item['value']='SECOND_100uA'
 item['note']='Seconds output; matches minute circuit. '+item['note'];design['parts'].append(item);parts[new]=item
parts['U1']['nets']['7']='SEC_DAC';parts['U1']['note']='DAC D/pin9=hours, C/pin8=minutes, B/pin7=seconds; A/pin6 unused. Internal 2.048V reference, gain2, LDAC grounded.'
parts['J5']['xy']=[83.3,92];parts['J5']['rot']=180;parts['J5']['note']+=' Rev2: rotated around body center so wire openings face the open center corridor, away from the power header; keep wiring corridor clear.'
(OUT/'design.json').write_text(json.dumps(design,indent=2)+'\n')
sourcing=json.loads((ROOT/'hardware/sourcing.json').read_text());sourcing['revision']='2'
for new,old in [('R10','R3'),('J10','J3')]:
 sourcing['parts'][new]=copy.deepcopy(sourcing['parts'][old]);sourcing['parts'][new]['status']='Existing F4 part choice reused; live stock not reverified for Rev2'
(OUT/'sourcing.json').write_text(json.dumps(sourcing,indent=2)+'\n')
# Balanced block helper, respecting quoted strings.
def endblock(text,start):
 depth=0;quoted=False;escape=False
 for i in range(start,len(text)):
  c=text[i]
  if escape:escape=False;continue
  if c=='\\' and quoted:escape=True;continue
  if c=='"':quoted=not quoted
  if not quoted:
   if c=='(':depth+=1
   elif c==')':
    depth-=1
    if depth==0:return i+1
 raise ValueError('Unbalanced KiCad expression')
def fix_dac_names(text):
 replacements=[]
 for match in re.finditer(r'\(pin output line',text):
  end=endblock(text,match.start());block=text[match.start():end]
  number=re.search(r'\(number "([6-9])"',block)
  if number and 'VOUT_' in block:
   block=re.sub(r'\(name "VOUT_[A-D]"', '(name "VOUT_'+{'6':'A','7':'B','8':'C','9':'D'}[number[1]]+'"',block)
   replacements.append((match.start(),end,block))
 for a,b,value in reversed(replacements):text=text[:a]+value+text[b:]
 return text
sch=(PROJECT/'ammeter-clock.kicad_sch').read_text();starts=list(re.finditer(r'\(symbol \(lib_id "AmmeterClock:Clock_\w+"\)',sch))
for old,new in [('R3','R10'),('J3','J10')]:
 candidates=[]
 for i,m in enumerate(starts):
  block=sch[m.start():starts[i+1].start() if i+1<len(starts) else len(sch)-2]
  if '(property "Reference" "'+old+'"' in block:candidates.append(block)
 assert len(candidates)==1,old
 block=candidates[0];oldpart=parts[old];newpart=parts[new];dx=newpart['sch'][0]-oldpart['sch'][0];dy=newpart['sch'][1]-oldpart['sch'][1]
 def move(m):return '('+m[1]+' '+str(round(float(m[2])+dx,6))+' '+str(round(float(m[3])+dy,6))
 block=re.sub(r'\((at|xy) (-?[\d.]+) (-?[\d.]+)',move,block)
 block=block.replace('"'+old+'"','"'+new+'"').replace('"'+oldpart['value']+'"','"'+newpart['value']+'"')
 for a,b in zip(oldpart['nets'].values(),newpart['nets'].values()):
  if a!=b:block=block.replace('"'+a+'"','"'+b+'"')
 oldid=oldpart['uuid'];newid=newpart['uuid']
 block=re.sub(r'\(uuid ([0-9a-f-]+)\)',lambda m:'(uuid '+(newid if m[1]==oldid else uid())+')',block)
 sch=sch.rstrip()[:-1]+block+'\n)\n'
# Replace U1's pin7 NC with the seconds net label (same geometry as original generator).
x,y=parts['U1']['sch'];px=x-15.24;py=y-((10-1)*1.27-6*2.54)
for m in list(re.finditer(r'\(no_connect \(at (-?[\d.]+) (-?[\d.]+)\)',sch)):
 if abs(float(m[1])-px)<.001 and abs(float(m[2])-py)<.001:
  end=endblock(sch,m.start());replacement=f'(wire (pts (xy {px} {py}) (xy {px-5.08} {py})) (stroke (width 0) (type default)) (uuid {uid()}))\n(label "SEC_DAC" (at {px-5.08} {py} 0) (effects (font (size 1.016 1.016)) (justify left bottom)) (uuid {uid()}))'
  sch=sch[:m.start()]+replacement+sch[end:];break
else:raise ValueError('U1 pin7 no-connect not found')
sch=re.sub(r'\(rev "[^"]+"\)','(rev "2")',sch, count=1)
sch=sch.replace('100 uA minute meter','100 uA minute and second meters')
(PROJECT/'ammeter-clock.kicad_sch').write_text(fix_dac_names(sch))
lib=PROJECT/'AmmeterClock.kicad_sym';lib.write_text(fix_dac_names(lib.read_text()))
b=p.LoadBoard(str(target));mm=p.FromMM;v=lambda x,y:p.VECTOR2I(mm(x),mm(y));fps={f.GetReference():f for f in b.GetFootprints()}
for name in ['SEC_DAC','SEC_OUT']:
 net=p.NETINFO_ITEM(b,'/'+name);b.Add(net)
for new,old in [('R10','R3'),('J10','J3')]:
 fp=fps[old].Duplicate();fp.SetReference(new);fp.SetValue(parts[new]['value']);fp.SetPosition(v(*parts[new]['xy']));fp.SetOrientationDegrees(parts[new]['rot']);path=p.KIID_PATH();path.push_back(p.KIID(design['root_uuid']));path.push_back(p.KIID(parts[new]['uuid']));fp.SetPath(path);b.Add(fp);fps[new]=fp
 for pad in fp.Pads():pad.SetNet(b.FindNet('/'+parts[new]['nets'][pad.GetNumber()]))
 for g in [fp.Reference(),fp.Value()]:g.SetVisible(False)
next(pad for pad in fps['U1'].Pads() if pad.GetNumber()=='7').SetNet(b.FindNet('/SEC_DAC'))
# Remove only the branches ending at J5; retain their distant endpoints for rerouting.
branches=[];removed=[]
for t in list(b.GetTracks()):
 if isinstance(t,p.PCB_VIA):continue
 a,c=t.GetStart(),t.GetEnd();xy=[p.ToMM(a.x),p.ToMM(a.y),p.ToMM(c.x),p.ToMM(c.y)]
 if any(abs(xy[i]-x)<.01 and abs(xy[i+1]-92)<.01 for i in [0,2] for x in [78.3,83.3]):
  if (a-c).EuclideanNorm()>mm(.01):
   end=(xy[2:4] if abs(xy[1]-92)<.01 and xy[0] in [78.3,83.3] else xy[:2])
   branches.append({'net':t.GetNetname().strip('/'),'xy':end,'layer':t.GetLayer()})
  b.RemoveNative(t);removed.append(t)
fps['J5'].SetOrientationDegrees(180);fps['J5'].SetPosition(v(83.3,92))
(OUT/'reroute-endpoints.json').write_text(json.dumps(branches,indent=2)+'\n')
# Clear duplicated/conflicting old silk labels near J5 and add explicit user-facing labels.
for drawing in list(b.GetDrawings()):
 if isinstance(drawing,p.PCB_TEXT):
  txt=drawing.GetText()
  if txt.startswith('AMMETER CLOCK'):drawing.SetText('AMMETER CLOCK / KN6UBF / REV2');drawing.SetPosition(v(55,82));drawing.SetTextAngle(p.EDA_ANGLE(90,p.DEGREES_T));drawing.SetTextSize(v(.9,.9))
for ref in ['J5','J10','R10']:fps[ref].Reference().SetVisible(False)
def label(text,x,y,size=.8):
 t=p.PCB_TEXT(b);t.SetText(text);t.SetPosition(v(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(mm(.12));t.SetLayer(p.F_SilkS);b.Add(t)
label('SECONDS',55.8,60.5,.8);label('+',53,53.8,.8);label('-',58,53.8,.8);label('R10',90,56,.8)
label('WIRE IN',80.8,86.6,.8)
b.GetTitleBlock().SetRevision('2')
p.SaveBoard(str(target),b)
print('Forked F4 into hardware/rev2. Added R10/J10, seconds on DAC B/pin7, rotated J5. Routing pending.')
