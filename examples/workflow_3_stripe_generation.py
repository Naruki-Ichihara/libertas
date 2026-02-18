"""
Stripe Pattern Generation for Extracted Mesh

This script:
1. Uses the pre-extracted mesh from mesh_extraction_workflow.py
2. Generates stripe pattern with specified hatch spacing
3. Converts stripe pattern to SVG paths for 3D printing
"""

import libertas as lb

# ============================================================================
# Configuration
# ============================================================================

# Input/Output paths
output_dir = "outputs/cantilever_problem"
xml_dir = f"{output_dir}/xml"

# Input mesh from mesh_extraction_workflow
mesh_path = f"{xml_dir}/mesh_from_density.xml"

# Stripe pattern parameters
hatch_spacing = 0.8          # Hatch spacing in mm (stripe width)
refine_levels = 0            # Mesh refinement levels (0=no refinement to save memory)
stripe_tolerance = 1e-1      # Absolute tolerance for stripe generation

# ============================================================================
# Step 1: Generate Stripe Pattern
# ============================================================================

print("\n" + "="*70)
print("STRIPE PATTERN GENERATION")
print("="*70)

print(f"\n1. Stripe pattern configuration:")
print(f"   Input mesh: {mesh_path}")
print(f"   Hatch spacing: {hatch_spacing} mm")
print(f"   Refinement levels: {refine_levels}")
print(f"   Tolerance: {stripe_tolerance}")

# Generate stripe pattern using extracted mesh
print(f"\n2. Generating stripe pattern...")
lb.generate_stripe_pattern(
    xml_dir=xml_dir,
    extracted_mesh_path=mesh_path,
    stripe_width=hatch_spacing,
    refine_levels=refine_levels,
    absolute_tol=stripe_tolerance,
    output_name="stripe"
)

print(f"   Stripe pattern generated successfully!")

