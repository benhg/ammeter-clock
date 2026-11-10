"""One-time local routing of Rev F4 R2/C6 replacements.
KiCad DRC is authoritative; never treat router success as fabrication approval.
Run once with KiCad bundled Python after the F4 footprint replacement. No third-party modules.
"""
import pcbnew as pcb
from pathlib import Path
from array import array
import heapq,math,time,json
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'hardware/rev2/ammeter-clock/ammeter-clock.kicad_pcb'
b=pcb.LoadBoard(str(P));mm=pcb.FromMM
STEP=.1;X0=50;Y0=50;W=687;H=535;N=W*H
occ=[array('Q',[0])*N,array('Q',[0])*N]
ALL=(1<<63)
pads={};padmap={};holes=[];existing_vias={}
def grid(x,y):return (round((x-X0)/STEP),round((y-Y0)/STEP))
def actual(g):return (X0+g[0]*STEP,Y0+g[1]*STEP)
def bits(net):return 1<<net

def rect(layer,cx,cy,hx,hy,mask):
 x0=max(0,math.floor((cx-hx-X0)/STEP));x1=min(W-1,math.ceil((cx+hx-X0)/STEP))
 y0=max(0,math.floor((cy-hy-Y0)/STEP));y1=min(H-1,math.ceil((cy+hy-Y0)/STEP))
 for y in range(y0,y1+1):
  for x in range(x0,x1+1):
   if abs(X0+x*STEP-cx)<=hx and abs(Y0+y*STEP-cy)<=hy:occ[layer][y*W+x]|=mask

def disk(layer,cx,cy,r,mask):
 x0=max(0,math.floor((cx-r-X0)/STEP));x1=min(W-1,math.ceil((cx+r-X0)/STEP))
 y0=max(0,math.floor((cy-r-Y0)/STEP));y1=min(H-1,math.ceil((cy+r-Y0)/STEP))
 for y in range(y0,y1+1):
  for x in range(x0,x1+1):
   if (X0+x*STEP-cx)**2+(Y0+y*STEP-cy)**2 <= r*r:occ[layer][y*W+x]|=mask

for fp in b.GetFootprints():
 for p in fp.Pads():
  pos=p.GetPosition();cx=pcb.ToMM(pos.x);cy=pcb.ToMM(pos.y)
  size=p.GetSize();hx=pcb.ToMM(size.x)/2;hy=pcb.ToMM(size.y)/2
  if abs(p.GetOrientationDegrees()%180-90)<1: hx,hy=hy,hx
  net=p.GetNetCode();mask=bits(net) if net else ALL
  if p.GetAttribute()!=pcb.PAD_ATTRIB_SMD:
   holes.append((cx,cy,pcb.ToMM(p.GetDrillSize().x)/2))
  layers=[0,1] if p.GetAttribute()!=pcb.PAD_ATTRIB_SMD else [0]
  if net:
   rec=dict(x=cx,y=cy,g=grid(cx,cy),layers=layers,p=p,ref=fp.GetReference(),num=p.GetNumber(),centerx=pcb.ToMM(fp.GetPosition().x))
   pads.setdefault(net,[]).append(rec);padmap[(fp.GetReference(),p.GetNumber())]=rec
  for l in layers:rect(l,cx,cy,hx+.30,hy+.30,mask)
  if not net:
   for l in [0,1]:rect(l,cx,cy,hx+.30,hy+.30,ALL)
# Rasterize the actual Uno outline, preserving the board-edge clearance even
# around its asymmetric right edge and chamfered corner segments.
design=json.loads((ROOT/'hardware/rev2/design.json').read_text())
mechanical=json.loads((ROOT/'hardware/uno-r3-mechanical.json').read_text())
edges=[(tuple(50+c for c in e['start']),tuple(50+c for c in e['end'])) for e in mechanical['outline']]
def inside(x,y):
 n=0
 for (ax,ay),(cx,cy) in edges:
  if (ay>y)!=(cy>y) and x<ax+(cx-ax)*(y-ay)/(cy-ay):n+=1
 return n%2==1

def edge_distance(x,y,a,c):
 dx=c[0]-a[0];dy=c[1]-a[1]
 u=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
 return (x-a[0]-u*dx)**2+(y-a[1]-u*dy)**2
for gy in range(H):
 y=Y0+gy*STEP
 for gx in range(W):
  x=X0+gx*STEP
  if not inside(x,y) or min(edge_distance(x,y,a,c) for a,c in edges)<.7**2:
   for l in [0,1]:occ[l][gy*W+gx]|=ALL
# Reserve bottom copper over the Uno's metal connector shells and ICSP pins.
for name,x0,y0,x1,y1 in design['keepouts']:
 rect(1,(x0+x1)/2,(y0+y1)/2,(x1-x0)/2+.18,(y1-y0)/2+.18,ALL)
 if name=='R4 WiFi antenna':rect(0,(x0+x1)/2,(y0+y1)/2,(x1-x0)/2+.18,(y1-y0)/2+.18,ALL)
# No front routing under the elevated boost module body, except socket pins.
# Rev G has no module-body routing exclusion.

D=[(1,0,10),(-1,0,10),(0,1,10),(0,-1,10),(1,1,14),(1,-1,14),(-1,1,14),(-1,-1,14)]

def route(start,end,net):
 mask=bits(net);foreign=~mask
 tx,ty=end['g'];sx,sy=start['g']
 targets={l*N+ty*W+tx for l in end['layers']}
 def heuristic(x,y):
  dx=abs(tx-x);dy=abs(ty-y);return 10*max(dx,dy)+4*min(dx,dy)
 heap=[];dist={};prev={}
 for l in start['layers']:
  n=l*N+sy*W+sx;dist[n]=0;heapq.heappush(heap,(heuristic(sx,sy),0,n))
 found=None;cnt=0
 while heap:
  _,cost,node=heapq.heappop(heap)
  if dist.get(node)!=cost:continue
  if node in targets:found=node;break
  cnt+=1
  if cnt>650000:break
  l=node//N;i=node%N;y,x=divmod(i,W)
  for dx,dy,c in D:
   nx=x+dx;ny=y+dy
   if not(0<=nx<W and 0<=ny<H):continue
   j=ny*W+nx
   if occ[l][j]&foreign:continue
   if dx and dy and ((occ[l][y*W+nx]&foreign) or (occ[l][ny*W+x]&foreign)):continue
   nxt=l*N+j;nc=cost+c
   if nc<dist.get(nxt,10**12):
    dist[nxt]=nc;prev[nxt]=node
    heapq.heappush(heap,(nc+int(heuristic(nx,ny)*1.10),nc,nxt))
  # Extra radial clearance for a 0.6mm via; copper mask already includes trace
  # radius/clearance. Check nearby cells on both layers before switching.
  other=1-l;safe=True
  for dl in [0,1]:
   for oy in range(-2,3):
    for ox in range(-2,3):
     if ox*ox+oy*oy>4:continue
     nx=x+ox;ny=y+oy
     if not(0<=nx<W and 0<=ny<H) or occ[dl][ny*W+nx]&foreign:safe=False;break
    if not safe:break
   if not safe:break
  if (x,y) in existing_vias and existing_vias[(x,y)]==net:
   safe=not ((occ[0][i]|occ[1][i])&foreign)
  if safe:
   cx,cy=actual((x,y))
   at_existing=(x,y) in existing_vias and existing_vias[(x,y)]==net
   if not at_existing:
    if any((cx-hx)**2+(cy-hy)**2 < (hr+.15+.28)**2 for hx,hy,hr in holes):safe=False
    if any((x-vx)**2+(y-vy)**2 < 36 for vx,vy in existing_vias):safe=False
  if safe:
   nxt=other*N+i;nc=cost+100
   if nc<dist.get(nxt,10**12):
    dist[nxt]=nc;prev[nxt]=node;heapq.heappush(heap,(nc+int(heuristic(x,y)*1.10),nc,nxt))
 if found is None:return None
 path=[];n=found
 while True:
  l=n//N;y,x=divmod(n%N,W);path.append((x,y,l))
  if n not in prev:break
  n=prev[n]
 return list(reversed(path))

# Existing routing is immutable obstacle copper for these two added links.
for t in b.GetTracks():
 net=t.GetNetCode();mask=bits(net)
 if isinstance(t,pcb.PCB_VIA):
  at=t.GetPosition();x,y=pcb.ToMM(at.x),pcb.ToMM(at.y)
  for l in [0,1]:disk(l,x,y,.67,mask)
  existing_vias[grid(x,y)]=net;holes.append((x,y,pcb.ToMM(t.GetDrill())/2))
 else:
  at,end=t.GetStart(),t.GetEnd();a=(pcb.ToMM(at.x),pcb.ToMM(at.y));c=(pcb.ToMM(end.x),pcb.ToMM(end.y));steps=max(1,math.ceil(math.dist(a,c)/.05));l=0 if t.GetLayer()==pcb.F_Cu else 1
  for i in range(steps+1):disk(l,a[0]+(c[0]-a[0])*i/steps,a[1]+(c[1]-a[1])*i/steps,.49,mask)
# Prevent adding via holes in SMD pads, including same-net pads.
for f in b.GetFootprints():
 for pad in f.Pads():
  if pad.GetAttribute()==pcb.PAD_ATTRIB_SMD:holes.append((pcb.ToMM(pad.GetPosition().x),pcb.ToMM(pad.GetPosition().y),.8))
track_count=0;via_count=0

def track(a,c,l,net,width=.20):
 global track_count
 if a==c:return
 t=pcb.PCB_TRACK(b);t.SetStart(pcb.VECTOR2I(mm(a[0]),mm(a[1])));t.SetEnd(pcb.VECTOR2I(mm(c[0]),mm(c[1])));t.SetWidth(mm(width));t.SetLayer(pcb.F_Cu if l==0 else pcb.B_Cu);t.SetNetCode(net);b.Add(t);track_count+=1
 steps=max(1,math.ceil(math.dist(a,c)/.05))
 for i in range(steps+1):disk(l,a[0]+(c[0]-a[0])*i/steps,a[1]+(c[1]-a[1])*i/steps,max(.49,width/2+.36),bits(net))

def apply(path,start,end,net):
 global via_count
 # Exact pad-center stubs ensure snap-to-grid introduces no open circuits.
 track((start['x'],start['y']),actual(path[0]),path[0][2],net)
 anchor=path[0];last=path[0];direction=None
 for pt in path[1:]:
  if pt[2]!=last[2]:
   track(actual(anchor),actual(last),last[2],net)
   x,y=actual(pt)
   if (pt[0],pt[1]) not in existing_vias:
    via=pcb.PCB_VIA(b);via.SetPosition(pcb.VECTOR2I(mm(x),mm(y)));via.SetWidth(mm(.6));via.SetDrill(mm(.3));via.SetViaType(pcb.VIATYPE_THROUGH);via.SetLayerPair(pcb.F_Cu,pcb.B_Cu);via.SetNetCode(net);b.Add(via);via_count+=1
    existing_vias[(pt[0],pt[1])]=net
   for l in [0,1]:disk(l,x,y,.67,bits(net))
   anchor=pt;direction=None
  else:
   new=(pt[0]-last[0],pt[1]-last[1])
   if direction is not None and new!=direction:
    track(actual(anchor),actual(last),last[2],net);anchor=last
   direction=new
  last=pt
 track(actual(anchor),actual(last),last[2],net)
 track(actual(last),(end['x'],end['y']),last[2],net)


links=[('U1','7','SEC_DAC',86,56,[0,1]),('R10','2','SEC_OUT',53,56,[0,1]),('J10','2','GND',68,68,[0,1])]
for branch in json.loads((ROOT/'hardware/rev2/reroute-endpoints.json').read_text()):
 pin='1' if branch['net']=='BTN_M' else '2'
 links.append(('J5',pin,branch['net'],*branch['xy'],[0 if branch['layer']==pcb.F_Cu else 1]))
for ref,pin,name,x,y,layers in links:
 net=b.FindNet('/'+name).GetNetCode();start=padmap[(ref,pin)]
 end=dict(x=x,y=y,g=grid(x,y),layers=layers)
 path=route(start,end,net)
 assert path,ref+' '+name+' cannot be routed'
 apply(path,start,end,net);print(ref,name,'routed',flush=True)
pcb.SaveBoard(str(P),b)
print('New tracks',track_count,'vias',via_count)
