"""Libertas - Extended fullcontrol with topology optimization features."""

__version__ = "0.1.0"

# Import libertas high-level API (always available)
from libertas.geometry import Geometry
from libertas.boundaries import BoundaryConditions
from libertas.materials import OrthotropicMaterial, MaterialLibrary
from libertas.problem import TopologyOptimization, OptimizationResult

__all__ = [
    "__version__",
    # High-level API
    "Geometry",
    "BoundaryConditions",
    "OrthotropicMaterial",
    "MaterialLibrary",
    "TopologyOptimization",
    "OptimizationResult",
]

# Optional: Try to import fullcontrol (3D printing)
try:
    from libertas.fullcontrol.fullcontrol import *
    from libertas.fullcontrol import fullcontrol as fc
    __all__.append("fc")
except (ImportError, ModuleNotFoundError):
    fc = None

# Optional: Try to import pytop (for advanced usage)
try:
    from libertas import pytop
    __all__.append("pytop")
except (ImportError, ModuleNotFoundError):
    pytop = None
