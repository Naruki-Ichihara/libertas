"""
Simply-supported beam: simultaneous topology and fiber orientation optimization.

Problem setup:
    - Rectangular domain (L x H), simply supported at both bottom corners
    - Downward point load applied at the bottom center (width 2*delta)
    - Orthotropic material (carbon-fiber-like) with SIMP penalization
    - Design variables: element density (rho) and fiber orientation (theta)
    - Objective: minimize structural compliance
    - Constraint: volume fraction <= target_fraction

Outputs (outputs/cantilever_problem/):
    h5/results.xdmf     - displacement, stress, density, orientation per iteration
    xml/density.xml     - final optimized density field
    xml/orientation.xml - final optimized orientation field
"""

import libertas as lb
import pygmsh

# Parameters -------------------------------------------------------
# Geometry (mm)
L = 100
H = 50
mesh_size = .5

# Material (MPa) — orthotropic, fiber-reinforced composite
E1 = 370e3   # Young's modulus along fiber
E2 = 250e3   # Young's modulus transverse to fiber
G12 = 100e3  # In-plane shear modulus
nu = 0.22    # Major Poisson's ratio

# Optimization
p = 3                         # SIMP penalty exponent
target_fraction = 0.30        # Target volume fraction
filter_radius = 1             # Helmholtz filter radius for density
filter_radius_orientation = 5 # Helmholtz filter radius for orientation (larger = smoother)

# Boundary conditions
delta = 1.                    # Half-width of the load application zone
force_vector = (0, -10)       # Downward point load (N/mm)

# Directory
output_path = "outputs/cantilever_problem"

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
EPS = 1e-10

bcs = lb.BoundaryConditions(geometry)

# Simply supported: pin at bottom-left (fix x and y), roller at bottom-right (fix y only)
# pointwise=True applies the BC to a single node rather than an edge
bcs.fix_x(x=0.0, y=0.0, pointwise=True)
bcs.fix_y(x=0.0, y=0.0, pointwise=True)
bcs.fix_y(x=L,   y=0.0, pointwise=True)

# Downward load distributed over the bottom-center strip
bcs.apply_load(
    selector=lambda x, y: L/2-delta < x < L/2+delta and y < EPS,
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
    filter_radius_density=filter_radius,
    filter_radius_orientation=filter_radius_orientation,
    output_dir=output_path
)

# Optimization -----------------------------------------------------------
result = problem.optimize(
    algorithm="MMA",        # Method of Moving Asymptotes (gradient-based)
    max_iterations=50,
    tolerance=1e-5,
    density_initial=target_fraction,
)

# Results
result.summary()
result.plot_convergence()