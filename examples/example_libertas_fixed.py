"""
Exact replica of example.py using libertas API - CORRECTED.

This demonstrates that libertas can reproduce the exact same problem
with much less code.
"""

import libertas as lb
import pygmsh

# Parameters -------------------------------------------------------
# Geometry
L = 15
H = 5
mesh_size = 0.1

# Material
E1 = 6.158e3
E2 = 2.845e3
G12 = 741
nu = 0.22

# Optimization
p = 3
target_fraction = 0.40
filter_radius = 0.2
filter_radius_orientation = 0.2

# Boundary conditions
delta = 0.5  # Increased for coarser mesh
force_vector = (0, -100)  # Increased force magnitude

# Directory
output_path = "output/example_libertas_fixed"

# Geometry ---------------------------------------------------------------
with pygmsh.geo.Geometry() as geom:
    geom.add_polygon([
        [0., 0.],
        [L, 0.],
        [L, H],
        [0., H]
    ], mesh_size=mesh_size)
    mesh_data = geom.generate_mesh()

geometry = lb.Geometry.from_pygmsh(
    mesh_data,
    save_path=f"{output_path}/mesh.xml"
)

# Boundary conditions ----------------------------------------------------
EPS = 0.01  # Tolerance appropriate for mesh_size=0.1

bcs = lb.BoundaryConditions(geometry)

# Left edge: fix x-displacement ONLY (not y!)
bcs.fix_x(x=0.0, tolerance=EPS)

# Right bottom corner: fix y-displacement
bcs.fix_y(
    selector=lambda x, y: x > L - delta and y < delta,
    tolerance=EPS
)

# Right bottom: apply load (same region as y-constraint is OK for traction)
bcs.apply_load(
    selector=lambda x, y: x > L - delta and y < delta,
    force=force_vector,
    marker=1
)

# Material --------------------------------------------------------------
material = lb.OrthotropicMaterial(
    E1=E1,
    E2=E2,
    G12=G12,
    nu12=nu,
    name="Composite material"
)

# Problem statement ------------------------------------------------------
problem = lb.TopologyOptimization(
    geometry=geometry,
    material=material,
    boundaries=bcs,
    target_density=target_fraction,
    penalty_exponent=p,
    penalty_epsilon=1e-2,
    filter_radius_density=filter_radius,
    filter_radius_orientation=filter_radius_orientation,
    sgn_sharpness=10.0,
    output_dir=output_path
)

# Optimization -----------------------------------------------------------
result = problem.optimize(
    algorithm="MMA",
    max_iterations=50,
    tolerance=1e-4,
    verbosity=1,
    density_initial=target_fraction,
    orientation_tolerance=1e-2
)

# Results
result.summary()
result.plot_convergence()

print(f"\n{'='*60}")
print(f"FIXED: Left edge now only fixes x (allows vertical movement)")
print(f"This creates a proper cantilever with non-zero compliance")
print(f"{'='*60}\n")
