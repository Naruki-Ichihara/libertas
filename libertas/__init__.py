"""Libertas - Extended fullcontrol with topology optimization features."""

__version__ = "0.1.0"

# Import libertas high-level API (always available)
from libertas.geometry import Geometry
from libertas.boundaries import BoundaryConditions
from libertas.materials import OrthotropicMaterial, MaterialLibrary
from libertas.problem import TopologyOptimization, OptimizationResult
from libertas.postprocess import (
    read_density_from_xml,
    read_density_from_xml_fenics,
    plot_density,
    save_density_image,
    extract_contour_svg,
    mesh_from_svg,
    generate_stripe_pattern,
    stripe_to_image,
    stripe_to_svg,
)
from libertas.path import Path
from libertas.layer import Layer
from libertas.model import Model
from libertas.svg_parser import parse_svg_to_paths, save_paths_to_svg
from libertas.gcode import layer_to_gcode, svg_to_gcode, model_to_gcode, layer_to_json, svg_to_json
from libertas.print_params import (
    PrintParams,
    TemperatureParams,
    SpeedParams,
    ExtrusionParams,
    RetractionParams,
    CoolingParams,
    PrinterType,
    MaterialType,
)

__all__ = [
    "__version__",
    # High-level API
    "Geometry",
    "BoundaryConditions",
    "OrthotropicMaterial",
    "MaterialLibrary",
    "TopologyOptimization",
    "OptimizationResult",
    # Postprocessing
    "read_density_from_xml",
    "read_density_from_xml_fenics",
    "plot_density",
    "save_density_image",
    "extract_contour_svg",
    "mesh_from_svg",
    "generate_stripe_pattern",
    "stripe_to_image",
    "stripe_to_svg",
    # Path management
    "Path",
    "Layer",
    "Model",
    "parse_svg_to_paths",
    "save_paths_to_svg",
    # GCode generation
    "layer_to_gcode",
    "svg_to_gcode",
    "model_to_gcode",
    "layer_to_json",
    "svg_to_json",
    # Print parameters
    "PrintParams",
    "TemperatureParams",
    "SpeedParams",
    "ExtrusionParams",
    "RetractionParams",
    "CoolingParams",
    "PrinterType",
    "MaterialType",
]

# Optional: Mesh factory utilities (requires mesh dependencies)
try:
    from libertas.mesh_factory import (
        density_to_image,
        image_to_svg,
        svg_to_mesh,
        image_to_mesh,
        mesh_from_density,
        mesh_from_density_safe,
    )
    __all__.extend([
        "density_to_image",
        "image_to_svg",
        "svg_to_mesh",
        "image_to_mesh",
        "mesh_from_density",
        "mesh_from_density_safe"
    ])
except ImportError:
    # Dependencies not installed, mesh factory not available
    pass

# Optional: Try to import fullcontrol (3D printing)
try:
    from libertas.fullcontrol.fullcontrol import *
    from libertas.fullcontrol import fullcontrol as fc
    __all__.append("fc")
except (ImportError, ModuleNotFoundError):
    fc = None

# Optional: Try to import pytop (for advanced usage)
try:
    import pytop
    __all__.append("pytop")
except (ImportError, ModuleNotFoundError):
    pytop = None
