import pathlib

import libertas as lb
import pytop as pt
from pytop.physics import elasticity as el

output_dir = "outputs/cantilever_problem"
xml_dir = f"{output_dir}/xml/"

# Geometry (mm)
L = 100
H = 50
EPS = 1e-10

# Material (MPa) — orthotropic, fiber-reinforced composite
E1 = 370e3   # Young's modulus along fiber
E2 = 250e3   # Young's modulus transverse to fiber
G12 = 100e3  # In-plane shear modulus
nu = 0.22    # Major Poisson's ratio

# Boundary conditions
delta = 1.                    # Half-width of the load application zone
force_vector = (0, -10)       # Downward point load (N/mm)

# Import solutions (from workflow_2)
base_mesh = pt.import_external_mesh(output_dir + "/mesh.xml", planation=True)
mesh = pt.import_external_mesh(xml_dir + "mesh_from_density.xml", planation=True)
tensor_space_base = pt.VectorFunctionSpace(base_mesh, 'CG', 1, dim=3)
tensor_space = pt.VectorFunctionSpace(mesh, 'CG', 1, dim=3)
orientation_tensor_in_base = pt.read_fenics_function_from_file(xml_dir + "orientation", tensor_space_base, "orientation")

# Base ->> Trimmed space
orientation_tensor_in_base.set_allow_extrapolation(True)
orientation_tensor_elems = pt.project(orientation_tensor_in_base, tensor_space, annotate=False)

# Elasticity problem: setup Function spaces
U = pt.VectorFunctionSpace(mesh, "CG", 1)
uh = pt.Function(U, name="displacement")
u = pt.TrialFunction(U)
du = pt.TestFunction(U)

# Boundary conditions
bcs = lb.BoundaryConditions(lb.Geometry(mesh))
bcs.fix_x(lambda x: x[0] < 1 and x[1] < EPS)
bcs.fix_y(lambda x: x[0] < 1 and x[1] < EPS)
bcs.fix_y(lambda x: x[0] > (L-1) and x[1] < EPS)

bcs.apply_load(
    selector=lambda x, y: L/2-delta < x < L/2+delta and y < EPS,
    force=force_vector,
    marker=1
)

dc_boundaries = bcs.build_dirichlet_bcs(U)
ds, force_dict = bcs.build_neumann_bcs()

# Problem setup
orientation_tensor_2 = pt.as_tensor([[orientation_tensor_elems[0], orientation_tensor_elems[2]],
                                     [orientation_tensor_elems[2], orientation_tensor_elems[1]]])
orientation_tensor_4 = pt.outer(orientation_tensor_2, orientation_tensor_2)
bilinear_form = el.linear_2D_orthotropic_elasticity_bilinear_form_tensor(u, du, E1, E2, G12, nu, orientation_tensor_2, orientation_tensor_4)
linear_form = pt.inner(force_dict[1], du) * ds(1)

# Solve
pt.solve(bilinear_form == linear_form, uh, dc_boundaries)

# Postprocess: Compute stress and strain tensors
stress = el.orthotropic_2d_plane_stress_tensor(uh, E1, E2, G12, nu, orientation_tensor_2, orientation_tensor_4)
strain = el.strain(uh)

# Outputs
h5_dir = pathlib.Path(output_dir) / "h5"
h5_dir.mkdir(parents=True, exist_ok=True)

W = pt.TensorFunctionSpace(mesh, "CG", 1)
stress_func = pt.project(stress, W, annotate=False)
strain_func = pt.project(strain, W, annotate=False)

stress_func.rename("stress", "stress")
strain_func.rename("strain", "strain")

results_file = pt.XDMFFile(str(h5_dir / "fe_results.xdmf"))
results_file.parameters["flush_output"] = True
results_file.parameters["functions_share_mesh"] = True
results_file.parameters["rewrite_function_mesh"] = False

results_file.write(uh, 0.0)
results_file.write(stress_func, 0.0)
results_file.write(strain_func, 0.0)
results_file.close()
