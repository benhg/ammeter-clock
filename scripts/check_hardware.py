"""Compare exported schematic nets with actual PCB pins, including no-connects.
Run with KiCad bundled Python after kicad-cli sch export netlist --format kicadxml.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import pcbnew as pcb
root=Path(__file__).resolve().parents[1]
import os
PROJECT=Path(os.environ.get("AMMETER_PROJECT_DIR",str(root)))
DATA=PROJECT if "AMMETER_PROJECT_DIR" in os.environ else root/"hardware"
sch=ET.parse(PROJECT/'reports/netlist.xml').getroot()
expected={};unconnected=set()
for net in sch.findall('./nets/net'):
 nodes=net.findall('node')
 # KiCad exports a named one-pin island for an explicit schematic no-connect.
 # The generator leaves these unused pass-through header pads at net 0.
 if net.attrib['name'].startswith('unconnected-'):
  assert len(nodes)==1,net.attrib['name']
  unconnected.add((nodes[0].attrib['ref'],nodes[0].attrib['pin']))
  continue
 for node in nodes:
  key=(node.attrib['ref'],node.attrib['pin'])
  assert key not in expected,key
  expected[key]=net.attrib['name']
b=pcb.LoadBoard(str(PROJECT/'ammeter-clock/ammeter-clock.kicad_pcb'))
actual={};allpads={}
for fp in b.GetFootprints():
 for pad in fp.Pads():
  key=(fp.GetReference(),pad.GetNumber())
  allpads[key]=pad
  if pad.GetNetCode():actual[key]=pad.GetNetname()
assert expected==actual,dict(missing=set(expected.items())-set(actual.items()),extra=set(actual.items())-set(expected.items()))
for key in unconnected:
 assert key in allpads and allpads[key].GetNetCode()==0,('No-connect pad is wired',key)
expected_refs={c.attrib['ref'] for c in sch.findall('./components/comp')}
assert expected_refs=={f.GetReference() for f in b.GetFootprints()}
result=f'PASS: {len(expected_refs)} components, {len(actual)} connected pins and {len(unconnected)} intentionally unused pins match schematic and PCB.\n'
(PROJECT/'reports/netlist-check.txt').write_text(result)
print(result,end='')
