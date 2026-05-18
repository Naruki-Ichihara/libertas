"""Topology + orientation optimization with a [+10/-10/-10/+10] symmetric laminate.

Same simply-supported beam problem as workflow_1, but the material at each
point is homogenized over a [+10/-10/-10/+10] stacking sequence (equal
thickness per ply).
"""

import libertas as lb
import pygmsh
import os

# Parameters -------------------------------------------------------
# Geometry (mm)
L = 60
H = 30
mesh_size = 0.5

# Material (MPa) — orthotropic, fiber-reinforced composite
E1 = 130e3   # Young's modulus along fiber
E2 = 10e3    # Young's modulus transverse to fiber
G12 = 4.3e3  # In-plane shear modulus
nu = 0.22    # Major Poisson's ratio

# Optimization
p = 3                          # SIMP penalty exponent
target_fraction = 0.5          # Target volume fraction
filter_radius = 1.2            # Helmholtz filter radius for density
filter_radius_orientation = 5  # Helmholtz filter radius for orientation

# Stacking sequence [+10/-10/-10/+10] — equal ply thickness
# Offset difference = 20 deg -> 180 deg periodicity only.
# With a12 >= 0 (theta in [0,90]), no equivalent angles exist -> no jumps.
stacking = [0]  # degrees

# Boundary conditions
delta = 2.5              # Half-width of the load application zone (mm)
force_vector = (0, -4)   # Downward distributed load (N/mm)

# Output
_HERE = os.path.dirname(__file__)
output_path = os.path.join(_HERE, "outputs", "cantilever_10")

# Geometry ---------------------------------------------------------------
with pygmsh.geo.Geometry() as geom:
    geom.add_polygon([
        [0., 0.],
        [L,  0.],
        [L,  H],
        [0., H],
    ], mesh_size=mesh_size)
    mesh_data = geom.generate_mesh()

geometry = lb.Geometry.from_pygmsh(
    mesh_data,
    save_path=f"{output_path}/mesh.xml"
)

# Boundary conditions ----------------------------------------------------
EPS = 1e-10
bcs = lb.BoundaryConditions(geometry)

# Simply supported: pin at bottom-left, roller at bottom-right
bcs.fix_x(x=0.0, y=0.0, pointwise=True)
bcs.fix_y(x=0.0, y=0.0, pointwise=True)
bcs.fix_y(x=L,   y=0.0, pointwise=True)

# Downward load distributed over the top-center strip
bcs.apply_load(
    selector=lambda x, y: L/2 - delta < x < L/2 + delta and y > H - EPS,
    force=force_vector,
    marker=1,
)

# Material ---------------------------------------------------------------
material = lb.OrthotropicMaterial(
    E1=E1,
    E2=E2,
    G12=G12,
    nu12=nu,
    name="0",
)

# Problem statement ------------------------------------------------------
problem = lb.TopologyOptimization(
    geometry=geometry,
    material=material,
    boundaries=bcs,
    target_density=target_fraction,
    penalty_exponent=p,
    filter_radius_density=filter_radius,
    filter_radius_orientation=filter_radius_orientation,
    output_dir=output_path,
    stacking_sequence=stacking,                        
    orientation_bounds=[(-1, 1), (-1, 1), (-1, 1)],     # a12 >= 0 -> theta >= 0
)

# Optimization -----------------------------------------------------------
result = problem.optimize(
    algorithm="MMA",
    max_iterations=200,
    tolerance=1e-5,
    density_initial=target_fraction,
)

# Results ----------------------------------------------------------------
result.summary()
result.plot_convergence()
