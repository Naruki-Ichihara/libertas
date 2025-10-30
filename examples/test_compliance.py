"""Test why compliance is zero."""

import libertas as lb
import pygmsh

# Simple cantilever - MUST have non-zero compliance
L = 10
H = 2
mesh_size = 0.2

with pygmsh.geo.Geometry() as geom:
    geom.add_polygon([[0, 0], [L, 0], [L, H], [0, H]], mesh_size=mesh_size)
    mesh_data = geom.generate_mesh()

geometry = lb.Geometry.from_pygmsh(mesh_data)

bcs = lb.BoundaryConditions(geometry)

# Classic cantilever: left fixed, right loaded
bcs.fix_displacement(x=0.0, tolerance=0.05)  # Left edge fully fixed
bcs.apply_load(
    selector=lambda x, y: x > L - 0.5 and 0.9 < y < 1.1,  # Right edge middle
    force=(0, -1000),  # Strong load
    marker=1
)

# Build to check
import libertas.pytop.pytop as pt
space = geometry.get_function_space("CG", 1, vector=True)
dirichlet_bcs = bcs.build_dirichlet_bcs(space)
ds, forces = bcs.build_neumann_bcs()

print(f"Dirichlet BCs: {len(dirichlet_bcs)}")
print(f"Neumann boundary domains: {ds}")
print(f"Forces dict: {forces}")
print(f"Force keys: {list(forces.keys()) if forces else 'None'}")

if forces:
    for marker, force in forces.items():
        print(f"  Marker {marker}: force = {force}")
