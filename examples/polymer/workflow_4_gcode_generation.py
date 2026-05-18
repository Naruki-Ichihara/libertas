"""
Workflow 4: G-code Generation from stripe SVG

Reads the stripe SVG produced by workflow_3, stacks layers up to a target
height, and outputs a single G-code file.

Input:  outputs/cantilever_10/stripe_paths.svg  (from workflow_3)
Output: outputs/cantilever_10/cantilever_stacked_<N>layer.gcode
"""

import libertas as lb
from libertas.svg_parser import parse_svg_to_paths
from libertas.fibrifier_gcode import simplify_path_nodes
from libertas.path import Path
from libertas.layer import Layer
from libertas.model import Model
import math
import os

# ============================================================================
# Configuration
# ============================================================================

_HERE = os.path.dirname(__file__)
output_dir = os.path.join(_HERE, "outputs", "cantilever_10")

# Input SVG (from workflow_3)
svg_path = f"{output_dir}/stripe_paths.svg"

# Bed placement offset (mm) — shift the print on the build plate
offset_x = 0.0
offset_y = 0.0

# Stacking
layer_height = 0.65          # mm per layer
target_height = 10.0         # mm total height
num_layers = math.floor(target_height / layer_height)  # 15 layers → 9.75 mm

# Path simplification
smooth_sigma = 3.0           # Gaussian smoothing
decimate_epsilon = 0.05      # RDP decimation tolerance (mm)

# Print parameters
print_params = lb.PrintParams(
    printer=lb.PrinterType.GENERIC,
    material=lb.MaterialType.PLA,
    temperature=lb.TemperatureParams(nozzle_temp=210, bed_temp=60),
    speed=lb.SpeedParams(print_speed=1000, travel_speed=3000, initial_layer_speed=500),
    extrusion=lb.ExtrusionParams(
        extrusion_width=0.4,
        extrusion_height=layer_height,
        extrusion_multiplier=1.0,
    ),
    retraction=lb.RetractionParams(enabled=True, retraction_distance=1.0, retraction_speed=40.0),
    cooling=lb.CoolingParams(fan_speed=100),
)

# ============================================================================
# Step 1: Parse SVG and prepare paths
# ============================================================================

print("\n" + "=" * 70)
print("WORKFLOW 4: G-CODE GENERATION")
print("=" * 70)

print(f"\n1. Parsing SVG: {svg_path}")
paths = parse_svg_to_paths(svg_path, segment_length=0.5)

# Simplify (no Y-flip needed: stripe_to_image now outputs correct image convention)
total_before = sum(len(p.nodes) for p in paths)
simplified_paths = []
for p in paths:
    new_nodes = simplify_path_nodes(p.nodes, sigma=smooth_sigma, epsilon=decimate_epsilon)
    simplified_paths.append(Path(path_id=p.path_id, nodes=new_nodes, path_type=p.path_type))
total_after = sum(len(p.nodes) for p in simplified_paths)
print(f"   {len(paths)} paths, simplified {total_before} → {total_after} points")

# ============================================================================
# Step 2: Build multi-layer Model
# ============================================================================

print(f"\n2. Building {num_layers}-layer model (height = {num_layers * layer_height:.2f} mm)...")

model = Model(model_id=1, name="cantilever_striped")
model.offset_x = offset_x
model.offset_y = offset_y
for i in range(num_layers):
    z = layer_height * (i + 1)
    layer = Layer(layer_id=i + 1, paths=simplified_paths, name=f"layer_{i+1}", z_height=z)
    stats = layer.statistics()
    if stats['closed_paths'] > 0:
        layer.optimize_closed_path_order()
    if stats['open_paths'] > 0:
        layer.optimize_open_path_order()
    model.add_layer(layer)

print(f"   Model: {len(model.layers)} layers, z = {layer_height:.2f} .. {num_layers * layer_height:.2f} mm")

# ============================================================================
# Step 3: Generate G-code
# ============================================================================

print(f"\n3. Generating G-code...")
gcode_path = f"{output_dir}/cantilever_stacked_{num_layers}layer.gcode"
result = lb.model_to_gcode(
    model=model,
    output_path=gcode_path,
    print_params=print_params,
)

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 70)
print("G-CODE GENERATION COMPLETE!")
print("=" * 70)

print(f"\n  Output:       {gcode_path}")
print(f"  Layers:       {result['num_layers']}")
print(f"  Paths:        {result['num_paths']}")
print(f"  Height range: {result['height_range']}")

print("\n" + "=" * 70 + "\n")
