"""GCode generation from Layer objects using FullControl."""

from typing import Optional, Dict, Any, TYPE_CHECKING, List
from pathlib import Path as PathLib
from libertas.layer import Layer
from libertas.path import Path
import sys
import re

if TYPE_CHECKING:
    from libertas.model import Model
    from libertas.print_params import PrintParams

# Try to import fullcontrol
FC_AVAILABLE = False
fc = None

try:
    # First try the submodule path
    import os
    libertas_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fullcontrol_path = os.path.join(libertas_dir, 'libertas', 'fullcontrol')
    if fullcontrol_path not in sys.path:
        sys.path.insert(0, fullcontrol_path)

    import fullcontrol as fc
    FC_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    try:
        # Try direct import if fullcontrol is installed separately
        import fullcontrol as fc
        FC_AVAILABLE = True
    except (ImportError, ModuleNotFoundError):
        FC_AVAILABLE = False


def _add_type_comments_to_gcode(
    gcode: str,
    paths: List[Path],
    layer_idx: int = 0
) -> str:
    """
    Add Cura-compatible ;TYPE: comments to GCode for proper visualization.

    Cura uses ;TYPE: comments to identify different path types and color them
    accordingly in the preview. This function inserts appropriate TYPE comments
    based on the path_type attribute.

    Args:
        gcode: Raw GCode string
        paths: List of Path objects in the order they appear in GCode
        layer_idx: Layer index (for layer comment)

    Returns:
        GCode string with ;TYPE: comments inserted
    """
    lines = gcode.split('\n')
    output_lines = []

    # Track current path index and whether we've added its TYPE comment
    path_idx = 0
    type_added_for_current_path = False
    in_header = True
    current_type = None

    for line in lines:
        # Check if we're past the header (after temperature commands)
        if in_header and (line.startswith('G0') or line.startswith('G1')):
            in_header = False
            # Add layer comment
            output_lines.append(f';LAYER:{layer_idx}')

        # Check for start of new extrusion move (not travel)
        if line.startswith('G1') and ' E' in line and path_idx < len(paths):
            path = paths[path_idx]

            # Map path_type to Cura TYPE
            if path.path_type == 'contour':
                # Contours are outer walls
                gcode_type = 'WALL-OUTER'
            elif path.path_type == 'stripe':
                # Stripes are fill/infill
                gcode_type = 'FILL'
            else:
                gcode_type = 'FILL'  # Default

            # Only add TYPE comment if it's different from current type
            if gcode_type != current_type:
                output_lines.append(f';TYPE:{gcode_type}')
                current_type = gcode_type
                type_added_for_current_path = True

        # Check for travel move or extruder off (indicates end of path)
        if (line.startswith('G0') or
            'Extruder(on=False)' in line or
            (line.startswith('G1') and ' E' not in line and ' X' in line)):
            # Move to next path
            if type_added_for_current_path:
                path_idx += 1
                type_added_for_current_path = False

        output_lines.append(line)

    return '\n'.join(output_lines)


def _add_type_comments_to_model_gcode(
    gcode: str,
    model: "Model"
) -> str:
    """
    Add Cura-compatible ;TYPE: and ;LAYER: comments to multi-layer GCode.

    Args:
        gcode: Raw GCode string
        model: Model object containing all layers

    Returns:
        GCode string with ;TYPE: and ;LAYER: comments inserted
    """
    lines = gcode.split('\n')
    output_lines = []

    # Flatten all paths from all layers for sequential tracking
    all_paths = []
    layer_start_path_idx = []
    path_count = 0

    for layer_idx, layer in enumerate(model.layers):
        layer_start_path_idx.append(path_count)
        for path in layer.paths:
            all_paths.append((layer_idx, path))
            path_count += 1

    # Track state
    path_idx = 0
    current_layer = -1
    current_type = None
    in_header = True
    in_extrusion = False

    for line in lines:
        # Check if we're past the header
        if in_header and (line.startswith('G0') or line.startswith('G1')):
            in_header = False

        # Detect Z-axis change (layer change)
        if line.startswith('G0') or line.startswith('G1'):
            z_match = re.search(r'Z([\d.]+)', line)
            if z_match and path_idx < len(all_paths):
                z_value = float(z_match.group(1))
                layer_idx, path = all_paths[path_idx]

                # Check if we've moved to a new layer
                if layer_idx != current_layer:
                    current_layer = layer_idx
                    output_lines.append(f';LAYER:{layer_idx}')
                    current_type = None  # Reset type for new layer

        # Check for start of extrusion
        if line.startswith('G1') and ' E' in line and path_idx < len(all_paths):
            layer_idx, path = all_paths[path_idx]

            # Map path_type to Cura TYPE
            if path.path_type == 'contour':
                gcode_type = 'WALL-OUTER'
            elif path.path_type == 'stripe':
                gcode_type = 'FILL'
            else:
                gcode_type = 'FILL'

            # Add TYPE comment if changed
            if gcode_type != current_type:
                output_lines.append(f';TYPE:{gcode_type}')
                current_type = gcode_type

            if not in_extrusion:
                in_extrusion = True

        # Check for end of path (travel move or extruder off)
        if in_extrusion and (line.startswith('G0') or
                             (line.startswith('G1') and ' E' not in line and (' X' in line or ' Y' in line))):
            # Move to next path
            path_idx += 1
            in_extrusion = False

        output_lines.append(line)

    return '\n'.join(output_lines)


def layer_to_gcode(
    layer: Layer,
    output_path: str,
    print_params: Optional["PrintParams"] = None,
    # Legacy individual parameters (for backward compatibility)
    printer: Optional[str] = None,
    nozzle_temp: Optional[float] = None,
    bed_temp: Optional[float] = None,
    print_speed: Optional[float] = None,
    travel_speed: Optional[float] = None,
    extrusion_width: Optional[float] = None,
    extrusion_height: Optional[float] = None,
    z_height: Optional[float] = None,
    initial_z: float = 0.2,
    fan_speed: Optional[int] = None,
    retract: Optional[bool] = None,
    primer: Optional[str] = None,
    relative_e: Optional[bool] = None,
    visualize: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Convert a Layer object to GCode using FullControl.

    This function takes an optimized Layer containing Path objects and generates
    GCode for 3D printing. It respects the path order and uses travel moves between
    non-connected paths.

    Args:
        layer: Layer object containing optimized paths
        output_path: Output GCode file path
        print_params: PrintParams object with all print settings (recommended)
        printer: Printer profile name (default: "generic") [deprecated - use print_params]
        nozzle_temp: Nozzle temperature in Celsius [deprecated - use print_params]
        bed_temp: Bed temperature in Celsius [deprecated - use print_params]
        print_speed: Printing speed in mm/min [deprecated - use print_params]
        travel_speed: Travel speed in mm/min [deprecated - use print_params]
        extrusion_width: Extrusion width in mm [deprecated - use print_params]
        extrusion_height: Layer height in mm [deprecated - use print_params]
        z_height: Z height for this layer in mm. If None, uses layer.z_height or initial_z
        initial_z: Initial Z height if z_height not specified (default: 0.2)
        fan_speed: Fan speed percentage (0-100) [deprecated - use print_params]
        retract: Enable retraction during travel moves [deprecated - use print_params]
        primer: Primer type [deprecated - use print_params]
        relative_e: Use relative extrusion [deprecated - use print_params]
        visualize: Generate visualization plot (default: False)
        **kwargs: Additional FullControl parameters

    Returns:
        Dictionary with metadata:
            - num_paths: Number of paths processed
            - total_length: Total extrusion length (mm)
            - total_travel: Total travel distance (mm)
            - gcode_path: Path to generated GCode file
            - visualization_path: Path to visualization (if visualize=True)

    Example:
        >>> import libertas as lb
        >>>
        >>> # Modern approach (recommended)
        >>> params = lb.PrintParams.from_preset(
        ...     printer=lb.PrinterType.PRUSA_I3,
        ...     material=lb.MaterialType.PLA
        ... )
        >>> result = lb.layer_to_gcode(layer, "output.gcode", params)
        >>>
        >>> # Legacy approach (still supported)
        >>> result = lb.layer_to_gcode(
        ...     layer, "output.gcode",
        ...     printer="prusa_i3",
        ...     nozzle_temp=210
        ... )

    Note:
        Requires FullControl to be installed. The layer should be optimized
        before calling this function for best print quality.
    """
    if not FC_AVAILABLE:
        raise ImportError(
            "FullControl is required for GCode generation. "
            "The fullcontrol submodule may not be initialized. "
            "Try: git submodule update --init --recursive"
        )

    # Extract parameters from PrintParams or use individual parameters
    if print_params is not None:
        # Use PrintParams (preferred method)
        printer = printer or print_params.printer.value
        nozzle_temp = nozzle_temp or print_params.temperature.nozzle_temp
        bed_temp = bed_temp or print_params.temperature.bed_temp
        print_speed = print_speed or print_params.speed.print_speed
        travel_speed = travel_speed or print_params.speed.travel_speed
        extrusion_width = extrusion_width or print_params.extrusion.extrusion_width
        extrusion_height = extrusion_height or print_params.extrusion.extrusion_height
        fan_speed = fan_speed or (int(print_params.cooling.fan_speed) if print_params.cooling.fan_always_on else None)
        retract = retract if retract is not None else print_params.retraction.enabled
        primer = primer or print_params.primer
        relative_e = relative_e if relative_e is not None else print_params.relative_extrusion
    else:
        # Use individual parameters with defaults (backward compatibility)
        printer = printer or "generic"
        nozzle_temp = nozzle_temp or 210
        bed_temp = bed_temp or 60
        print_speed = print_speed or 1000
        travel_speed = travel_speed or 3000
        extrusion_width = extrusion_width or 0.4
        extrusion_height = extrusion_height or 0.2
        retract = retract if retract is not None else True
        relative_e = relative_e if relative_e is not None else True

    # Determine Z height
    if z_height is None:
        if layer.z_height is not None:
            z_height = layer.z_height
        else:
            z_height = initial_z

    # Get layer bounds for Y-axis flip (SVG coords → GCode coords)
    # SVG: origin top-left, Y down
    # GCode: origin bottom-left, Y up
    layer_bounds = layer.get_bounds()
    y_min, y_max = layer_bounds[1], layer_bounds[3]
    y_flip_base = y_min + y_max  # Sum for flip calculation

    # Create FullControl steps
    steps = []

    # Add printer settings
    steps.append(fc.Printer(print_speed=print_speed))

    # Add fan control if specified
    if fan_speed is not None:
        steps.append(fc.Fan(speed_percent=fan_speed))

    # Start position - move to first path's start point
    if len(layer.paths) > 0:
        first_path = layer.paths[0]
        x_start, y_start = first_path.start_point

        # Flip Y coordinate
        y_start_flipped = y_flip_base - y_start

        # Add initial point at Z height
        steps.append(fc.Point(x=x_start, y=y_start_flipped, z=z_height))

    # Process each path in the layer
    total_extrusion = 0.0
    total_travel = 0.0

    for i, path in enumerate(layer.paths):
        # For each path, add points
        for j, (x, y) in enumerate(path.nodes):
            # Apply Y-axis flip for all coordinates
            y_flipped = y_flip_base - y

            if j == 0 and i > 0:
                # This is the start of a new path - check if we need travel move
                prev_path = layer.paths[i - 1]
                prev_x, prev_y = prev_path.end_point
                curr_x, curr_y = path.start_point

                # Calculate travel distance (using original coordinates)
                travel_dist = ((curr_x - prev_x)**2 + (curr_y - prev_y)**2)**0.5
                total_travel += travel_dist

                # Add travel move (retract if enabled)
                if retract and travel_dist > 0.5:  # Retract for travels > 0.5mm
                    # Turn off extrusion for travel
                    steps.append(fc.Extruder(on=False))

                # Travel to new start point (with flipped Y)
                steps.append(fc.Point(x=x, y=y_flipped, z=z_height))

                if retract and travel_dist > 0.5:
                    # Turn on extrusion again
                    steps.append(fc.Extruder(on=True))
            else:
                # Regular extrusion point (with flipped Y)
                steps.append(fc.Point(x=x, y=y_flipped, z=z_height))

                # Calculate extrusion length for this segment (using original coordinates)
                if j > 0:
                    x_prev, y_prev = path.nodes[j - 1]
                    segment_length = ((x - x_prev)**2 + (y - y_prev)**2)**0.5
                    total_extrusion += segment_length

    # Generate GCode
    print(f"Generating GCode for {len(layer.paths)} paths...")
    print(f"  Total extrusion length: {total_extrusion:.2f} mm")
    print(f"  Total travel distance: {total_travel:.2f} mm")
    print(f"  Z height: {z_height:.3f} mm")

    # Create initialization data, excluding None values
    init_data = {
        'print_speed': print_speed,
        'travel_speed': travel_speed,
        'nozzle_temp': nozzle_temp,
        'bed_temp': bed_temp,
        'extrusion_width': extrusion_width,
        'extrusion_height': extrusion_height,
        'relative_e': relative_e,
    }

    # Add primer setting (only if enabled - False or None means disabled)
    if primer and isinstance(primer, str):
        init_data['primer'] = primer

    # Add any additional kwargs
    init_data.update(kwargs)

    # Create GcodeControls with settings
    controls = fc.GcodeControls(
        printer_name=printer,
        initialization_data=init_data
    )

    # Convert to GCode
    gcode = fc.transform(steps, 'gcode', controls)

    # Add Cura-compatible TYPE comments
    gcode = _add_type_comments_to_gcode(gcode, layer.paths, layer_idx=0)

    # Save GCode
    output_path_obj = PathLib(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(gcode)

    print(f"GCode saved to: {output_path}")

    # Prepare result
    result = {
        'num_paths': len(layer.paths),
        'total_length': total_extrusion,
        'total_travel': total_travel,
        'z_height': z_height,
        'gcode_path': str(output_path)
    }

    # Generate visualization if requested
    if visualize:
        viz_path = str(output_path_obj.with_suffix('.html'))
        print(f"Generating visualization: {viz_path}")

        try:
            fig = fc.transform(steps, 'plot')
            fig.write_html(viz_path)
            result['visualization_path'] = viz_path
            print(f"Visualization saved to: {viz_path}")
        except Exception as e:
            print(f"Warning: Could not generate visualization: {e}")

    return result


def svg_to_gcode(
    svg_path: str,
    output_gcode_path: str,
    segment_length: float = 0.5,
    optimize_paths: bool = True,
    **gcode_kwargs
) -> Dict[str, Any]:
    """
    Convert an SVG file directly to GCode.

    This is a convenience function that combines SVG parsing, Layer creation,
    path optimization, and GCode generation into a single call.

    Args:
        svg_path: Input SVG file path
        output_gcode_path: Output GCode file path
        segment_length: Segment length for SVG discretization in mm (default: 0.5)
        optimize_paths: Apply path optimization (default: True)
        **gcode_kwargs: Additional arguments passed to layer_to_gcode()

    Returns:
        Dictionary with combined metadata from parsing and GCode generation

    Example:
        >>> import libertas as lb
        >>>
        >>> result = lb.svg_to_gcode(
        ...     svg_path="paths.svg",
        ...     output_gcode_path="output.gcode",
        ...     segment_length=0.5,
        ...     printer="prusa_i3",
        ...     nozzle_temp=210,
        ...     visualize=True
        ... )
    """
    from libertas.svg_parser import parse_svg_to_paths

    print("=" * 70)
    print("SVG TO GCODE CONVERSION")
    print("=" * 70)

    # Parse SVG
    print(f"\nParsing SVG: {svg_path}")
    paths = parse_svg_to_paths(svg_path, segment_length=segment_length)
    print(f"  Parsed {len(paths)} paths")

    # Create Layer
    layer = Layer(layer_id=1, paths=paths, name="SVGLayer")
    stats = layer.statistics()
    print(f"  Closed paths: {stats['closed_paths']}")
    print(f"  Open paths: {stats['open_paths']}")
    print(f"  Total length: {stats['total_length']:.2f} mm")

    # Optimize paths if requested
    if optimize_paths:
        print("\n" + "-" * 70)
        print("Optimizing path order...")
        print("-" * 70)

        # Optimize closed paths first
        if stats['closed_paths'] > 0:
            closed_travel = layer.optimize_closed_path_order()
            print(f"  Closed path travel: {closed_travel:.2f} mm")

        # Then optimize open paths
        if stats['open_paths'] > 0:
            open_travel = layer.optimize_open_path_order()
            print(f"  Open path travel: {open_travel:.2f} mm")

    # Generate GCode
    print("\n" + "-" * 70)
    print("Generating GCode...")
    print("-" * 70)
    result = layer_to_gcode(layer, output_gcode_path, **gcode_kwargs)

    # Add parsing metadata
    result['num_paths_parsed'] = len(paths)
    result['segment_length'] = segment_length
    result['optimized'] = optimize_paths

    print("\n" + "=" * 70)
    print("CONVERSION COMPLETE")
    print("=" * 70)

    return result


def model_to_gcode(
    model: "Model",
    output_path: str,
    print_params: Optional["PrintParams"] = None,
    # Legacy individual parameters (for backward compatibility)
    printer: Optional[str] = None,
    nozzle_temp: Optional[float] = None,
    bed_temp: Optional[float] = None,
    print_speed: Optional[float] = None,
    travel_speed: Optional[float] = None,
    extrusion_width: Optional[float] = None,
    extrusion_height: Optional[float] = None,
    fan_speed: Optional[int] = None,
    retract: Optional[bool] = None,
    primer: Optional[str] = None,
    relative_e: Optional[bool] = None,
    visualize: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Convert a Model (multiple layers) to GCode using FullControl.

    This function takes a Model containing multiple Layer objects stacked in Z
    and generates GCode for multi-layer 3D printing. Each layer is printed at
    its specified z_height.

    Args:
        model: Model object containing layers
        output_path: Output GCode file path
        print_params: PrintParams object with all print settings (recommended)
        printer: Printer profile name [deprecated - use print_params]
        nozzle_temp: Nozzle temperature in Celsius [deprecated - use print_params]
        bed_temp: Bed temperature in Celsius [deprecated - use print_params]
        print_speed: Printing speed in mm/min [deprecated - use print_params]
        travel_speed: Travel speed in mm/min [deprecated - use print_params]
        extrusion_width: Extrusion width in mm [deprecated - use print_params]
        extrusion_height: Layer height in mm [deprecated - use print_params]
        fan_speed: Fan speed percentage (0-100) [deprecated - use print_params]
        retract: Enable retraction during travel moves [deprecated - use print_params]
        primer: Primer type [deprecated - use print_params]
        relative_e: Use relative extrusion [deprecated - use print_params]
        visualize: Generate visualization plot (default: False)
        **kwargs: Additional FullControl parameters

    Returns:
        Dictionary with metadata:
            - num_layers: Number of layers processed
            - num_paths: Total number of paths across all layers
            - total_length: Total extrusion length (mm)
            - total_travel: Total travel distance (mm)
            - height_range: (min_z, max_z) tuple
            - gcode_path: Path to generated GCode file

    Example:
        >>> import libertas as lb
        >>>
        >>> # Modern approach (recommended)
        >>> params = lb.PrintParams.from_preset(
        ...     printer=lb.PrinterType.PRUSA_I3,
        ...     material=lb.MaterialType.PLA
        ... )
        >>> result = lb.model_to_gcode(model, "output.gcode", params)
        >>>
        >>> # Legacy approach (still supported)
        >>> result = lb.model_to_gcode(
        ...     model, "output.gcode",
        ...     printer="prusa_i3",
        ...     nozzle_temp=210
        ... )
    """
    if not FC_AVAILABLE:
        raise ImportError(
            "FullControl is required for GCode generation. "
            "The fullcontrol submodule may not be initialized."
        )

    # Extract parameters from PrintParams or use individual parameters
    if print_params is not None:
        # Use PrintParams (preferred method)
        printer = printer or print_params.printer.value
        nozzle_temp = nozzle_temp or print_params.temperature.nozzle_temp
        bed_temp = bed_temp or print_params.temperature.bed_temp
        print_speed = print_speed or print_params.speed.print_speed
        travel_speed = travel_speed or print_params.speed.travel_speed
        extrusion_width = extrusion_width or print_params.extrusion.extrusion_width
        extrusion_height = extrusion_height or print_params.extrusion.extrusion_height
        fan_speed = fan_speed or (int(print_params.cooling.fan_speed) if print_params.cooling.fan_always_on else None)
        retract = retract if retract is not None else print_params.retraction.enabled
        primer = primer or print_params.primer
        relative_e = relative_e if relative_e is not None else print_params.relative_extrusion
    else:
        # Use individual parameters with defaults (backward compatibility)
        printer = printer or "generic"
        nozzle_temp = nozzle_temp or 210
        bed_temp = bed_temp or 60
        print_speed = print_speed or 1000
        travel_speed = travel_speed or 3000
        extrusion_width = extrusion_width or 0.4
        extrusion_height = extrusion_height or 0.2
        retract = retract if retract is not None else True
        relative_e = relative_e if relative_e is not None else True

    # Sort layers by height
    model.sort_layers_by_height()

    # Create FullControl steps
    steps = []

    # Add printer settings
    steps.append(fc.Printer(print_speed=print_speed))

    # Add fan control if specified
    if fan_speed is not None:
        steps.append(fc.Fan(speed_percent=fan_speed))

    # Get model offset
    offset_x = getattr(model, 'offset_x', 0.0)
    offset_y = getattr(model, 'offset_y', 0.0)

    # Get model bounds for Y-axis flip (SVG coords → GCode coords)
    # SVG: origin top-left, Y down
    # GCode: origin bottom-left, Y up
    model_bounds = model.get_bounds()
    y_min, y_max = model_bounds[1], model_bounds[4]
    y_flip_base = y_min + y_max  # Sum for flip calculation

    # Start position
    if len(model.layers) > 0 and len(model.layers[0].paths) > 0:
        first_layer = model.layers[0]
        first_path = first_layer.paths[0]
        x_start, y_start = first_path.start_point
        z_start = first_layer.z_height if first_layer.z_height is not None else extrusion_height

        # Flip Y coordinate and apply offset
        y_start_flipped = y_flip_base - y_start
        steps.append(fc.Point(x=x_start + offset_x, y=y_start_flipped + offset_y, z=z_start))

    # Process each layer
    total_extrusion = 0.0
    total_travel = 0.0
    total_paths = 0

    print(f"Generating GCode for {len(model.layers)} layers...")

    for layer_idx, layer in enumerate(model.layers):
        z_height = layer.z_height if layer.z_height is not None else (layer_idx + 1) * extrusion_height

        print(f"  Layer {layer_idx + 1}/{len(model.layers)}: z={z_height:.3f}mm, paths={len(layer.paths)}")

        # Process each path in the layer
        for path_idx, path in enumerate(layer.paths):
            total_paths += 1

            for node_idx, (x, y) in enumerate(path.nodes):
                # Apply Y-axis flip and offset to coordinates
                y_flipped = y_flip_base - y
                x_offset = x + offset_x
                y_offset = y_flipped + offset_y

                if node_idx == 0 and (layer_idx > 0 or path_idx > 0):
                    # Travel move needed
                    if path_idx > 0:
                        prev_path = layer.paths[path_idx - 1]
                    else:
                        prev_layer = model.layers[layer_idx - 1]
                        prev_path = prev_layer.paths[-1]

                    prev_x, prev_y = prev_path.end_point
                    curr_x, curr_y = path.start_point

                    # Calculate travel distance (using original coordinates)
                    travel_dist = ((curr_x - prev_x)**2 + (curr_y - prev_y)**2)**0.5
                    total_travel += travel_dist

                    if retract and travel_dist > 0.5:
                        steps.append(fc.Extruder(on=False))

                    steps.append(fc.Point(x=x_offset, y=y_offset, z=z_height))

                    if retract and travel_dist > 0.5:
                        steps.append(fc.Extruder(on=True))
                else:
                    steps.append(fc.Point(x=x_offset, y=y_offset, z=z_height))

                    if node_idx > 0:
                        x_prev, y_prev = path.nodes[node_idx - 1]
                        # Calculate extrusion length (using original coordinates)
                        segment_length = ((x - x_prev)**2 + (y - y_prev)**2)**0.5
                        total_extrusion += segment_length

    print(f"\nModel statistics:")
    print(f"  Total layers: {len(model.layers)}")
    print(f"  Total paths: {total_paths}")
    print(f"  Total extrusion: {total_extrusion:.2f} mm")
    print(f"  Total travel: {total_travel:.2f} mm")
    print(f"  Height range: {model.get_height_range()[0]:.3f} - {model.get_height_range()[1]:.3f} mm")
    if offset_x != 0.0 or offset_y != 0.0:
        print(f"  Offset applied: X={offset_x:.2f}mm, Y={offset_y:.2f}mm")

    # Create initialization data
    init_data = {
        'print_speed': print_speed,
        'travel_speed': travel_speed,
        'nozzle_temp': nozzle_temp,
        'bed_temp': bed_temp,
        'extrusion_width': extrusion_width,
        'extrusion_height': extrusion_height,
        'relative_e': relative_e,
    }

    # Add primer setting (only if enabled - False or None means disabled)
    if primer and isinstance(primer, str):
        init_data['primer'] = primer

    init_data.update(kwargs)

    # Create GcodeControls
    controls = fc.GcodeControls(
        printer_name=printer,
        initialization_data=init_data
    )

    # Convert to GCode
    gcode = fc.transform(steps, 'gcode', controls)

    # Add Cura-compatible TYPE and LAYER comments
    gcode = _add_type_comments_to_model_gcode(gcode, model)

    # Save GCode
    output_path_obj = PathLib(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(gcode)

    print(f"\nGCode saved to: {output_path}")

    # Prepare result
    result = {
        'num_layers': len(model.layers),
        'num_paths': total_paths,
        'total_length': total_extrusion,
        'total_travel': total_travel,
        'height_range': model.get_height_range(),
        'gcode_path': str(output_path)
    }

    # Generate visualization if requested
    if visualize:
        viz_path = str(output_path_obj.with_suffix('.html'))
        print(f"Generating visualization: {viz_path}")

        try:
            fig = fc.transform(steps, 'plot')
            fig.write_html(viz_path)
            result['visualization_path'] = viz_path
            print(f"Visualization saved to: {viz_path}")
        except Exception as e:
            print(f"Warning: Could not generate visualization: {e}")

    return result
