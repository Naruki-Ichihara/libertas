"""Simple example: XML → GCode with offset (50, 50)"""

import sys
sys.path.insert(0, '/workspace')

import libertas as lb
from pathlib import Path

# Parse density XML to SVG paths
xml_dir = Path("/workspace/output/example_libertas/xml")
svg_path = xml_dir.parent / "svg" / "paths.svg"

paths = lb.parse_svg_to_paths(str(svg_path), segment_length=0.5)

# Create model
model = lb.Model(model_id=1, layer_height=0.2)
for i in range(50):
    layer = lb.Layer(layer_id=i, paths=paths)
    model.add_layer(layer)

model.optimize_all_layers()

# Set offset (50, 50)
model.set_offset(50.0, 50.0)

# Print parameters
params = lb.PrintParams.from_preset(
    printer=lb.PrinterType.PRUSA_I3,
    material=lb.MaterialType.PLA
)
params.relative_extrusion = False

# Generate GCode
output_path = xml_dir.parent / "gcode" / "simple_offset_50_50.gcode"
result = lb.model_to_gcode(model, str(output_path), params)

print(f"\nGenerated: {output_path}")
print(f"Layers: {result['num_layers']}")
print(f"Offset: (50.0, 50.0)")
print(f"Center: {model.get_center_position()}")
