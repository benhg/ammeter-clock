"""Check R9 current limiting with an explicit engineering clamp model.
This is not a manufacturer model of unpowered OPA197 behavior or Pololu startup.
"""
from pathlib import Path
import subprocess,json,hashlib,datetime,math,re
import os
source=Path(__file__).resolve().parent
project=Path(os.environ.get('AMMETER_PROJECT_DIR',str(source.parent))).resolve()
data=project if 'AMMETER_PROJECT_DIR' in os.environ else project/'hardware'
root=project/'simulations' if 'AMMETER_PROJECT_DIR' in os.environ else source
out=root/'protection-results';out.mkdir(parents=True,exist_ok=True)
j=json.loads((data/'design.json').read_text());parts={p['ref']:p for p in j['parts']}
assert j['revision'] in ['F4','2'] and parts['R9']['nets']=={'1':'HOUR_DAC','2':'HOUR_AMP_IN'} and parts['U3']['nets']['3']=='HOUR_AMP_IN'
cases=[]
for dac in [3.75,4.095,5.25]:
 for tol in [-.01,.01]:
  name=f'input_{dac}_{tol}';res=4700*(1+tol)
  text=f'''R9 protection - assumed 0.3V diode plus 1ohm dynamic resistance
Vdac dac 0 {dac}
Vrail rail 0 PWL(0 0 1m 0 11m 15 15m 15 25m 0 30m 0)
Rinput dac pin {res}
Bclamp pin rail I=max((V(pin)-V(rail)-.3),0)
Rleak pin 0 1G
.control
set wr_singlescale
set wr_vecnames
tran 10u 30m 0 10u
wrdata protection-results/{name}.dat v(rail) v(pin) i(Vdac)
quit
.endc
.end
'''
  deck=out/(name+'.cir');deck.write_text(text);q=subprocess.run(['ngspice','-b',str(deck.relative_to(root))],cwd=root,capture_output=True,text=True,timeout=10);log=q.stdout+q.stderr;(out/(name+'.log')).write_text(log)
  assert q.returncode==0 and not re.search(r'timestep too small|analysis aborted|simulation\(s\) aborted|^Error',log,re.M|re.I)
  rows=[list(map(float,l.split())) for l in (out/(name+'.dat')).read_text().splitlines()[1:]];assert rows[-1][0]>=.03
  current=max(-r[3] for r in rows);bound=dac/res;assert current<=bound*1.001
  cases.append(dict(dac_V=dac,resistance_ohm=res,peak_current_A=current,conservative_zero_drop_bound_A=bound))
summary=dict(revision=j['revision'],verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_board_sha256=hashlib.sha256((project/'ammeter-clock/ammeter-clock.kicad_pcb').read_bytes()).hexdigest(),accepted=len(cases),rejected=0,cases=cases,bound_at_5_25V_minus_1pct_A=5.25/4653,bound_including_assumed_total_minus_2pct_A=5.25/4606,max_resistor_power_W=5.25**2/4653,scope='Resistor current limiting only; 0.3V/1ohm engineering clamp, imposed rail ramp. Not a simulation of actual unpowered OPA197, input voltage stress, Pololu startup or needle motion.')
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
