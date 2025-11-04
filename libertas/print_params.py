"""Print parameters data classes for 3D printing configuration."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class PrinterType(Enum):
    """Common printer types."""
    GENERIC = "generic"
    PRUSA_I3 = "prusa_i3"
    PRUSA_MINI = "prusa_mini"
    PRUSA_MK4 = "prusa_mk4"
    ENDER_3 = "ender_3"
    ENDER_5_PLUS = "ender_5_plus"
    CR_10 = "cr_10"
    ULTIMAKER = "ultimaker2plus"
    BAMBULAB_X1 = "bambulab_x1"
    VORON_ZERO = "voron_zero"
    CUSTOM = "custom"


class MaterialType(Enum):
    """Common material types."""
    PLA = "pla"
    ABS = "abs"
    PETG = "petg"
    TPU = "tpu"
    NYLON = "nylon"
    ASA = "asa"
    PC = "polycarbonate"
    CUSTOM = "custom"


@dataclass
class TemperatureParams:
    """
    Temperature parameters for printing.

    Attributes:
        nozzle_temp: Nozzle temperature in Celsius
        bed_temp: Bed temperature in Celsius
        initial_layer_nozzle_temp: Optional override for first layer nozzle temp
        initial_layer_bed_temp: Optional override for first layer bed temp
        chamber_temp: Optional chamber temperature
    """
    nozzle_temp: float = 210.0
    bed_temp: float = 60.0
    initial_layer_nozzle_temp: Optional[float] = None
    initial_layer_bed_temp: Optional[float] = None
    chamber_temp: Optional[float] = None

    @classmethod
    def from_material(cls, material: MaterialType) -> "TemperatureParams":
        """
        Create temperature parameters from material type.

        Args:
            material: Material type enum

        Returns:
            TemperatureParams with typical settings for the material
        """
        presets = {
            MaterialType.PLA: cls(nozzle_temp=210, bed_temp=60),
            MaterialType.ABS: cls(nozzle_temp=240, bed_temp=100),
            MaterialType.PETG: cls(nozzle_temp=235, bed_temp=80),
            MaterialType.TPU: cls(nozzle_temp=225, bed_temp=60),
            MaterialType.NYLON: cls(nozzle_temp=250, bed_temp=80),
            MaterialType.ASA: cls(nozzle_temp=245, bed_temp=100),
            MaterialType.PC: cls(nozzle_temp=270, bed_temp=110),
        }
        return presets.get(material, cls())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'nozzle_temp': self.nozzle_temp,
            'bed_temp': self.bed_temp,
            'initial_layer_nozzle_temp': self.initial_layer_nozzle_temp,
            'initial_layer_bed_temp': self.initial_layer_bed_temp,
            'chamber_temp': self.chamber_temp,
        }


@dataclass
class SpeedParams:
    """
    Speed parameters for printing.

    Attributes:
        print_speed: Normal printing speed in mm/min
        travel_speed: Travel move speed in mm/min
        initial_layer_speed: First layer printing speed in mm/min
        outer_wall_speed: Outer perimeter speed (optional, defaults to print_speed)
        inner_wall_speed: Inner perimeter speed (optional, defaults to print_speed)
        infill_speed: Infill speed (optional, defaults to print_speed)
    """
    print_speed: float = 1000.0
    travel_speed: float = 3000.0
    initial_layer_speed: float = 500.0
    outer_wall_speed: Optional[float] = None
    inner_wall_speed: Optional[float] = None
    infill_speed: Optional[float] = None

    def get_outer_wall_speed(self) -> float:
        """Get outer wall speed, defaulting to print_speed if not set."""
        return self.outer_wall_speed if self.outer_wall_speed is not None else self.print_speed

    def get_inner_wall_speed(self) -> float:
        """Get inner wall speed, defaulting to print_speed if not set."""
        return self.inner_wall_speed if self.inner_wall_speed is not None else self.print_speed

    def get_infill_speed(self) -> float:
        """Get infill speed, defaulting to print_speed if not set."""
        return self.infill_speed if self.infill_speed is not None else self.print_speed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'print_speed': self.print_speed,
            'travel_speed': self.travel_speed,
            'initial_layer_speed': self.initial_layer_speed,
            'outer_wall_speed': self.outer_wall_speed,
            'inner_wall_speed': self.inner_wall_speed,
            'infill_speed': self.infill_speed,
        }


@dataclass
class ExtrusionParams:
    """
    Extrusion parameters.

    Attributes:
        extrusion_width: Extrusion width in mm
        extrusion_height: Layer height in mm
        initial_layer_height: First layer height (optional, defaults to extrusion_height)
        extrusion_multiplier: Flow rate multiplier (1.0 = 100%)
        filament_diameter: Filament diameter in mm
    """
    extrusion_width: float = 0.4
    extrusion_height: float = 0.2
    initial_layer_height: Optional[float] = None
    extrusion_multiplier: float = 1.0
    filament_diameter: float = 1.75

    def get_initial_layer_height(self) -> float:
        """Get initial layer height, defaulting to extrusion_height if not set."""
        return self.initial_layer_height if self.initial_layer_height is not None else self.extrusion_height

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'extrusion_width': self.extrusion_width,
            'extrusion_height': self.extrusion_height,
            'initial_layer_height': self.initial_layer_height,
            'extrusion_multiplier': self.extrusion_multiplier,
            'filament_diameter': self.filament_diameter,
        }


@dataclass
class RetractionParams:
    """
    Retraction parameters.

    Attributes:
        enabled: Enable retraction
        retraction_distance: Retraction distance in mm
        retraction_speed: Retraction speed in mm/s
        z_hop_height: Z-hop height during travel (0 = disabled)
        z_hop_enabled: Enable Z-hop during travel moves
        minimum_travel_distance: Minimum travel distance to trigger retraction in mm
        wipe_distance: Wipe distance after retraction in mm (0 = disabled)
    """
    enabled: bool = True
    retraction_distance: float = 1.0
    retraction_speed: float = 40.0
    z_hop_height: float = 0.0
    z_hop_enabled: bool = False
    minimum_travel_distance: float = 0.5
    wipe_distance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'enabled': self.enabled,
            'retraction_distance': self.retraction_distance,
            'retraction_speed': self.retraction_speed,
            'z_hop_height': self.z_hop_height,
            'z_hop_enabled': self.z_hop_enabled,
            'minimum_travel_distance': self.minimum_travel_distance,
            'wipe_distance': self.wipe_distance,
        }


@dataclass
class CoolingParams:
    """
    Cooling parameters.

    Attributes:
        fan_speed: Fan speed percentage (0-100)
        initial_layer_fan_speed: Fan speed for first layer (optional)
        minimum_layer_time: Minimum layer time in seconds (slow down if faster)
        fan_always_on: Keep fan always on
        disable_fan_first_layers: Number of initial layers with fan disabled
    """
    fan_speed: float = 100.0
    initial_layer_fan_speed: Optional[float] = None
    minimum_layer_time: float = 10.0
    fan_always_on: bool = True
    disable_fan_first_layers: int = 1

    def get_initial_layer_fan_speed(self) -> float:
        """Get initial layer fan speed, defaulting to 0 or fan_speed."""
        if self.initial_layer_fan_speed is not None:
            return self.initial_layer_fan_speed
        return 0.0 if self.disable_fan_first_layers > 0 else self.fan_speed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'fan_speed': self.fan_speed,
            'initial_layer_fan_speed': self.initial_layer_fan_speed,
            'minimum_layer_time': self.minimum_layer_time,
            'fan_always_on': self.fan_always_on,
            'disable_fan_first_layers': self.disable_fan_first_layers,
        }


@dataclass
class PrintParams:
    """
    Complete printing parameters.

    Main container for all print parameters, combining temperature, speed,
    extrusion, retraction, and cooling settings.

    Attributes:
        printer: Printer type
        material: Material type (optional)
        temperature: Temperature parameters
        speed: Speed parameters
        extrusion: Extrusion parameters
        retraction: Retraction parameters
        cooling: Cooling parameters
        primer: Primer type for initialization (False to disable, str for primer name)
        relative_extrusion: Use relative extrusion (E values)
        e_units: Extrusion units ('mm' or 'mm3')
        bed_temp_wait: Wait for bed to reach temperature (M190 vs M140)
        nozzle_temp_wait: Wait for nozzle to reach temperature (M109 vs M104)
        build_volume_x: Build volume X dimension (mm) - for safety checks
        build_volume_y: Build volume Y dimension (mm) - for safety checks
        build_volume_z: Build volume Z dimension (mm) - for safety checks
        custom_params: Additional custom parameters
    """
    printer: PrinterType = PrinterType.GENERIC
    material: Optional[MaterialType] = None
    temperature: TemperatureParams = field(default_factory=TemperatureParams)
    speed: SpeedParams = field(default_factory=SpeedParams)
    extrusion: ExtrusionParams = field(default_factory=ExtrusionParams)
    retraction: RetractionParams = field(default_factory=RetractionParams)
    cooling: CoolingParams = field(default_factory=CoolingParams)
    primer: Optional[bool | str] = 'no_primer'  # 'no_primer' to disable primer by default
    relative_extrusion: bool = True
    e_units: str = 'mm'  # 'mm' or 'mm3' (volumetric)
    bed_temp_wait: bool = False  # M190 (wait) vs M140 (no wait)
    nozzle_temp_wait: bool = False  # M109 (wait) vs M104 (no wait)
    build_volume_x: Optional[float] = None
    build_volume_y: Optional[float] = None
    build_volume_z: Optional[float] = None
    custom_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_preset(
        cls,
        printer: PrinterType = PrinterType.GENERIC,
        material: MaterialType = MaterialType.PLA
    ) -> "PrintParams":
        """
        Create PrintParams from printer and material presets.

        Args:
            printer: Printer type
            material: Material type

        Returns:
            PrintParams with appropriate settings for the combination
        """
        temp = TemperatureParams.from_material(material)
        return cls(
            printer=printer,
            material=material,
            temperature=temp
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert all parameters to a dictionary.

        Returns:
            Dictionary containing all parameters
        """
        return {
            'printer': self.printer.value,
            'material': self.material.value if self.material else None,
            'temperature': self.temperature.to_dict(),
            'speed': self.speed.to_dict(),
            'extrusion': self.extrusion.to_dict(),
            'retraction': self.retraction.to_dict(),
            'cooling': self.cooling.to_dict(),
            'primer': self.primer,
            'relative_extrusion': self.relative_extrusion,
            'e_units': self.e_units,
            'bed_temp_wait': self.bed_temp_wait,
            'nozzle_temp_wait': self.nozzle_temp_wait,
            'build_volume_x': self.build_volume_x,
            'build_volume_y': self.build_volume_y,
            'build_volume_z': self.build_volume_z,
            'custom_params': self.custom_params,
        }

    def to_gcode_kwargs(self) -> Dict[str, Any]:
        """
        Convert to kwargs suitable for layer_to_gcode() or model_to_gcode().

        Returns:
            Dictionary with parameters formatted for GCode generation functions
        """
        kwargs = {
            'printer': self.printer.value,
            'nozzle_temp': self.temperature.nozzle_temp,
            'bed_temp': self.temperature.bed_temp,
            'print_speed': self.speed.print_speed,
            'travel_speed': self.speed.travel_speed,
            'extrusion_width': self.extrusion.extrusion_width,
            'extrusion_height': self.extrusion.extrusion_height,
            'fan_speed': int(self.cooling.fan_speed) if self.cooling.fan_always_on else None,
            'retract': self.retraction.enabled,
            'relative_e': self.relative_extrusion,
            **self.custom_params
        }

        # Add primer (always include if it's a string)
        if isinstance(self.primer, str):
            kwargs['primer'] = self.primer

        # Add optional FullControl parameters if set
        if self.e_units:
            kwargs['e_units'] = self.e_units
        if self.bed_temp_wait is not None:
            kwargs['bed_temp_wait'] = self.bed_temp_wait
        if self.nozzle_temp_wait is not None:
            kwargs['nozzle_temp_wait'] = self.nozzle_temp_wait

        return kwargs

    def __repr__(self) -> str:
        """String representation."""
        material_str = f", {self.material.value}" if self.material else ""
        return (f"PrintParams({self.printer.value}{material_str}, "
                f"nozzle={self.temperature.nozzle_temp}°C, "
                f"bed={self.temperature.bed_temp}°C, "
                f"speed={self.speed.print_speed}mm/min, "
                f"layer_height={self.extrusion.extrusion_height}mm)")
