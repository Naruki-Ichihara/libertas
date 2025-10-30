"""
Debug boundary conditions to see why load isn't applied.
"""

import libertas as lb
import pygmsh

# Geometry
L = 6
H = 1
mesh_size = 0.02

with pygmsh.geo.Geometry() as geom:
    geom.add_polygon([
        [0., 0.],
        [L/2, 0.],
        [L/2, H],
        [0., H]
    ], mesh_size=mesh_size)
    mesh_data = geom.generate_mesh()

geometry = lb.Geometry.from_pygmsh(mesh_data, save_path="output/debug/mesh.xml")

# Check mesh bounds
import libertas.pytop.pytop as pt
coords = geometry.mesh.coordinates()
print("Mesh coordinate ranges:")
print(f"  x: [{coords[:, 0].min():.6f}, {coords[:, 0].max():.6f}]")
print(f"  y: [{coords[:, 1].min():.6f}, {coords[:, 1].max():.6f}]")

# Test boundary condition selectors
EPS = 1e-10
delta = 0.04

print("\nTesting boundary selectors:")

# Test left edge
left_count = sum(1 for coord in coords if coord[0] < EPS)
print(f"Left edge (x < {EPS}): {left_count} nodes")

# Test right bottom
right_bottom_count = sum(1 for coord in coords if coord[0] > L/2 - EPS - delta and coord[1] < EPS)
print(f"Right bottom (x > {L/2 - EPS - delta:.6f} and y < {EPS}): {right_bottom_count} nodes")

# Test left upper (load zone)
left_upper_count = sum(1 for coord in coords if coord[0] < delta + EPS and coord[1] > H - EPS)
print(f"Left upper (x < {delta + EPS:.6f} and y > {H - EPS}): {left_upper_count} nodes")

# Create BCs with actual pytop SubDomains to verify
print("\nCreating boundary conditions...")

class LeftUpper(pt.SubDomain):
    def inside(self, x, on_boundary):
        result = x[0] < delta + EPS and x[1] > H - EPS and on_boundary
        if result:
            print(f"  Load point found: ({x[0]:.6f}, {x[1]:.6f})")
        return result

# Create boundary domains
ds = pt.make_noiman_boundary_domains(geometry.mesh, [LeftUpper()], True)

print("\nBoundary domain created successfully!")
print("If no 'Load point found' messages above, the selector is not matching any boundary facets.")
