"""Anisotropic topology optimization problem definition."""

from typing import Optional, Dict, Any, Union, Tuple, List
from pathlib import Path

from libertas.geometry import Geometry
from libertas.boundaries import BoundaryConditions
from libertas.materials import OrthotropicMaterial

try:
    from libertas.pytop import pytop as pt
    from libertas.pytop.pytop.physics.elasticity import (
        linear_2D_orthotropic_elasticity_bilinear_form_tensor,
        orthotropic_2d_plane_stress_tensor
    )
    from libertas.pytop.pytop.physics.utils import penalized_weight, isoparametric_2D_box_to_triangle, sgn
except ImportError:
    from libertas import pytop as pt
    from pytop.physics.elasticity import (
        linear_2D_orthotropic_elasticity_bilinear_form_tensor,
        orthotropic_2d_plane_stress_tensor
    )
    from pytop.physics.utils import penalized_weight, isoparametric_2D_box_to_triangle, sgn


class AnisotropicTopologyOptimization:
    """
    Anisotropic topology optimization with density and orientation design variables.

    This is specialized for orthotropic material optimization with orientation,
    matching the example.py workflow.
    """

    def __init__(
        self,
        geometry: Geometry,
        material: OrthotropicMaterial,
        boundaries: BoundaryConditions,
        target_density: float = 0.4,
        penalty_exponent: float = 3.0,
        penalty_epsilon: float = 1e-2,
        filter_radius_density: float = 0.1,
        filter_radius_orientation: float = 0.1,
        sgn_sharpness: float = 10.0,
        output_dir: Optional[str] = None
    ) -> None:
        """
        Initialize anisotropic topology optimization problem.

        Args:
            geometry: Geometry instance with mesh
            material: Orthotropic material properties
            boundaries: Boundary conditions
            target_density: Target volume fraction (0-1)
            penalty_exponent: SIMP penalty exponent (p)
            penalty_epsilon: Small value to prevent singularity in SIMP
            filter_radius_density: Helmholtz filter radius for density
            filter_radius_orientation: Helmholtz filter radius for orientation
            sgn_sharpness: Sharpness parameter for sgn function in orientation coupling
            output_dir: Output directory for results
        """
        self.geometry = geometry
        self.material = material
        self.boundaries = boundaries
        self.target_density = target_density
        self.penalty_exponent = penalty_exponent
        self.penalty_epsilon = penalty_epsilon
        self.filter_radius_density = filter_radius_density
        self.filter_radius_orientation = filter_radius_orientation
        self.sgn_sharpness = sgn_sharpness
        self.output_dir = Path(output_dir) if output_dir else Path("./output")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Function spaces (created on demand)
        self._spaces: Dict[str, Any] = {}

        # Solution fields
        self._displacement: Optional[Any] = None

        # Pytop components (created during optimize)
        self._design_vars_pytop: Optional[pt.DesignVariables] = None
        self._pytop_problem: Optional[pt.ProblemStatement] = None
        self._optimizer: Optional[pt.NloptOptimizer] = None

        # Output files
        self._results_file: Optional[pt.XDMFFile] = None
        self._xml_dir: Optional[Path] = None
        self._h5_dir: Optional[Path] = None

    def optimize(
        self,
        algorithm: str = "MMA",
        max_iterations: int = 200,
        tolerance: float = 1e-4,
        verbosity: int = 1,
        density_initial: float = None,
        orientation_initial: Optional[Tuple[float, float, float]] = None,
        orientation_tolerance: float = 1e-2
    ) -> "OptimizationResult":
        """
        Run anisotropic topology optimization.

        Args:
            algorithm: Optimization algorithm ("MMA", "BFGS", etc.)
            max_iterations: Maximum number of iterations
            tolerance: Convergence tolerance
            verbosity: Verbosity level (0=silent, 1=normal, 2=verbose)
            density_initial: Initial density value (default: target_density)
            orientation_initial: Initial orientation parameters (default: (-1+TOL, -1+TOL, 0))
            orientation_tolerance: Tolerance for orientation initial values

        Returns:
            OptimizationResult with optimized fields
        """
        # Set default orientation initial values
        if orientation_initial is None:
            orientation_initial = (
                -1.0 + orientation_tolerance,
                -1.0 + orientation_tolerance,
                0.0
            )

        # Build the problem
        self._build_problem(density_initial, orientation_initial)

        # Setup optimizer
        opt_algorithm = f"LD_{algorithm}" if not algorithm.startswith("LD_") else algorithm

        self._optimizer = pt.NloptOptimizer(
            self._design_vars_pytop,
            self._pytop_problem,
            opt_algorithm
        )

        self._optimizer.set_maxeval(max_iterations)
        self._optimizer.set_ftol_rel(tolerance)
        self._optimizer.set_param("verbosity", verbosity)

        # Run optimization
        log_file = str(self.output_dir / "optimization_log.csv")
        self._optimizer.run(log_file)

        # Close XDMF file
        if self._results_file:
            self._results_file.close()

        # Save final density and orientation to XML
        self._save_final_results_to_xml()

        # Return results
        return OptimizationResult(
            problem=self,
            log_file=log_file,
            output_dir=self.output_dir
        )

    def _build_problem(
        self,
        density_initial: Optional[float],
        orientation_initial: Tuple[float, float, float]
    ) -> None:
        """Build pytop problem from high-level specification."""
        # Create output directory structure
        h5_dir = self.output_dir / "h5"
        xml_dir = self.output_dir / "xml"
        h5_dir.mkdir(parents=True, exist_ok=True)
        xml_dir.mkdir(parents=True, exist_ok=True)

        # Create function spaces
        self._spaces["displacement"] = self.geometry.get_function_space("CG", 1, vector=True)
        self._spaces["scalar"] = self.geometry.get_function_space("CG", 1, vector=False)
        self._spaces["vector3"] = self.geometry.get_function_space("CG", 1, vector=True, dim=3)
        self._spaces["tensor"] = self.geometry.get_tensor_function_space("CG", 1)

        # Create displacement function
        self._displacement = pt.Function(self._spaces["displacement"], name="displacement")

        # Save mesh to xml
        self.geometry.save(str(xml_dir / "mesh.xml"))

        # Postprocessing function for orientation
        def postprocess_orientation(x: Any) -> Any:
            diagonals = isoparametric_2D_box_to_triangle(x[0], x[1])
            coupling_factor = pt.sqrt(diagonals[0] * diagonals[1]) * sgn(x[2], self.sgn_sharpness)
            vector = pt.project(
                pt.as_vector([diagonals[0], diagonals[1], coupling_factor]),
                self._spaces["vector3"]
            )
            return vector

        # Build design variables
        self._design_vars_pytop = pt.DesignVariables()

        # Density variable - no individual recording, only in combined results.xdmf
        density_init = density_initial if density_initial is not None else self.target_density
        self._design_vars_pytop.register(
            self._spaces["scalar"],
            "density",
            [density_init],
            [(0, 1)],
            lambda x: pt.helmholtz_filter(x, R=self.filter_radius_density)
        )

        # Orientation variable - no individual recording, only in combined results.xdmf
        self._design_vars_pytop.register(
            self._spaces["vector3"],
            "orientation",
            list(orientation_initial),
            [(-1, 1), (-1, 1), (-1, 1)],
            lambda x: pt.helmholtz_filter(x, R=self.filter_radius_orientation),
            postprocess_orientation
        )

        # Build Dirichlet BCs
        self._bcs = self.boundaries.build_dirichlet_bcs(self._spaces["displacement"])

        # Build Neumann BCs
        self._ds, self._forces = self.boundaries.build_neumann_bcs()

        # Create single XDMF output file for all fields in h5/ directory
        self._results_file = pt.XDMFFile(str(h5_dir / "results.xdmf"))
        self._results_file.parameters["flush_output"] = True
        self._results_file.parameters["functions_share_mesh"] = True
        self._results_file.parameters["rewrite_function_mesh"] = False

        # Store paths for later use
        self._xml_dir = xml_dir
        self._h5_dir = h5_dir

        # Create pytop problem
        self._pytop_problem = self._create_pytop_problem()

    def _create_pytop_problem(self) -> pt.ProblemStatement:
        """Create pytop ProblemStatement for anisotropic optimization."""
        problem = self

        class AnisotropicProblem(pt.ProblemStatement):
            def objective(self, design_variables: Dict, iter_num: int = 0) -> float:
                """Compute compliance objective with anisotropic material."""
                # Get design variables
                rho = design_variables["density"]
                orientation_tensor_elems = design_variables["orientation"]

                # Build orientation tensor
                diagonals = isoparametric_2D_box_to_triangle(
                    orientation_tensor_elems[0],
                    orientation_tensor_elems[1]
                )
                coupling_factor = pt.sqrt(diagonals[0] * diagonals[1]) * sgn(orientation_tensor_elems[2], problem.sgn_sharpness)

                orientation_tensor_2 = pt.as_tensor([
                    [diagonals[0], coupling_factor],
                    [coupling_factor, diagonals[1]]
                ])
                orientation_tensor_4 = pt.outer(orientation_tensor_2, orientation_tensor_2)

                # Penalty
                penalty = (
                    penalized_weight(rho, problem.penalty_exponent, eps=problem.penalty_epsilon) *
                    pt.sqrt(diagonals[0]**2 + diagonals[1]**2)
                )

                # Build bilinear form
                u = pt.TrialFunction(problem._spaces["displacement"])
                du = pt.TestFunction(problem._spaces["displacement"])

                a = linear_2D_orthotropic_elasticity_bilinear_form_tensor(
                    u, du,
                    problem.material.E1,
                    problem.material.E2,
                    problem.material.G12,
                    problem.material.nu12,
                    orientation_tensor_2,
                    orientation_tensor_4,
                    penalty
                )

                # Load term
                if problem._forces:
                    L = sum(
                        pt.inner(force, du) * problem._ds(marker)
                        for marker, force in problem._forces.items()
                    )
                else:
                    L = pt.inner(pt.Constant((0, 0)), du) * pt.dx

                # Solve
                pt.solve(a == L, problem._displacement, problem._bcs)

                # Compute compliance
                if problem._forces:
                    compliance = sum(
                        pt.assemble(pt.inner(force, problem._displacement) * problem._ds(marker))
                        for marker, force in problem._forces.items()
                    )
                else:
                    compliance = 0.0

                # Record outputs (only during forward pass, not gradient computation)
                if iter_num is not None:
                    time = float(iter_num)

                    # Write displacement
                    problem._displacement.rename("displacement", "displacement")
                    problem._results_file.write(problem._displacement, time)

                    # Compute and write stress tensor
                    stress_tensor = orthotropic_2d_plane_stress_tensor(
                        problem._displacement,
                        problem.material.E1,
                        problem.material.E2,
                        problem.material.G12,
                        problem.material.nu12,
                        orientation_tensor_2,
                        orientation_tensor_4
                    )
                    stress_function = pt.project(stress_tensor, problem._spaces["tensor"])
                    stress_function.rename("stress", "stress")
                    problem._results_file.write(stress_function, time)

                    # Write density
                    rho_function = pt.Function(problem._spaces["scalar"])
                    rho_function.assign(rho)
                    rho_function.rename("density", "density")
                    problem._results_file.write(rho_function, time)

                    # Write orientation tensor (the postprocessed 2nd order tensor as a vector)
                    orientation_vector = pt.as_vector([
                        orientation_tensor_2[0, 0],  # T_11
                        orientation_tensor_2[1, 1],  # T_22
                        orientation_tensor_2[0, 1]   # T_12
                    ])
                    orientation_function = pt.project(orientation_vector, problem._spaces["vector3"])
                    orientation_function.rename("orientation", "orientation")
                    problem._results_file.write(orientation_function, time)

                return compliance

            def constraint_volume(self, design_variables: Dict, iter_num: int = 0) -> float:
                """Volume constraint."""
                rho = design_variables["density"]
                unitary = pt.project(pt.Constant(1), problem._spaces["scalar"])
                volume_fraction = pt.assemble(rho * pt.dx) / pt.assemble(unitary * pt.dx)

                return volume_fraction - problem.target_density

        return AnisotropicProblem()

    def _save_final_results_to_xml(self) -> None:
        """Save final density and orientation fields to XML format."""
        try:
            # Get final design variables using dictionary-like access
            final_density = self._design_vars_pytop["density"]
            final_orientation = self._design_vars_pytop["orientation"]

            print(f"Saving final results to {self._xml_dir}...")

            # Save density to XML
            density_file = pt.File(str(self._xml_dir / "density.xml"))
            density_file << final_density
            print(f"  ✓ Saved density.xml")

            # Save orientation to XML
            orientation_file = pt.File(str(self._xml_dir / "orientation.xml"))
            orientation_file << final_orientation
            print(f"  ✓ Saved orientation.xml")

        except Exception as e:
            import traceback
            print(f"Warning: Could not save final results to XML: {e}")
            traceback.print_exc()


class OptimizationResult:
    """Results from anisotropic topology optimization."""

    def __init__(
        self,
        problem: AnisotropicTopologyOptimization,
        log_file: str,
        output_dir: Path
    ) -> None:
        """
        Initialize result.

        Args:
            problem: The optimization problem
            log_file: Path to log file
            output_dir: Output directory
        """
        self.problem = problem
        self.log_file = log_file
        self.output_dir = output_dir

    def summary(self) -> None:
        """Print optimization summary."""
        print(f"\n{'='*60}")
        print(f"Anisotropic Topology Optimization Complete")
        print(f"{'='*60}")
        print(f"Results directory: {self.output_dir}")
        print(f"Log file: {self.log_file}")
        print(f"\nOutput structure:")
        print(f"  h5/results.xdmf - Combined XDMF file with all fields:")
        print(f"    - displacement  (vector field)")
        print(f"    - stress        (tensor field)")
        print(f"    - density       (scalar field)")
        print(f"    - orientation   (vector field)")
        print(f"  xml/ - Final result XML files:")
        print(f"    - mesh.xml")
        print(f"    - density.xml")
        print(f"    - orientation.xml")
        print(f"\nView in ParaView:")
        print(f"  paraview {self.output_dir}/h5/results.xdmf")
        print(f"\n  All fields available in single file!")
        print(f"  Use 'Warp By Vector' filter with displacement")
        print(f"  Color by: density, stress components, etc.")
        print(f"{'='*60}\n")

    def get_compliance_history(self) -> List[float]:
        """Get compliance history from log file."""
        import pandas as pd

        if Path(self.log_file).exists():
            try:
                df = pd.read_csv(self.log_file)
                return df["objective"].tolist() if "objective" in df.columns else []
            except Exception:
                return []
        return []

    def plot_convergence(self) -> None:
        """Plot convergence history."""
        try:
            import matplotlib.pyplot as plt

            history = self.get_compliance_history()
            if not history:
                print("No convergence data available")
                return

            plt.figure(figsize=(10, 6))
            plt.semilogy(history)
            plt.xlabel("Iteration")
            plt.ylabel("Compliance (log scale)")
            plt.title("Optimization Convergence")
            plt.grid(True)
            plt.savefig(self.output_dir / "convergence.png", dpi=150, bbox_inches='tight')
            plt.close()

            print(f"Convergence plot saved to: {self.output_dir / 'convergence.png'}")

        except ImportError:
            print("matplotlib not installed. Cannot create convergence plot.")
        except Exception as e:
            print(f"Error creating convergence plot: {e}")


# Alias for shorter name
TopologyOptimization = AnisotropicTopologyOptimization
