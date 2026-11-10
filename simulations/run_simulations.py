"""Run reproducible ngspice simulations for the Rev F4 meter interfaces.
Requires ngspice on PATH. Standard-library Python; plot_results.py is optional.
"""
from pathlib import Path
import subprocess,csv,json,re,itertools,math,hashlib,datetime
import os,shutil
SOURCE=Path(__file__).resolve().parent
PROJECT=Path(os.environ.get('AMMETER_PROJECT_DIR',str(SOURCE.parent))).resolve()
DATA=PROJECT if 'AMMETER_PROJECT_DIR' in os.environ else PROJECT/'hardware'
ROOT=PROJECT/'simulations' if 'AMMETER_PROJECT_DIR' in os.environ else SOURCE
ROOT.mkdir(exist_ok=True)
if ROOT!=SOURCE:
 shutil.copytree(SOURCE/'models',ROOT/'models',dirs_exist_ok=True)
 shutil.copy2(SOURCE/'.spiceinit',ROOT/'.spiceinit')
RESULT=ROOT/'results';RESULT.mkdir(exist_ok=True)
for stale in RESULT.glob('*'):
 if stale.suffix in ['.dat','.log','.csv','.json']:stale.unlink()
DECKS=ROOT/'decks';DECKS.mkdir(exist_ok=True)
design=json.loads((DATA/'design.json').read_text())
parts={p['ref']:p for p in design['parts']}
if design['revision'] in ['E','F','F1','F4','G']:
 assert parts['J4']['nets']==parts['SW1']['nets']=={'1':'BTN_H','2':'GND'}
 assert parts['J5']['nets']==parts['SW2']['nets']=={'1':'BTN_M','2':'GND'}
assert parts['R1']['value'].startswith('22k') and parts['R2']['value'].startswith('10k') and parts['R3']['value'].startswith('56k')
assert parts['R1']['nets']=={'1':'HOUR_OUT','2':'HOUR_FB'}
assert parts['R2']['nets']=={'1':'HOUR_FB','2':'GND'}
assert parts['R3']['nets']=={'1':'MIN_DAC','2':'MIN_OUT'}
assert parts['U1']['value']=='MCP4728-E/UN' and parts['U3']['value']=='OPA197ID'
assert parts['R6']['value'].startswith('47R') and parts['R6']['nets']=={'1':'AMP_DRIVE','2':'HOUR_OUT'}
assert parts['C6']['value'].startswith('1n') and parts['C6']['nets']=={'1':'AMP_DRIVE','2':'HOUR_FB'}
firmware=(SOURCE.parent/'firmware/AmmeterClock/ClockCore.h').read_text()
HCODE=int(re.search(r's.hourScale\s*=\s*(\d+)',firmware)[1])
MCODE=int(re.search(r's.minuteScale\s*=\s*(\d+)',firmware)[1])
assert parts['R9']['nets']=={'1':'HOUR_DAC','2':'HOUR_AMP_IN'} and parts['R9']['value']=='4.7k 1%'
assert parts['U3']['nets']['3']=='HOUR_AMP_IN'
model='.include models/OPAx197.LIB\n'
amp='Xd amp_in fb vp 0 drive OPAx197\nRprotect dac amp_in 4700\nRf out fb {rf}\nRg fb 0 {rg}\nRiso drive out 47\nCf drive fb 1n\nRmeter out 0 {load}\n'

def run(name,circuit,analysis,vectors):
 deck=f'{name}\n'+circuit+f'''\n.control
set wr_singlescale
set wr_vecnames
{analysis}
wrdata results/{name}.dat {' '.join(vectors)}
quit
.endc
.end
'''
 path=DECKS/(name+'.cir');path.write_text(deck)
 (RESULT/(name+'.dat')).unlink(missing_ok=True)
 p=subprocess.run(['ngspice','-b',str(path.relative_to(ROOT))],cwd=ROOT,text=True,capture_output=True,timeout=10)
 log=p.stdout+p.stderr;(RESULT/(name+'.log')).write_text(log)
 assert p.returncode==0 and not re.search(r'(?im)^\s*(error|fatal)|timestep too small|analysis aborted',log),(name,log[-2000:])
 data=RESULT/(name+'.dat');assert data.exists(),name
 rows=[list(map(float,line.split())) for line in data.read_text().splitlines()[1:] if line.strip()]
 assert rows and all(all(math.isfinite(v) for v in row) for row in rows),name
 return rows

def write(name,rows):
 if not rows:return
 with (RESULT/(name+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

# Macro-model is a nominal device, not a statistical/worst-case silicon model.
# 0.1% feedback resistor corners are explicit circuit corners only.
hour=[];failures=[]
for index,(usb,boost,load,tol) in enumerate(itertools.product([4.5,4.7,5.25],[14.4,15,15.6],[1000,2000,10000,100000],[-1,0,1])):
 rf=22000*(1+tol*.001);rg=10000*(1-tol*.001)
 circuit=model+f'Vboost vp 0 {boost}\nVdac dac 0 PWL(0 .3 1m .3 1.001m {4.096*HCODE/4096})\n'+amp.format(rf=rf,rg=rg,load=load)
 try:rows=run(f'hour_corner_{index:03}',circuit,'tran 10u 3m 0 10u',['v(out)','i(Vboost)'])
 except (AssertionError,subprocess.TimeoutExpired):
  failures.append(dict(case=f'hour_corner_{index:03}',reason='TI macro-model did not converge; no result accepted',meter_ohm=load));continue
 out,current=rows[-1][1:]
 hour.append(dict(usb_V=usb,boost_V=boost,meter_ohm=load,gain_corner=tol,output_V=out,error_vs_12_V=out-12,boost_current_mA=-current*1000))
write('hour_corners',hour)
for load in [1000,10000,100000]:
 try:run(f'hour_transfer_{load}',model+'Vboost vp 0 15\nVcmd dac 0 PWL(0 .05 1m .05 11m 4.096)\n'+amp.format(rf=22000,rg=10000,load=load),'tran 10u 12m 0 10u',['v(dac)','v(out)'])
 except (AssertionError,subprocess.TimeoutExpired):failures.append(dict(case=f'hour_transfer_{load}',reason='TI macro-model did not converge; no result accepted',meter_ohm=load))

# Minute DAC: ideal internal-reference source; no MCP4728 silicon/EEPROM model.
# Optional 20ohm series output resistance is a conservative sensitivity assumption only; datasheet typical is 1ohm.
minute=[]
for index,(usb,rs,coil,ro) in enumerate(itertools.product([4.5,4.7,5.25],[55440,56000,56560],[0,1000,10000],[0,20])):
 output_link='VoutputSense dac series 0' if ro==0 else f'Rout dac series {ro}'
 coil_link='VcoilSense meter 0 0' if coil==0 else f'Rcoil meter 0 {coil}'
 circuit=f'Vdac dac 0 {4.096*MCODE/4096}\n{output_link}\nRseries series meter {rs}\n{coil_link}\n'
 rows=run(f'minute_corner_{index:03}',circuit,'op',['i(Vdac)'])
 current=-rows[-1][1]*1e6
 minute.append(dict(usb_V=usb,series_ohm=rs,coil_ohm=coil,assumed_DAC_output_ohm=ro,current_uA=current))
write('minute_corners',minute)

# Seconds duplicates the minute branch; check all tolerance/coil corners together
# with both channels loaded. Independent ideal DAC sources do not model crosstalk.
seconds=[]
if design['revision']=='2':
 assert parts['R10']['nets']=={'1':'SEC_DAC','2':'SEC_OUT'} and parts['R10']['value'].startswith('56k')
 assert parts['U1']['nets']['7']=='SEC_DAC' and parts['J10']['nets']=={'1':'SEC_OUT','2':'GND'}
 for index,(rs,coil,ro) in enumerate(itertools.product([55440,56000,56560],[0,1000,10000],[0,20])):
  circuit=f'Vminute m 0 {4.096*MCODE/4096}\nRminute m 0 {rs+coil+ro}\nVsecond s 0 {4.096*MCODE/4096}\nRsecond s 0 {rs+coil+ro}\n'
  rows=run(f'simultaneous_second_{index:03}',circuit,'op',['i(Vminute)','i(Vsecond)'])
  m,s=rows[-1][1:];assert abs(m-s)<1e-12 and 0<=-s*1e6<75
  seconds.append(dict(series_ohm=rs,coil_ohm=coil,output_ohm=ro,minute_uA=-m*1e6,second_uA=-s*1e6))
 # Rollover, grounded output and maximum possible DAC command: resistor limits current.
 for name,voltage,load in [('rollover','PWL(0 4.095 1m 4.095 1.001m 0 2m 0)',56000),('short','4.095',55440)]:
  rows=run('seconds_'+name,f'Vsecond s 0 {voltage}\nRseries s 0 {load}\n','tran 1u 2m',['i(Vsecond)'])
  assert max(-r[1]*1e6 for r in rows)<75
  if name=='rollover':assert abs(rows[-1][1])<1e-12
 write('seconds_corners',seconds)

# Hour meter resistance and cable capacitance are not known: use broad cases.
step=[]
for load,cap in itertools.product([1000,2000,10000,100000],[1e-11,1e-9,1e-8,1e-7]):
 name=f'hour_step_{cap:g}' if load==100000 else f'hour_step_{load}_{cap:g}'
 circuit=model+'Vboost vp 0 15\nVdac dac 0 PWL(0 .4 1m .4 1.001m 3.75 3m 3.75 3.001m .4)\n'+amp.format(rf=22000,rg=10000,load=load)+f'Cload out 0 {cap}\n'
 try:rows=run(name,circuit,'tran 1u 5m 0 1u',['v(out)'])
 except (AssertionError,subprocess.TimeoutExpired):
  failures.append(dict(case=name,reason='TI macro-model did not converge; no result accepted',meter_ohm=load));continue
 late=[v for t,v in rows if .0025<t<.00295]
 step.append(dict(meter_ohm=load,load_cap_F=cap,high_mean_V=sum(late)/len(late),late_ripple_pp_V=max(late)-min(late),max_output_V=max(v for t,v in rows)))
write('step_summary',step)

# Distinguish command supply error from op-amp supply rejection.
ripple=[]
for rail in ['usb','boost']:
 circuit=model
 circuit+=('Vusb usb 0 SIN(5 .05 100)\nBdac dac 0 V=(.3+3.45*min(time/0.001,1)) + (V(usb)-5)*3.75*10^(-57/20)/5\nVboost vp 0 15\n' if rail=='usb' else 'Vdac dac 0 PWL(0 .3 1m .3 1.001m 3.75)\nVboost vp 0 SIN(15 .05 100)\n')
 circuit+=amp.format(rf=22000,rg=10000,load=100000)
 try:
  rows=run('ripple_'+rail,circuit,'tran 10u 50m 0 10u',['v(out)','v(vp)'])
  late=[r[1] for r in rows if r[0]>.03]
  ripple.append(dict(rail=rail,frequency_Hz=100,assumed_supply_ripple_pp_V=.1,output_ripple_pp_V=max(late)-min(late)))
 except (AssertionError,subprocess.TimeoutExpired):failures.append(dict(case='ripple_'+rail,reason='TI macro-model did not converge; no result accepted',meter_ohm=100000))

for frequency in [100000,1200000]:
 circuit=model+f'Vdac dac 0 PWL(0 .3 1m .3 1.001m 3.75)\nVboost vp 0 SIN(15 .05 {frequency})\n'+amp.format(rf=22000,rg=10000,load=100000)
 try:
  rows=run(f'ripple_boost_{frequency}',circuit,'tran 10n 300u 0 10n',['v(out)','v(vp)'])
  late=[r[1] for r in rows if r[0]>.0002]
  ripple.append(dict(rail='boost',frequency_Hz=frequency,assumed_supply_ripple_pp_V=.1,output_ripple_pp_V=max(late)-min(late)))
 except (AssertionError,subprocess.TimeoutExpired):failures.append(dict(case=f'ripple_boost_{frequency}',reason='TI macro-model did not converge; no result accepted',meter_ohm=100000))
write('ripple_summary',ripple)

# Converter startup and EEPROM power-on behavior require bench testing.
if failures:write('failed_cases',failures)

summary={'revision':design['revision'],'analysis_count':len(list(RESULT.glob('*.dat'))),'verified_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_board_sha256':hashlib.sha256((PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb').read_bytes()).hexdigest(),'engine':subprocess.check_output(['ngspice','--version'],text=True).splitlines()[1].strip(),'hour_code':HCODE,'minute_code':MCODE,
 'seconds_corner_count':len(seconds),'hour_corner_count':len(hour),'minute_corner_count':len(minute),
 'hour_output_min_V':min(r['output_V'] for r in hour),'hour_output_max_V':max(r['output_V'] for r in hour),
 'minute_current_max_uA':max(r['current_uA'] for r in minute),'step_cases':step,'ripple_cases':ripple,'failed_case_count':len(failures),'failed_cases':failures}
(RESULT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='failed_cases'},indent=2))
