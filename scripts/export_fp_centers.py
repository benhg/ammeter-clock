"""Print pin-pattern centers; exclude silkscreen, labels and module outlines."""
import json
import sys
import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
centers = {}
for fp in board.GetFootprints():
    points = [pad.GetPosition() for pad in fp.Pads()]
    if not points:
        continue
    centers[fp.GetReference()] = [
        pcbnew.ToMM((min(p.x for p in points) + max(p.x for p in points)) / 2),
        pcbnew.ToMM((min(p.y for p in points) + max(p.y for p in points)) / 2),
    ]
print(json.dumps(centers, sort_keys=True))
