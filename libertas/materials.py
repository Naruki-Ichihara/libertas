"""Orthotropic material definitions for anisotropic topology optimization."""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class OrthotropicMaterial:
    """
    Orthotropic material with different properties in principal directions.

    Used for anisotropic topology optimization with fiber-reinforced
    composites or materials with directional properties.
    """

    E1: float = 6.158e3  # Young's modulus in direction 1 [Pa]
    E2: float = 2.845e3  # Young's modulus in direction 2 [Pa]
    E3: float = None  # Young's modulus in direction 3 [Pa] (for 3D, defaults to E2)
    G12: float = 741  # Shear modulus in plane 12 [Pa]
    G23: float = None  # Shear modulus in plane 23 [Pa] (for 3D, defaults to G12)
    G13: float = None  # Shear modulus in plane 13 [Pa] (for 3D, defaults to G12)
    nu12: float = 0.22  # Poisson's ratio 12 [-]
    nu23: float = None  # Poisson's ratio 23 [-] (for 3D, defaults to nu12)
    nu13: float = None  # Poisson's ratio 13 [-] (for 3D, defaults to nu12)
    name: str = "Orthotropic Material"

    def __post_init__(self) -> None:
        """Validate and set default 3D properties."""
        if self.E1 <= 0 or self.E2 <= 0:
            raise ValueError("Young's moduli must be positive")

        if self.G12 <= 0:
            raise ValueError("Shear modulus must be positive")

        # Set defaults for 3D if not provided
        if self.E3 is None:
            self.E3 = self.E2

        if self.G23 is None:
            self.G23 = self.G12

        if self.G13 is None:
            self.G13 = self.G12

        if self.nu23 is None:
            self.nu23 = self.nu12

        if self.nu13 is None:
            self.nu13 = self.nu12

    @property
    def nu21(self) -> float:
        """Poisson's ratio 21 (from reciprocal relation)."""
        return self.nu12 * self.E2 / self.E1

    def to_dict(self) -> Dict[str, Any]:
        """Convert material properties to dictionary."""
        return {
            "name": self.name,
            "type": "OrthotropicMaterial",
            "E1": self.E1,
            "E2": self.E2,
            "E3": self.E3,
            "G12": self.G12,
            "G23": self.G23,
            "G13": self.G13,
            "nu12": self.nu12,
            "nu21": self.nu21,
            "nu23": self.nu23,
            "nu13": self.nu13
        }


# Material library - common orthotropic materials
class MaterialLibrary:
    """Library of common orthotropic materials for topology optimization."""

    # Unidirectional fiber composites
    CARBON_FIBER_EPOXY = OrthotropicMaterial(
        E1=150e9,
        E2=10e9,
        G12=5e9,
        nu12=0.3,
        name="Carbon Fiber/Epoxy (UD)"
    )

    GLASS_FIBER_EPOXY = OrthotropicMaterial(
        E1=45e9,
        E2=12e9,
        G12=5.5e9,
        nu12=0.28,
        name="Glass Fiber/Epoxy (UD)"
    )

    ARAMID_FIBER_EPOXY = OrthotropicMaterial(
        E1=76e9,
        E2=5.5e9,
        G12=2.3e9,
        nu12=0.34,
        name="Aramid Fiber/Epoxy (UD)"
    )

    # Natural fiber composites
    FLAX_FIBER_EPOXY = OrthotropicMaterial(
        E1=30e9,
        E2=7e9,
        G12=3e9,
        nu12=0.35,
        name="Flax Fiber/Epoxy (UD)"
    )

    # 3D printing materials (anisotropic due to layer deposition)
    PLA_3D_PRINTED = OrthotropicMaterial(
        E1=3.5e9,   # In-plane
        E2=2.8e9,   # Through-thickness
        G12=1.2e9,
        nu12=0.36,
        name="PLA (3D Printed, 0° raster)"
    )

    ABS_3D_PRINTED = OrthotropicMaterial(
        E1=2.3e9,   # In-plane
        E2=1.9e9,   # Through-thickness
        G12=0.9e9,
        nu12=0.35,
        name="ABS (3D Printed, 0° raster)"
    )

    # Wood (natural orthotropic material)
    WOOD_SPRUCE = OrthotropicMaterial(
        E1=11e9,    # Along grain
        E2=0.37e9,  # Across grain (radial)
        G12=0.69e9,
        nu12=0.37,
        name="Spruce Wood"
    )

    # Generic material for testing (from example.py)
    GENERIC_COMPOSITE = OrthotropicMaterial(
        E1=6.158e3,
        E2=2.845e3,
        G12=741,
        nu12=0.22,
        name="Generic Composite (Example)"
    )

    @classmethod
    def list_materials(cls) -> list:
        """List all available materials."""
        return [
            attr for attr in dir(cls)
            if not attr.startswith('_') and isinstance(getattr(cls, attr), OrthotropicMaterial)
        ]

    @classmethod
    def get_material(cls, name: str) -> OrthotropicMaterial:
        """
        Get material by name.

        Args:
            name: Material name (case-insensitive)

        Returns:
            OrthotropicMaterial instance

        Raises:
            KeyError: If material not found
        """
        name_upper = name.upper().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")

        if hasattr(cls, name_upper):
            return getattr(cls, name_upper)

        raise KeyError(
            f"Material '{name}' not found. "
            f"Available: {', '.join(cls.list_materials())}"
        )
