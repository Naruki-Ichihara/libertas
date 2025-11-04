"""Test Layer to CSV export for FullControl."""

import sys
sys.path.insert(0, '/workspace')

import libertas as lb
from pathlib import Path

print("=" * 70)
print("LAYER TO CSV EXPORT TEST")
print("=" * 70)

# Parse SVG
svg_path = Path("/workspace/output/example_libertas/svg/paths.svg")
output_dir = Path("/workspace/output/example_libertas/csv")
output_dir.mkdir(parents=True, exist_ok=True)

print(f"\nInput SVG: {svg_path}")

paths = lb.parse_svg_to_paths(str(svg_path), segment_length=0.5)
print(f"Parsed {len(paths)} paths")

# Create layer
layer = lb.Layer(layer_id=0, paths=paths, z_height=0.2, name="TestLayer")
layer.optimize_closed_path_order()
layer.optimize_open_path_order()

print(f"\nLayer info:")
print(f"  {layer}")
print(f"  Closed paths: {len(layer.get_closed_paths())}")
print(f"  Open paths: {len(layer.get_open_paths())}")

# Export to CSV
csv_path = output_dir / "layer_points.csv"
print(f"\nExporting to CSV: {csv_path}")

num_points = layer.to_points_csv(
    str(csv_path),
    z_height=0.2,
    include_travel=True,
    extrusion_on_value=1.0,
    extrusion_off_value=0.0
)

print(f"  Total points: {num_points}")
print(f"  File size: {Path(csv_path).stat().st_size / 1024:.1f} KB")

# Show first few lines
print(f"\nFirst 10 lines of CSV:")
with open(csv_path, 'r') as f:
    for i, line in enumerate(f):
        if i >= 10:
            break
        print(f"  {line.rstrip()}")

# Count extrusion on/off points
with open(csv_path, 'r') as f:
    lines = f.readlines()[1:]  # Skip header
    extrusion_on = sum(1 for line in lines if line.strip().endswith('1.0'))
    extrusion_off = sum(1 for line in lines if line.strip().endswith('0.0'))

print(f"\nExtrusion statistics:")
print(f"  ON points: {extrusion_on}")
print(f"  OFF points (travel): {extrusion_off}")
print(f"  Total: {extrusion_on + extrusion_off}")

# FullControl example
print("\n" + "=" * 70)
print("FULLCONTROL USAGE EXAMPLE")
print("=" * 70)

print("""
To use this CSV in FullControl:

```python
import pandas as pd
import fullcontrol as fc

# Read CSV
df = pd.read_csv('layer_points.csv')

# Create FullControl points
steps = []
for _, row in df.iterrows():
    # Add point
    steps.append(fc.Point(x=row['x'], y=row['y'], z=row['z']))

    # Control extrusion
    if row['extrusion'] > 0.5:
        steps.append(fc.Extruder(on=True))
    else:
        steps.append(fc.Extruder(on=False))

# Generate GCode
gcode = fc.transform(steps, 'gcode')
```
""")

print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)

print(f"\nGenerated file: {csv_path}")
print(f"Ready for FullControl import!")
