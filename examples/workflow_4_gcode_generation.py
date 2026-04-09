"""
Workflow 4: G-code Generation from SVG stripe patterns

Converts optimized stripe pattern SVGs to printable G-code using FullControl.
Paths are simplified (smoothed + decimated) before conversion.

Input:  SVG files from workflow_3b (stripe_paths_*.svg)
Output: G-code files for each ply
"""

import libertas as lb

# ============================================================================
# Configuration
# ============================================================================

sample_dir = "sample"
output_dir = "sample"

# Stacking sequence
stacking_sequence = [10, -10]  # degrees
layer_height = 0.2  # mm per ply

# SVG → GCode parameters
smooth_sigma = 3.0        # Gaussian smoothing
decimate_epsilon = 0.05   # RDP decimation tolerance (mm)
connection_threshold = 8.0  # Path connection threshold (mm)

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
# Generate G-code for each ply
# ============================================================================

print("\n" + "=" * 70)
print("WORKFLOW 4: G-CODE GENERATION")
print("=" * 70)

for ply_idx, angle in enumerate(stacking_sequence):
    svg_path = f"{sample_dir}/stripe_paths_{angle}deg.svg"
    gcode_path = f"{output_dir}/ply_{ply_idx}_{angle}deg.gcode"
    z = layer_height * (ply_idx + 1)

    print(f"\n--- Ply {ply_idx} ({angle:+d}°) at z={z:.2f}mm ---")

    result = lb.svg_to_gcode(
        svg_path=svg_path,
        output_gcode_path=gcode_path,
        print_params=print_params,
        z_height=z,
        smooth_sigma=smooth_sigma,
        decimate_epsilon=decimate_epsilon,
        optimize_paths=True,
        flip_y=True,
    )

    print(f"  Paths: {result['num_paths']}, "
          f"Length: {result['total_length']:.1f}mm, "
          f"Travel: {result['total_travel']:.1f}mm")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 70)
print("COMPLETE")
print("=" * 70)

for ply_idx, angle in enumerate(stacking_sequence):
    z = layer_height * (ply_idx + 1)
    print(f"  Ply {ply_idx} ({angle:+3d}°)  z={z:.2f}mm  → "
          f"{output_dir}/ply_{ply_idx}_{angle}deg.gcode")

print("=" * 70 + "\n")
