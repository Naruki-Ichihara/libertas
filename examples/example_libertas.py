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
target_fraction = 0.60
filter_radius = 0.4
filter_radius_orientation = 0.2

# Boundary conditions
delta = 0.2
force_vector = (0, -1)

# Directory
output_path = "output/example_libertas"

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

# Left edge: fix x-displacement
bcs.fix_x(x=0.0)
bcs.fix_y(x=0.0)

bcs.apply_load(
    selector=lambda x, y: x > L-delta and y < EPS,
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
    algorithm="MMA",
    max_iterations=200,
    tolerance=1e-5,
    density_initial=target_fraction,
)

# Results
result.summary()
result.plot_convergence()

# Extract mesh from optimization results (optional)
# This generates a triangular mesh from the optimized density field
# and saves it as mesh_from_density.xml in the xml directory
print("\nExtracting mesh from optimization results...")
mesh_data = result.extract_mesh(
    threshold=0.5,       # Density threshold
    max_area=0.1,        # Maximum triangle area (or None for auto)
    min_angle=25.0,      # Minimum angle constraint
    smoothness=0.02      # Bézier curve smoothness
)
print(f"Extracted mesh with {len(mesh_data['triangles'])} triangles")
