# Rev 2 — seconds meter and accessible minute button terminal

This is an isolated successor to the built Rev F4 two-meter shield. Open
`ammeter-clock/ammeter-clock.kicad_pro` here in KiCad 8. The root project is the
Rev F4 baseline and is not replaced by Rev 2.

- R10 (56 kΩ, 1%) and J10 (two-position 5 mm screw terminal) duplicate R3/J3.
  MCP4728 B / pin 7 drives R10 → J10 pin 1 (+); pin 2 is GND.
- Hours remain on DAC D / pin 9; minutes remain on C / pin 8. A / pin 6 is unused.
  The old schematic's reversed channel *names* were corrected to match these pins.
- J5 rotates 180° around its body center, with wire entry toward the board center,
  away from the bottom power header. Its signal/GND pad assignments follow the
  rotated connector. Route external button wiring through the open center corridor.
- Same Uno outline, mounting holes, stackable headers, R3/R4 WiFi signals and
  underside/antenna exclusions. Pololu module and all other electrical values stay.
- 28 assembled components: 6 SMT, 22 through-hole; customer installs the Pololu
  module in U4's assembler-fitted socket. Seconds needs another **0–100 µA** needle
  movement. Firmware 0.3.0 enables that channel through the calibration wizard.

`fabrication/ammeter-clock-rev2-fabrication.zip` contains the Gerbers, full BOM/CPL,
manifest and check summaries. The BOM reuses F4 catalogue parts; current stock
has not been rechecked. This is a prototype package, not a bench-qualified release.

Validation: zero ERC/DRC violations, zero unconnected pads; all 32 component
references including four mounting holes match between schematic and board.
Both Uno header geometries and signal assignments pass. 205 ngspice analyses,
including 18 simultaneous minute/second load corners and seconds rollover/short,
plus six engineering input-clamp cases pass. Ideal DAC sources and imposed boost
rails do not establish converter startup, crosstalk or needle dynamics. New terminal
access, physical stack clearances and seconds response still need a built Rev 2.

To rerun from repository root (KiCad 8 Python is required for PCB scripts):

```sh
export AMMETER_PROJECT_DIR="$PWD/hardware/rev2"
kicad-cli sch export netlist --format kicadxml -o hardware/rev2/reports/netlist.xml hardware/rev2/ammeter-clock/ammeter-clock.kicad_sch
python scripts/check_hardware.py
python scripts/check_shield.py
python scripts/check_r4_wifi.py
python simulations/run_simulations.py
python simulations/check_input_protection.py
python scripts/export_rev2.py
```

Use the Python bundled with KiCad where `pcbnew` is imported. Set PATH to include
`ngspice`. Raw simulation traces are regenerated locally; summary JSON/CSVs and
source decks/models are retained. `build_rev2.py` is the historical one-time fork
from the root F4 snapshot; it refuses to overwrite an existing Rev 2 project.
Subsequent layout edits should be made in KiCad, then checked and exported again.
