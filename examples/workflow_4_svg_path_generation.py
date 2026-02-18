"""
Path Generation Workflow - Convert Stripe Pattern to SVG

This script:
1. Reads stripe pattern from optimization results
2. Converts stripe to SVG with density clipping
3. Scales output by 6x for fabrication
"""

import libertas as lb

# ============================================================================
# Configuration
# ============================================================================

# Input/Output paths
output_dir = "outputs/cantilever_problem"
xml_dir = f"{output_dir}/xml"

# Stripe to SVG parameters
stripe_xml_path = f"{xml_dir}/stripe"           # Path to stripe XML (without .xml)
mesh_path = f"{xml_dir}/mesh_from_density.xml"  # Extracted mesh (used for stripe generation)
density_xml_path = f"{xml_dir}/density"         # Path to density XML (without .xml)
output_svg_path = f"{output_dir}/stripe_paths.svg"

# Conversion parameters
resolution = (1000, 800)        # High resolution for smooth contours
refine_levels = 0                # Must match stripe generation refinement
density_threshold = 0.5          # Clip paths where density > threshold
contour_level = 0.0              # Extract zero-crossings of stripe pattern
stroke_color = "#000000"         # Black paths
stroke_width = 2             # Line width in mm
min_path_length = 2            # Filter out paths shorter than 0.5mm
scale_factor = 6.0               # Scale output by 6x

# Optional: show density boundary
show_density_contour = True      # Overlay density boundary on SVG
density_contour_color = "#FF0000"  # Red boundary
density_contour_width = 2     # Boundary line width
density_offset = 0.1             # Offset to shrink density boundary (0 = no offset)

# ============================================================================
# Convert Stripe Pattern to SVG
# ============================================================================

print("\n" + "="*70)
print("STRIPE PATTERN TO SVG CONVERSION")
print("="*70)

print(f"\nInput:")
print(f"  Stripe XML:     {stripe_xml_path}.xml")
print(f"  Mesh:           {mesh_path}")
print(f"  Density XML:    {density_xml_path}.xml")

print(f"\nParameters:")
print(f"  Resolution:            {resolution}")
print(f"  Refine levels:         {refine_levels}")
print(f"  Density threshold:     {density_threshold}")
print(f"  Contour level:         {contour_level}")
print(f"  Min path length:       {min_path_length} mm")
print(f"  Scale factor:          {scale_factor}x")
print(f"  Show density contour:  {show_density_contour}")
print(f"  Density offset:        {density_offset} mm")

print("\nConverting stripe pattern to SVG paths...")

result = lb.stripe_to_svg(
    stripe_xml_path=stripe_xml_path,
    mesh_path=mesh_path,
    output_svg_path=output_svg_path,
    resolution=resolution,
    refine_levels=refine_levels,
    density_xml_path=density_xml_path,
    density_threshold=density_threshold,
    contour_level=contour_level,
    stroke_color=stroke_color,
    stroke_width=stroke_width,
    min_path_length=min_path_length,
    show_density_contour=show_density_contour,
    density_contour_color=density_contour_color,
    density_contour_width=density_contour_width,
    density_offset=density_offset,
    scale_factor=scale_factor
)

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*70)
print("CONVERSION COMPLETE!")
print("="*70)

print(f"\nOutput SVG: {output_svg_path}")

print(f"\nStatistics:")
print(f"  Number of stripe paths: {result['num_contours']}")
print(f"  Total points:           {result['total_points']:,}")
print(f"  Resolution used:        {result['resolution']}")
print(f"  Contour level:          {result['contour_level']}")

if 'density_threshold' in result:
    print(f"  Density threshold:      {result['density_threshold']}")
    print(f"  Solid fraction:         {result['solid_fraction']:.1%}")

if 'num_density_contours' in result:
    print(f"  Density contour paths:  {result['num_density_contours']}")

bounds = result['bounds']
print(f"\nDomain bounds:")
print(f"  X: [{bounds['x_min']:.2f}, {bounds['x_max']:.2f}] mm")
print(f"  Y: [{bounds['y_min']:.2f}, {bounds['y_max']:.2f}] mm")

print(f"\nScaled output size (6x):")
print(f"  Width:  {(bounds['x_max'] - bounds['x_min']) * scale_factor:.2f} mm")
print(f"  Height: {(bounds['y_max'] - bounds['y_min']) * scale_factor:.2f} mm")

print("\n" + "="*70 + "\n")
