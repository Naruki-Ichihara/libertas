"""GCode generation from Layer/Model objects using FullControl.

Public API:
    layer_to_gcode  — Single Layer → GCode
    svg_to_gcode    — SVG file → GCode (with path optimization + simplification)
    model_to_gcode  — Multi-layer Model → GCode
    layer_to_json   — Layer → FullControl JSON
    svg_to_json     — SVG → FullControl JSON
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path as PathLib
from libertas.layer import Layer
from libertas.path import Path
import sys

if TYPE_CHECKING:
    from libertas.model import Model
    from libertas.print_params import PrintParams

# Try to import fullcontrol
FC_AVAILABLE = False
fc = None

try:
    import os
    libertas_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fullcontrol_path = os.path.join(libertas_dir, 'libertas', 'fullcontrol')
    if fullcontrol_path not in sys.path:
        sys.path.insert(0, fullcontrol_path)
    import fullcontrol as fc
    FC_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    try:
        import fullcontrol as fc
        FC_AVAILABLE = True
    except (ImportError, ModuleNotFoundError):
        FC_AVAILABLE = False


def _require_fc():
    if not FC_AVAILABLE:
        raise ImportError(
            "FullControl is required for GCode generation. "
            "Try: git submodule update --init --recursive"
        )


def _resolve_params(print_params, **overrides):
    """Extract print parameters from PrintParams or use defaults."""
    defaults = dict(
        printer="generic", nozzle_temp=210, bed_temp=60,
        print_speed=1000, travel_speed=3000,
        extrusion_width=0.4, extrusion_height=0.2,
        retract=True, primer=None, relative_e=True, fan_speed=None,
    )

    if print_params is not None:
        defaults.update(
            printer=print_params.printer.value,
            nozzle_temp=print_params.temperature.nozzle_temp,
            bed_temp=print_params.temperature.bed_temp,
            print_speed=print_params.speed.print_speed,
            travel_speed=print_params.speed.travel_speed,
            extrusion_width=print_params.extrusion.extrusion_width,
            extrusion_height=print_params.extrusion.extrusion_height,
            retract=print_params.retraction.enabled,
            primer=print_params.primer,
            relative_e=print_params.relative_extrusion,
            fan_speed=(int(print_params.cooling.fan_speed)
                       if print_params.cooling.fan_always_on else None),
        )

    # Apply explicit overrides (non-None only)
    for k, v in overrides.items():
        if v is not None and k in defaults:
            defaults[k] = v

    return defaults


def _build_fc_steps(layers_data, params):
    """
    Build FullControl step list from layer data.

    Args:
        layers_data: list of (z_height, paths, offset_x, offset_y)
        params: dict from _resolve_params

    Returns:
        (steps, total_extrusion, total_travel, total_paths)
    """
    steps = []
    steps.append(fc.Printer(print_speed=params["print_speed"]))

    if params["fan_speed"] is not None:
        steps.append(fc.Fan(speed_percent=params["fan_speed"]))

    total_extrusion = 0.0
    total_travel = 0.0
    total_paths = 0
    prev_end = None

    for z, paths, ox, oy in layers_data:
        for path in paths:
            total_paths += 1
            nodes = path.nodes

            for j, (x, y) in enumerate(nodes):
                px, py = x + ox, y + oy

                if j == 0:
                    # Start of path — travel move if not first point
                    if prev_end is not None:
                        travel_dist = ((px - prev_end[0])**2 +
                                       (py - prev_end[1])**2)**0.5
                        total_travel += travel_dist
                        if params["retract"] and travel_dist > 0.5:
                            steps.append(fc.Extruder(on=False))
                        steps.append(fc.Point(x=px, y=py, z=z))
                        if params["retract"] and travel_dist > 0.5:
                            steps.append(fc.Extruder(on=True))
                    else:
                        steps.append(fc.Point(x=px, y=py, z=z))
                else:
                    steps.append(fc.Point(x=px, y=py, z=z))
                    x_prev, y_prev = nodes[j - 1]
                    seg_len = ((x - x_prev)**2 + (y - y_prev)**2)**0.5
                    total_extrusion += seg_len

            if nodes:
                lx, ly = nodes[-1]
                prev_end = (lx + ox, ly + oy)

    return steps, total_extrusion, total_travel, total_paths


def _generate_gcode(steps, params, output_path, visualize=False, **extra_kwargs):
    """Run FullControl transform and save."""
    init_data = {
        'print_speed': params["print_speed"],
        'travel_speed': params["travel_speed"],
        'nozzle_temp': params["nozzle_temp"],
        'bed_temp': params["bed_temp"],
        'extrusion_width': params["extrusion_width"],
        'extrusion_height': params["extrusion_height"],
        'relative_e': params["relative_e"],
    }
    if params["primer"] and isinstance(params["primer"], str):
        init_data['primer'] = params["primer"]
    init_data.update(extra_kwargs)

    controls = fc.GcodeControls(
        printer_name=params["printer"],
        initialization_data=init_data,
    )

    gcode = fc.transform(steps, 'gcode', controls)

    out = PathLib(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(gcode)

    result = {'gcode_path': str(output_path)}

    if visualize:
        viz_path = str(out.with_suffix('.html'))
        try:
            fig = fc.transform(steps, 'plot')
            fig.write_html(viz_path)
            result['visualization_path'] = viz_path
        except Exception as e:
            print(f"Warning: Could not generate visualization: {e}")

    return result


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def layer_to_gcode(
    layer: Layer,
    output_path: str,
    print_params: Optional["PrintParams"] = None,
    z_height: Optional[float] = None,
    initial_z: float = 0.2,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    visualize: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Convert a Layer object to GCode using FullControl.

    Coordinates are used as-is (no Y-flip). Apply coordinate transforms
    before calling this function if needed.

    Args:
        layer: Layer object containing paths.
        output_path: Output GCode file path.
        print_params: PrintParams object (recommended).
        z_height: Z height (mm). If None, uses layer.z_height or initial_z.
        initial_z: Fallback Z height (default: 0.2).
        offset_x: X offset applied to all coordinates (mm).
        offset_y: Y offset applied to all coordinates (mm).
        visualize: Generate HTML visualization (default: False).
        **kwargs: Override individual params (nozzle_temp, print_speed, etc.)
                  and/or pass extra FullControl parameters.

    Returns:
        dict with: num_paths, total_length, total_travel, gcode_path
    """
    _require_fc()

    params = _resolve_params(print_params, **kwargs)

    if z_height is None:
        z_height = layer.z_height if layer.z_height is not None else initial_z

    layers_data = [(z_height, layer.paths, offset_x, offset_y)]
    steps, total_ext, total_trav, n_paths = _build_fc_steps(layers_data, params)

    print(f"Generating GCode: {n_paths} paths, "
          f"extrusion={total_ext:.1f}mm, travel={total_trav:.1f}mm, z={z_height:.3f}mm")

    result = _generate_gcode(steps, params, output_path, visualize=visualize)
    result.update(
        num_paths=n_paths, total_length=total_ext,
        total_travel=total_trav, z_height=z_height,
    )
    print(f"GCode saved to: {output_path}")
    return result


def svg_to_gcode(
    svg_path: str,
    output_gcode_path: str,
    print_params: Optional["PrintParams"] = None,
    segment_length: float = 0.5,
    optimize_paths: bool = True,
    flip_y: bool = True,
    smooth_sigma: float = 3.0,
    decimate_epsilon: float = 0.05,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    z_height: Optional[float] = None,
    visualize: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Convert an SVG file to GCode with path optimization and simplification.

    Pipeline: SVG → parse → optimize order → smooth → decimate → fullcontrol gcode.

    Args:
        svg_path: Input SVG file path.
        output_gcode_path: Output GCode file path.
        print_params: PrintParams object (recommended).
        segment_length: SVG discretization segment length (mm).
        optimize_paths: Apply TSP path ordering (default: True).
        flip_y: Flip Y axis (SVG Y-down → machine Y-up). Default: True.
        smooth_sigma: Gaussian smoothing sigma (0 = no smoothing).
        decimate_epsilon: RDP decimation tolerance mm (0 = no decimation).
        offset_x: X offset for bed placement (mm).
        offset_y: Y offset for bed placement (mm).
        z_height: Z height for this layer (mm).
        visualize: Generate HTML visualization.
        **kwargs: Override individual params and/or pass extra FullControl parameters.

    Returns:
        dict with: num_paths, total_length, total_travel, gcode_path, etc.
    """
    _require_fc()
    from libertas.svg_parser import parse_svg_to_paths
    from libertas.fibrifier_gcode import simplify_path_nodes

    import xml.etree.ElementTree as ET

    print(f"Parsing SVG: {svg_path}")
    paths = parse_svg_to_paths(svg_path, segment_length=segment_length)
    print(f"  Parsed {len(paths)} paths")

    # Y-flip
    if flip_y:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        viewbox = root.attrib.get("viewBox", "0 0 0 0").split()
        svg_height = float(viewbox[3])

        flipped = []
        for p in paths:
            new_nodes = [(x, svg_height - y) for x, y in p.nodes]
            flipped.append(Path(
                path_id=p.path_id, nodes=new_nodes, path_type=p.path_type))
        paths = flipped

    # Create Layer and optimize
    layer = Layer(layer_id=1, paths=paths, name="SVGLayer")
    stats = layer.statistics()
    print(f"  Closed: {stats['closed_paths']}, Open: {stats['open_paths']}, "
          f"Length: {stats['total_length']:.1f}mm")

    if optimize_paths:
        if stats['closed_paths'] > 0:
            layer.optimize_closed_path_order()
        if stats['open_paths'] > 0:
            layer.optimize_open_path_order()
        print(f"  Path order optimized")

    # Smooth and decimate
    if smooth_sigma > 0 or decimate_epsilon > 0:
        total_before = sum(len(p.nodes) for p in layer.paths)
        simplified = []
        for p in layer.paths:
            new_nodes = simplify_path_nodes(
                p.nodes, sigma=smooth_sigma, epsilon=decimate_epsilon)
            simplified.append(Path(
                path_id=p.path_id, nodes=new_nodes, path_type=p.path_type))
        layer.paths = simplified
        total_after = sum(len(p.nodes) for p in layer.paths)
        print(f"  Simplified: {total_before} → {total_after} points "
              f"({100*total_after/total_before:.0f}%)")

    # Generate GCode
    result = layer_to_gcode(
        layer, output_gcode_path,
        print_params=print_params,
        z_height=z_height,
        offset_x=offset_x,
        offset_y=offset_y,
        visualize=visualize,
        **kwargs,
    )

    result['num_paths_parsed'] = len(paths)
    result['segment_length'] = segment_length
    result['optimized'] = optimize_paths
    return result


def model_to_gcode(
    model: "Model",
    output_path: str,
    print_params: Optional["PrintParams"] = None,
    visualize: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Convert a Model (multiple layers) to GCode using FullControl.

    Coordinates are used as-is with model offset applied.

    Args:
        model: Model object containing layers with z_heights.
        output_path: Output GCode file path.
        print_params: PrintParams object (recommended).
        visualize: Generate HTML visualization.
        **kwargs: Override individual params (nozzle_temp, print_speed, etc.)

    Returns:
        dict with: num_layers, num_paths, total_length, total_travel, gcode_path
    """
    _require_fc()

    params = _resolve_params(print_params, **kwargs)

    model.sort_layers_by_height()

    ox = getattr(model, 'offset_x', 0.0)
    oy = getattr(model, 'offset_y', 0.0)
    eh = params["extrusion_height"]

    layers_data = []
    for i, layer in enumerate(model.layers):
        z = layer.z_height if layer.z_height is not None else (i + 1) * eh
        layers_data.append((z, layer.paths, ox, oy))

    steps, total_ext, total_trav, n_paths = _build_fc_steps(layers_data, params)

    print(f"Generating GCode: {len(model.layers)} layers, {n_paths} paths, "
          f"extrusion={total_ext:.1f}mm, travel={total_trav:.1f}mm")

    result = _generate_gcode(steps, params, output_path, visualize=visualize)
    result.update(
        num_layers=len(model.layers), num_paths=n_paths,
        total_length=total_ext, total_travel=total_trav,
        height_range=model.get_height_range(),
    )
    print(f"GCode saved to: {output_path}")
    return result


# ═══════════════════════════════════════════════════════════════
# JSON export (FullControl format)
# ═══════════════════════════════════════════════════════════════

def layer_to_json(
    layer: Layer,
    output_json_path: str,
    z_height: float = 0.2,
    separate_paths: bool = True,
) -> Dict[str, Any]:
    """
    Export a Layer to FullControl JSON format.

    Args:
        layer: Layer object containing paths.
        output_json_path: Output JSON file path.
        z_height: Z height for this layer (mm).
        separate_paths: Insert travel moves between paths.

    Returns:
        dict with export metadata.
    """
    _require_fc()
    import json

    steps = []
    for i, path in enumerate(layer.paths):
        if i > 0 and separate_paths:
            steps.append(fc.Extruder(on=False))

        for j, (x, y) in enumerate(path.nodes):
            steps.append(fc.Point(x=x, y=y, z=z_height))
            if j == 0 and i > 0 and separate_paths:
                steps.append(fc.Extruder(on=True))

    # Export to JSON
    json_data = [step.__dict__ for step in steps if hasattr(step, '__dict__')]

    out = PathLib(output_json_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)

    total_length = sum(p.length for p in layer.paths)
    result = {
        'num_paths': len(layer.paths),
        'total_length': total_length,
        'z_height': z_height,
        'json_path': str(output_json_path),
    }
    print(f"JSON saved to: {output_json_path} ({len(layer.paths)} paths)")
    return result


def svg_to_json(
    svg_path: str,
    output_json_path: str,
    z_height: float = 0.2,
    segment_length: float = 0.5,
    optimize_paths: bool = True,
    separate_paths: bool = True,
) -> Dict[str, Any]:
    """
    Convert SVG directly to FullControl JSON.

    Args:
        svg_path: Input SVG file path.
        output_json_path: Output JSON file path.
        z_height: Z height (mm).
        segment_length: SVG discretization segment length (mm).
        optimize_paths: Apply path ordering optimization.
        separate_paths: Insert travel moves between paths.

    Returns:
        dict with export metadata.
    """
    from libertas.svg_parser import parse_svg_to_paths

    paths = parse_svg_to_paths(svg_path, segment_length=segment_length)
    layer = Layer(layer_id=1, paths=paths, name="SVGLayer")

    if optimize_paths:
        if layer.get_closed_paths():
            layer.optimize_closed_path_order()
        if layer.get_open_paths():
            layer.optimize_open_path_order()

    return layer_to_json(layer, output_json_path, z_height=z_height,
                         separate_paths=separate_paths)
