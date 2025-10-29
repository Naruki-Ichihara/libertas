"""Libertas - Extended fullcontrol with additional features."""

__version__ = "0.1.0"

# Re-export all fullcontrol functionality
from libertas.fullcontrol.fullcontrol import *

# Import fullcontrol submodules for direct access
from libertas.fullcontrol import fullcontrol as fc

__all__ = ["__version__", "fc"]
