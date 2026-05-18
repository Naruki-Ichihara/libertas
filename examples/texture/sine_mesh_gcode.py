"""
Sine-wave mesh texture: polymer-only G-code via FullControl.

Generates a 0°/90° interlocking mesh where each line follows a sine wave.
Outputs SVG then converts to G-code.

  0° paths: horizontal lines with sinusoidal Y-offset
 90° paths: vertical   lines with sinusoidal X-offset
"""

import libertas as lb
import numpy as np
import os

# ============================================================================
# Configuration
# ============================================================================

_HERE = os.path.dirname(__file__)
output_dir = os.path.join(_HERE, "outputs", "sine_mesh")
output_svg = os.path.join(output_dir, "sine_mesh.svg")
output_gcode = os.path.join(output_dir, "sine_mesh.gcode")

# --- Geometry ---
WIDTH = 100.0           # mm (X)
HEIGHT = 100.0          # mm (Y)

# --- Mesh pattern ---
SPAN = 2.0              # mm — spacing between parallel lines
WAVELENGTH = 4.0        # mm — sine wave period
AMPLITUDE = 0.6         # mm — sine wave amplitude (peak)
INSET = 0.5             # mm — border inset
POINTS_PER_WAVE = 20    # sample points per wavelength

# --- Stacking ---
LAYER_HEIGHT = 0.2      # mm
NUM_LAYERS = 5          # total layers (alternating 0°/90°)

# --- Print parameters ---
print_params = lb.PrintParams(
    printer=lb.PrinterType.GENERIC,
    material=lb.MaterialType.PLA,
    temperature=lb.TemperatureParams(nozzle_temp=210, bed_temp=60),
    speed=lb.SpeedParams(print_speed=1000, travel_speed=3000),
    extrusion=lb.ExtrusionParams(
        extrusion_width=0.4,
        extrusion_height=LAYER_HEIGHT,
    ),
    retraction=lb.RetractionParams(enabled=True),
    cooling=lb.CoolingParams(fan_speed=100),
)

# --- Bed placement ---
OFFSET_X = 0.0
OFFSET_Y = 0.0


# ============================================================================
# Sine-wave path generation
# ============================================================================

def make_sine_paths(
    width: float,
    height: float,
    span: float,
    wavelength: float,
    amplitude: float,
    inset: float,
    pts_per_wave: int,
) -> tuple:
    """
    Generate 0° and 90° sine-wave mesh paths.

    Returns:
        (paths_0deg, paths_90deg) — each a list of [(x,y), ...] polylines
    """
    # Sampling resolution
    ds = wavelength / pts_per_wave

    # 0° paths: sweep along X, oscillate in Y
    paths_0 = []
    y = inset
    direction = 1
    while y <= height - inset + 1e-9:
        xs = np.arange(inset, width - inset + ds, ds)
        ys = y + amplitude * np.sin(2 * np.pi * xs / wavelength)
        coords = list(zip(xs.tolist(), ys.tolist()))
        if direction == -1:
            coords = coords[::-1]
        paths_0.append(coords)
        y += span
        direction *= -1

    # 90° paths: sweep along Y, oscillate in X
    paths_90 = []
    x = inset
    direction = 1
    while x <= width - inset + 1e-9:
        ys = np.arange(inset, height - inset + ds, ds)
        xs = x + amplitude * np.sin(2 * np.pi * ys / wavelength)
        coords = list(zip(xs.tolist(), ys.tolist()))
        if direction == -1:
            coords = coords[::-1]
        paths_90.append(coords)
        x += span
        direction *= -1

    return paths_0, paths_90


def make_contour(width, height, inset):
    """Rectangular contour as [(x,y), ...]."""
    x0, y0 = inset, inset
    x1, y1 = width - inset, height - inset
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


# ============================================================================
# SVG generation
# ============================================================================

def generate_svg(
    output_path: str,
    width: float,
    height: float,
    paths_0: list,
    paths_90: list,
    contour: list,
):
    """Write an SVG with contour + all sine-wave mesh lines."""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}mm" height="{height}mm" '
        f'viewBox="0 0 {width} {height}">'
    )

    # Contour group
    lines.append('  <g id="contour" fill="none" stroke="#000" stroke-width="0.05">')
    pts = " ".join(f"{x:.4f},{y:.4f}" for x, y in contour)
    lines.append(f'    <polyline points="{pts}"/>')
    lines.append('  </g>')

    # Stripe groups (0° and 90° share the same group for G-code parser)
    lines.append('  <g id="stripes" fill="none" stroke="#000" stroke-width="0.05">')
    for path in paths_0 + paths_90:
        pts = " ".join(f"{x:.4f},{y:.4f}" for x, y in path)
        lines.append(f'    <polyline points="{pts}"/>')
    lines.append('  </g>')

    lines.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write("\n".join(lines))

    n_total = len(paths_0) + len(paths_90)
    print(f"SVG saved: {output_path}  ({n_total} paths: {len(paths_0)} x 0° + {len(paths_90)} x 90°)")


# ============================================================================
# G-code generation (FullControl via libertas)
# ============================================================================

def generate_gcode(
    svg_path: str,
    gcode_path: str,
    print_params: lb.PrintParams,
    layer_height: float,
    num_layers: int,
    offset_x: float,
    offset_y: float,
):
    """Stack SVG paths into multi-layer G-code using FullControl."""
    from libertas.svg_parser import parse_svg_to_paths
    from libertas.layer import Layer
    from libertas.model import Model

    paths = parse_svg_to_paths(svg_path, segment_length=0.5)
    print(f"Parsed {len(paths)} paths from SVG")

    model = Model(model_id=1, name="sine_mesh")
    model.offset_x = offset_x
    model.offset_y = offset_y

    for i in range(num_layers):
        z = layer_height * (i + 1)
        layer = Layer(layer_id=i + 1, paths=paths, name=f"layer_{i+1}", z_height=z)
        stats = layer.statistics()
        if stats['open_paths'] > 0:
            layer.optimize_open_path_order()
        if stats['closed_paths'] > 0:
            layer.optimize_closed_path_order()
        model.add_layer(layer)

    print(f"Model: {num_layers} layers, z = {layer_height:.2f} .. {num_layers * layer_height:.2f} mm")

    result = lb.model_to_gcode(
        model=model,
        output_path=gcode_path,
        print_params=print_params,
    )
    return result


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print(f"SINE MESH TEXTURE  {WIDTH:.0f}x{HEIGHT:.0f}mm")
    print(f"  span={SPAN}mm  wavelength={WAVELENGTH}mm  amplitude={AMPLITUDE}mm")
    print(f"  layers={NUM_LAYERS}  layer_height={LAYER_HEIGHT}mm")
    print("=" * 70)

    # 1. Generate paths
    paths_0, paths_90 = make_sine_paths(
        WIDTH, HEIGHT, SPAN, WAVELENGTH, AMPLITUDE, INSET, POINTS_PER_WAVE,
    )
    contour = make_contour(WIDTH, HEIGHT, INSET)

    # 2. Write SVG
    generate_svg(output_svg, WIDTH, HEIGHT, paths_0, paths_90, contour)

    # 3. Generate G-code
    result = generate_gcode(
        output_svg, output_gcode, print_params,
        LAYER_HEIGHT, NUM_LAYERS, OFFSET_X, OFFSET_Y,
    )

    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"  SVG:    {output_svg}")
    print(f"  GCode:  {result['gcode_path']}")
    print(f"  Layers: {result['num_layers']}")
    print(f"  Paths:  {result['num_paths']}")
    print("=" * 70)
