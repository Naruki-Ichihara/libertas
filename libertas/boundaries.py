"""Boundary condition handling for libertas."""

from typing import Callable, Optional, Union, Tuple, List, Any
from libertas.geometry import Geometry

try:
    from libertas.pytop import pytop as pt
except ImportError:
    from libertas import pytop as pt


class BoundaryConditions:
    """
    Flexible boundary condition specification for topology optimization.

    Supports coordinate-based selectors, label-based selection,
    and custom SubDomain classes.
    """

    def __init__(self, geometry: Geometry) -> None:
        """
        Initialize boundary conditions for a geometry.

        Args:
            geometry: Geometry instance
        """
        self.geometry = geometry
        self._dirichlet_bcs: List[dict] = []
        self._neumann_bcs: List[dict] = []
        self._boundary_domains: Optional[pt.MeshFunction] = None

    def fix_x(
        self,
        selector: Optional[Union[Callable, float]] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        tolerance: float = 1e-6,
        label: Optional[str] = None,
        pointwise: bool = False
    ) -> "BoundaryConditions":
        """
        Fix displacement in x-direction.

        Args:
            selector: Function (x, y, [z]) -> bool or x-coordinate value
            x, y, z: Coordinate constraints
            tolerance: Tolerance for coordinate matching
            label: Physical group label from mesh file
            pointwise: If True, use pointwise method for single point BCs

        Returns:
            Self for method chaining
        """
        subdomain = self._make_subdomain(
            selector, x, y, z, tolerance, label, pointwise
        )

        self._dirichlet_bcs.append({
            "subdomain": subdomain,
            "component": 0,  # x-component
            "value": 0.0,
            "label": label or "fix_x",
            "pointwise": pointwise
        })

        return self

    def fix_y(
        self,
        selector: Optional[Union[Callable, float]] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        tolerance: float = 1e-6,
        label: Optional[str] = None,
        pointwise: bool = False
    ) -> "BoundaryConditions":
        """
        Fix displacement in y-direction.

        Args:
            selector: Function (x, y, [z]) -> bool or y-coordinate value
            x, y, z: Coordinate constraints
            tolerance: Tolerance for coordinate matching
            label: Physical group label from mesh file
            pointwise: If True, use pointwise method for single point BCs

        Returns:
            Self for method chaining
        """
        subdomain = self._make_subdomain(
            selector, x, y, z, tolerance, label, pointwise
        )

        self._dirichlet_bcs.append({
            "subdomain": subdomain,
            "component": 1,  # y-component
            "value": 0.0,
            "label": label or "fix_y",
            "pointwise": pointwise
        })

        return self

    def fix_z(
        self,
        selector: Optional[Union[Callable, float]] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        tolerance: float = 1e-6,
        label: Optional[str] = None,
        pointwise: bool = False
    ) -> "BoundaryConditions":
        """
        Fix displacement in z-direction.

        Args:
            selector: Function (x, y, z) -> bool or z-coordinate value
            x, y, z: Coordinate constraints
            tolerance: Tolerance for coordinate matching
            label: Physical group label from mesh file
            pointwise: If True, use pointwise method for single point BCs

        Returns:
            Self for method chaining
        """
        subdomain = self._make_subdomain(
            selector, x, y, z, tolerance, label, pointwise
        )

        self._dirichlet_bcs.append({
            "subdomain": subdomain,
            "component": 2,  # z-component
            "value": 0.0,
            "label": label or "fix_z",
            "pointwise": pointwise
        })

        return self

    def fix_displacement(
        self,
        selector: Optional[Callable] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        tolerance: float = 1e-6,
        value: Union[float, Tuple[float, ...]] = 0.0,
        label: Optional[str] = None,
        pointwise: bool = False
    ) -> "BoundaryConditions":
        """
        Fix all displacement components.

        Args:
            selector: Function (x, y, [z]) -> bool
            x, y, z: Coordinate constraints
            tolerance: Tolerance for coordinate matching
            value: Fixed displacement value(s)
            label: Physical group label from mesh file
            pointwise: If True, use pointwise method for single point BCs

        Returns:
            Self for method chaining
        """
        subdomain = self._make_subdomain(
            selector, x, y, z, tolerance, label, pointwise
        )

        if isinstance(value, (int, float)):
            value = (value,) * self.geometry.dim

        self._dirichlet_bcs.append({
            "subdomain": subdomain,
            "component": None,  # All components
            "value": value,
            "label": label or "fix_displacement",
            "pointwise": pointwise
        })

        return self

    def apply_load(
        self,
        selector: Optional[Callable] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        tolerance: float = 1e-6,
        force: Tuple[float, ...] = (0.0, 0.0),
        label: Optional[str] = None,
        marker: int = 1
    ) -> "BoundaryConditions":
        """
        Apply Neumann (traction/load) boundary condition.

        Args:
            selector: Function (x, y, [z]) -> bool
            x, y, z: Coordinate constraints
            tolerance: Tolerance for coordinate matching
            force: Force vector
            label: Physical group label from mesh file
            marker: Boundary marker ID

        Returns:
            Self for method chaining
        """
        subdomain = self._make_subdomain(selector, x, y, z, tolerance, label)

        self._neumann_bcs.append({
            "subdomain": subdomain,
            "force": pt.Constant(force),
            "marker": marker,
            "label": label or f"load_{marker}"
        })

        return self

    def add_custom(
        self,
        subdomain: pt.SubDomain,
        bc_type: str = "dirichlet",
        value: Any = 0.0,
        component: Optional[int] = None,
        force: Optional[Tuple[float, ...]] = None,
        marker: int = 1,
        label: Optional[str] = None
    ) -> "BoundaryConditions":
        """
        Add custom boundary condition using SubDomain class.

        Args:
            subdomain: Custom SubDomain instance
            bc_type: "dirichlet" or "neumann"
            value: Value for Dirichlet BC
            component: Component index (None for all)
            force: Force vector for Neumann BC
            marker: Boundary marker ID
            label: Optional label

        Returns:
            Self for method chaining
        """
        if bc_type == "dirichlet":
            self._dirichlet_bcs.append({
                "subdomain": subdomain,
                "component": component,
                "value": value,
                "label": label or "custom_dirichlet"
            })
        elif bc_type == "neumann":
            self._neumann_bcs.append({
                "subdomain": subdomain,
                "force": pt.Constant(force or (0.0,) * self.geometry.dim),
                "marker": marker,
                "label": label or f"custom_neumann_{marker}"
            })
        else:
            raise ValueError(f"Unknown BC type: {bc_type}")

        return self

    def build_dirichlet_bcs(self, function_space: Any) -> List[pt.DirichletBC]:
        """
        Build list of FEniCS DirichletBC objects.

        Args:
            function_space: Function space for displacement

        Returns:
            List of DirichletBC objects
        """
        bcs = []

        for bc_spec in self._dirichlet_bcs:
            subdomain = bc_spec["subdomain"]
            component = bc_spec["component"]
            value = bc_spec["value"]
            pointwise = bc_spec.get("pointwise", False)

            # For pointwise BCs, use method="pointwise"
            method = "pointwise" if pointwise else "topological"

            if component is not None:
                # Single component
                bc = pt.DirichletBC(
                    function_space.sub(component),
                    pt.Constant(value),
                    subdomain,
                    method=method
                )
            else:
                # All components
                bc = pt.DirichletBC(
                    function_space,
                    pt.Constant(value),
                    subdomain,
                    method=method
                )

            bcs.append(bc)

        return bcs

    def build_neumann_bcs(self) -> Tuple[pt.MeshFunction, dict]:
        """
        Build Neumann boundary conditions as boundary domains.

        Returns:
            Tuple of (boundary_domains, force_dict)
        """
        if not self._neumann_bcs:
            return None, {}

        # Create boundary domains
        subdomains = [bc["subdomain"] for bc in self._neumann_bcs]
        boundary_domains = pt.make_noiman_boundary_domains(
            self.geometry.mesh,
            subdomains,
            True
        )

        # Create force dictionary
        force_dict = {}
        for i, bc in enumerate(self._neumann_bcs, start=1):
            force_dict[i] = bc["force"]

        self._boundary_domains = boundary_domains

        return boundary_domains, force_dict

    def _make_subdomain(
        self,
        selector: Optional[Union[Callable, float]],
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        tolerance: float,
        label: Optional[str],
        pointwise: bool = False
    ) -> pt.SubDomain:
        """
        Create SubDomain from various selector types.

        Args:
            selector: Callable or coordinate value
            x, y, z: Coordinate constraints
            tolerance: Tolerance for matching
            label: Physical group label

        Returns:
            SubDomain instance
        """
        dim = self.geometry.dim

        # Label-based (from mesh file)
        if label is not None:
            # This would require mesh with physical groups
            # For now, raise not implemented
            raise NotImplementedError(
                "Label-based boundary selection not yet implemented. "
                "Use coordinate-based or custom SubDomain."
            )

        # Callable selector
        if callable(selector):
            return self._subdomain_from_callable(selector, dim, pointwise)

        # Coordinate-based
        conditions = []
        if x is not None:
            conditions.append(lambda pos: abs(pos[0] - x) < tolerance)
        if y is not None:
            conditions.append(lambda pos: abs(pos[1] - y) < tolerance)
        if z is not None and dim == 3:
            conditions.append(lambda pos: abs(pos[2] - z) < tolerance)

        if not conditions:
            raise ValueError("Must provide selector, coordinates, or label")

        def combined_selector(pos: Any) -> bool:
            return all(cond(pos) for cond in conditions)

        return self._subdomain_from_callable(combined_selector, dim, pointwise)

    def _subdomain_from_callable(
        self, func: Callable, dim: int, pointwise: bool = False
    ) -> pt.SubDomain:
        """
        Create SubDomain class from callable.

        Args:
            func: Callable that takes coordinates and returns bool
            dim: Spatial dimension
            pointwise: If True, ignore on_boundary check (for single point BCs)

        Returns:
            SubDomain instance
        """
        class CallableSubDomain(pt.SubDomain):
            def inside(self, x: Any, on_boundary: bool) -> bool:
                if not pointwise and not on_boundary:
                    return False
                try:
                    return func(x[0], x[1], x[2] if dim == 3 else None)
                except (IndexError, TypeError):
                    try:
                        return func(x[0], x[1])
                    except TypeError:
                        return func(x)

        return CallableSubDomain()
