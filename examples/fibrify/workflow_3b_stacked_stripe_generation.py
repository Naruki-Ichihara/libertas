"""
Stacked Stripe Pattern Generation for [0/90/90/0] Laminate

This script:
1. Generates stripe patterns for each unique ply angle in the stacking sequence.
   The optimized orientation tensor is rotated by each offset before solving
   the Swift-Hohenberg PDE for the stripe field.
2. Converts each stripe pattern to SVG with density clipping.
3. Converts each SVG to G-code at the corresponding z-height.

Run after: workflow_1b (optimization) + workflow_2 (mesh extraction).
"""

import libertas as lb

# ============================================================================
# Configuration
# ============================================================================

output_dir = "outputs/cantilever_10"
xml_dir = f"{output_dir}/xml"
mesh_path = f"{xml_dir}/mesh_from_density.xml"  # from workflow_2

# Stacking sequence (must match optimization)
stacking_sequence = [10, -10, -10, 10]  # degrees

# --- Stripe parameters ---
hatch_spacing = 2       # mm
refine_levels = 0
stripe_tolerance = 1e-1

# --- SVG conversion parameters ---
svg_resolution = (1000, 800)
density_threshold = 0.5
min_path_length = 4       # mm
scale_factor = 1
density_offset = 0.1      # mm

# --- Print parameters ---
layer_height = 0.2        # mm per ply
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
# Step 1: Generate stripe patterns for each unique ply angle
# ============================================================================

print("\n" + "=" * 70)
print("STEP 1: STACKED STRIPE PATTERN GENERATION")
print("=" * 70)

stripe_result = lb.generate_stacked_stripe_patterns(
    xml_dir=xml_dir,
    extracted_mesh_path=mesh_path,
    stacking_sequence=stacking_sequence,
    stripe_width=hatch_spacing,
    refine_levels=refine_levels,
    absolute_tol=stripe_tolerance,
    output_prefix="stripe",
)

# ============================================================================
# Step 2: Convert each stripe pattern to SVG
# ============================================================================

print("\n" + "=" * 70)
print("STEP 2: STRIPE TO SVG CONVERSION (per ply angle)")
print("=" * 70)

# Only process unique angles (avoid duplicate SVG generation)
unique_plies = {ply["angle"]: ply for ply in stripe_result["plies"]}
refined_mesh = stripe_result["mesh_path"]

for angle, ply in sorted(unique_plies.items()):
    svg_path = f"{output_dir}/stripe_paths_{angle}deg.svg"
    print(f"\n  Converting {ply['output_name']} -> SVG ...")

    lb.stripe_to_svg(
        stripe_xml_path=ply["stripe_xml"],
        mesh_path=refined_mesh,
        output_svg_path=svg_path,
        resolution=svg_resolution,
        refine_levels=0,  # already refined
        density_xml_path=f"{xml_dir}/density",
        density_threshold=density_threshold,
        min_path_length=min_path_length,
        show_density_contour=True,
        density_offset=density_offset,
        scale_factor=scale_factor,
    )
