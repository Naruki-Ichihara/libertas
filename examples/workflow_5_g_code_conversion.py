"""
G-Code Generation Workflow - Convert SVG Stripe Paths to G-Code

This script uses libertas built-in svg_to_gcode() function to:
1. Parse SVG stripe paths
2. Optimize path order
3. Export to G-code format with proper extrusion control
"""

import libertas as lb

# ============================================================================
# Configuration
# ============================================================================

# Input/Output paths
output_dir = "outputs/cantilever_problem"
svg_path = f"{output_dir}/stripe_paths.svg"
output_gcode_path = f"{output_dir}/stripe_layer.gcode"

# Print parameters
print_params = lb.PrintParams(
    printer=lb.PrinterType.GENERIC,
    material=lb.MaterialType.PLA,
    temperature=lb.TemperatureParams(
        nozzle_temp=210,          # Nozzle temperature (°C)
        bed_temp=60,              # Bed temperature (°C)
    ),
    speed=lb.SpeedParams(
        print_speed=1000,         # Print speed (mm/min)
        travel_speed=3000,        # Travel speed (mm/min)
        initial_layer_speed=500,  # First layer speed (mm/min)
    ),
    extrusion=lb.ExtrusionParams(
        extrusion_width=0.4,      # Extrusion width (mm)
        extrusion_height=0.2,     # Layer height (mm)
        extrusion_multiplier=1.0, # Extrusion flow multiplier
    ),
    retraction=lb.RetractionParams(
        enabled=True,
        retraction_distance=1.0,  # Retraction distance (mm)
        retraction_speed=40.0,    # Retraction speed (mm/s)
    ),
    cooling=lb.CoolingParams(
        fan_speed=100,            # Fan speed (0-100%)
    ),
)

# Conversion parameters
segment_length = 0.5        # Discretization length for SVG curves (mm)
z_height = 0.2              # Z-height for the layer (mm)
optimize_paths = True       # Optimize path order to minimize travel distance

# ============================================================================
# Convert SVG to G-Code using libertas.svg_to_gcode()
# ============================================================================

print("\nUsing libertas.svg_to_gcode() with path optimization enabled")
print("This generates G-code with proper extrusion control\n")

# Use libertas built-in svg_to_gcode function
result = lb.svg_to_gcode(
    svg_path=svg_path,
    output_gcode_path=output_gcode_path,
    print_params=print_params,
    segment_length=segment_length,
    z_height=z_height,
    optimize_paths=optimize_paths
)

# ============================================================================
# Summary
# ============================================================================

print(f"\n📊 Conversion Summary:")
print(f"  Output file:         {result['gcode_path']}")
print(f"  Number of paths:     {result['num_paths']}")
print(f"  Total path length:   {result['total_length']:.2f} mm")
print(f"  Travel distance:     {result['total_travel']:.2f} mm")
print(f"  Z-height:            {result['z_height']} mm")
print(f"  Optimized:           {'Yes' if result.get('optimized', False) else 'No'}")

print(f"\n🖨️ Print Settings:")
print(f"  Nozzle temp:         {print_params.temperature.nozzle_temp}°C")
print(f"  Bed temp:            {print_params.temperature.bed_temp}°C")
print(f"  Print speed:         {print_params.speed.print_speed} mm/min")
print(f"  Travel speed:        {print_params.speed.travel_speed} mm/min")
print(f"  Extrusion width:     {print_params.extrusion.extrusion_width} mm")
print(f"  Layer height:        {print_params.extrusion.extrusion_height} mm")

print(f"\n📝 Next steps:")
print(f"  1. Review {result['gcode_path']} in a G-code viewer")
print(f"  2. Adjust print parameters if needed")
print(f"  3. Send to your 3D printer")

print(f"\n💡 Tips:")
print(f"  - Paths are optimized to minimize travel distance")
print(f"  - Retraction is enabled for travel moves")
print(f"  - Adjust extrusion_multiplier if needed for fine-tuning")

print("\n" + "="*70 + "\n")
