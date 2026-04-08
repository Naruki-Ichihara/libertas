"""
Post-processing: extract a triangular FEM mesh from the optimized density field.

Reads the density XML produced by workflow_1, converts it to a smooth boundary
representation, and generates a conforming triangular mesh for use in subsequent
FEniCS analyses (e.g. stripe pattern generation in workflow_3).

Pipeline:
    xml/density.xml
        -> rasterize to image (read_density_from_xml)
        -> Gaussian smoothing (remove FEM-level noise)
        -> iso-contour as Bézier SVG (extract_contour_svg)
        -> constrained Delaunay triangulation (mesh_from_svg)
        -> xml/mesh_from_density.xml

Requires workflow_1 to have been run first (outputs/cantilever_problem/xml/).
"""

import libertas as lb
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

# ============================================================================
# Configuration
# ============================================================================

# Input/Output paths
output_dir = "outputs/cantilever_10"
xml_dir = f"{output_dir}/xml"

# Rasterization — higher resolution captures finer boundary detail
resolution = (1000, 500)     # (width, height) in pixels; match aspect ratio of the domain

# Pre-smoothing — blurs the density field before contouring to suppress FEM artifacts
gaussian_sigma = 2           # pixels; increase for a smoother boundary, 0 to disable

# Contour extraction
threshold = 0.5              # density iso-level that defines the solid/void interface
smoothness = 0.01            # Bézier fit tolerance (smaller = smoother, larger = sharper corners)
corner_angle = 120.0         # corners sharper than this angle (deg) are treated as hard corners

# Mesh quality — Triangle library constraints
max_area = 0.2               # maximum triangle area (mm²); primary mesh density control
min_angle = 25.0             # minimum interior angle (deg); prevents sliver elements
min_edge_length = 0.05       # None = rely on max_area only (avoids overriding max_area)
samples_per_curve = 3        # sample points per Bézier curve segment

# ============================================================================
# Step 1: Read Density Field
# ============================================================================

print("\n" + "="*70)
print("MESH EXTRACTION WORKFLOW")
print("="*70)

print("\n1. Reading density field from XML...")
density_img, metadata = lb.read_density_from_xml(
    xml_dir,
    resolution=resolution,
    interpolation="linear"
)
print(f"   Density image: {density_img.shape}")
print(f"   Bounds: x=[{metadata['bounds']['x_min']:.2f}, {metadata['bounds']['x_max']:.2f}], "
      f"y=[{metadata['bounds']['y_min']:.2f}, {metadata['bounds']['y_max']:.2f}]")
print(f"   Density range: [{metadata['density_range'][0]:.3f}, {metadata['density_range'][1]:.3f}]")

# Apply Gaussian filter to smooth the density field
if gaussian_sigma > 0:
    print(f"\n   Applying Gaussian filter (sigma={gaussian_sigma})...")
    density_img = gaussian_filter(density_img, sigma=gaussian_sigma)
    print(f"   Filtered density range: [{density_img.min():.3f}, {density_img.max():.3f}]")

# ============================================================================
# Step 2: Extract Contours as SVG
# ============================================================================

print("\n2. Extracting smooth contours as SVG...")
contour_svg_path = f"{xml_dir}/contour_for_mesh.svg"
lb.extract_contour_svg(
    density_img,
    metadata,
    contour_svg_path,
    threshold=threshold,
    smoothness=smoothness,
    corner_angle=corner_angle,
    fill_color="#000000"
)
print(f"   Contour SVG saved to: {contour_svg_path}")

# ============================================================================
# Step 3: Generate Triangular Mesh
# ============================================================================

print("\n3. Generating triangular mesh from contours...")
print(f"   Parameters:")
print(f"   - max_area: {max_area} mm^2")
print(f"   - min_edge_length: {min_edge_length} mm")
print(f"   - min_angle: {min_angle} degrees")
print(f"   - samples_per_curve: {samples_per_curve}")
print(f"   - smoothness: {smoothness}")
print(f"   - corner_angle: {corner_angle} degrees")

mesh_output_path = f"{xml_dir}/mesh_from_density.xml"
# Use the max_area variable from configuration
mesh_data = lb.mesh_from_svg(
    contour_svg_path,
    mesh_output_path,
    max_area=max_area,  # Use configuration value
    min_angle=min_angle,
    min_edge_length=min_edge_length,
    min_boundary_spacing=2.0,  # Filter boundary points to be at least 2mm apart
    boundary_corner_angle=corner_angle,
    samples_per_curve=samples_per_curve
)

print(f"   Mesh extracted successfully!")
print(f"   Vertices:  {len(mesh_data['vertices']):,}")
print(f"   Triangles: {len(mesh_data['triangles']):,}")
print(f"   Mesh saved to: {mesh_output_path}")

# ============================================================================
# Step 4: Visualize Mesh
# ============================================================================

print("\n4. Creating mesh visualization...")

vertices = mesh_data['vertices']
triangles = mesh_data['triangles']

fig, ax = plt.subplots(figsize=(16, 10))
ax.triplot(vertices[:, 0], vertices[:, 1], triangles, 'b-', linewidth=0.2, alpha=0.6)
ax.set_title('Generated Mesh', fontsize=16, fontweight='bold')
ax.set_xlabel('X (mm)', fontsize=12)
ax.set_ylabel('Y (mm)', fontsize=12)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3)

plt.tight_layout()
viz_plot_path = f"{output_dir}/mesh_visualization.png"
plt.savefig(viz_plot_path, dpi=150, bbox_inches='tight')
print(f"   Mesh visualization saved to: {viz_plot_path}")
plt.close()

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*70)
print("MESH EXTRACTION COMPLETE!")
print("="*70)

print("\nGenerated Files:")
print(f"  1. Contour SVG:      {contour_svg_path}")
print(f"  2. Mesh XML:         {mesh_output_path}")
print(f"  3. Visualization:    {viz_plot_path}")

print("\nMesh Statistics:")
print(f"  Vertices:            {len(vertices):,}")
print(f"  Triangles:           {len(triangles):,}")

print("\n" + "="*70 + "\n")
