"""
Woven texture: alternating 0°/90° sine-wave layers via FullControl.

Each layer prints only one direction (0° or 90°), alternating per layer.
Phase shift between adjacent lines creates an over-under weave illusion.

Layer 0: ——  0° (horizontal waves)
Layer 1: ||  90° (vertical waves)
Layer 2: ——  0° (horizontal waves, phase shifted)
Layer 3: ||  90° (vertical waves, phase shifted)
...
"""

import libertas as lb
from libertas.svg_parser import parse_svg_to_paths
from libertas.layer import Layer
from libertas.model import Model
import numpy as np
import os

# ============================================================================
# Configuration
# ============================================================================

_HERE = os.path.dirname(__file__)
output_dir = os.path.join(_HERE, "outputs", "weave")
output_gcode = os.path.join(output_dir, "weave.gcode")

# --- Geometry ---
WIDTH = 100.0           # mm (X)
HEIGHT = 100.0          # mm (Y)

# --- Weave pattern ---
SPAN = 2.0              # mm — spacing between parallel lines
WAVELENGTH = 4.0        # mm — sine wave period
AMPLITUDE = 0.6         # mm — sine wave amplitude (peak)
INSET = 0.5             # mm — border inset
POINTS_PER_WAVE = 20    # sample points per wavelength

# --- Stacking ---
LAYER_HEIGHT = 0.2      # mm
NUM_REPEATS = 3         # number of 0°+90° pairs → total layers = NUM_REPEATS * 2
PHASE_SHIFT = 0.0       # radians — phase offset between repeats (pi = half-wave interlock, 0 = aligned)

# --- Print parameters ---
print_params = lb.PrintParams(
    printer=lb.PrinterType.PRUSA_MINI,
    material=lb.MaterialType.NYLON,
    temperature=lb.TemperatureParams(nozzle_temp=210, bed_temp=60),
    speed=lb.SpeedParams(print_speed=1000, travel_speed=3000),
    extrusion=lb.ExtrusionParams(
        extrusion_width=0.4,
        extrusion_height=LAYER_HEIGHT,
    ),
    retraction=lb.RetractionParams(enabled=True),
    cooling=lb.CoolingParams(fan_speed=100),
)

OFFSET_X = 0.0
OFFSET_Y = 0.0


# ============================================================================
# Path generation
# ============================================================================

def make_sine_paths_single_dir(
    width, height, span, wavelength, amplitude, inset, pts_per_wave,
    direction: int = 0,
    phase: float = 0.0,
):
    """
    Generate sine-wave paths in a single direction.

    Args:
        direction: 0 = horizontal (along X), 90 = vertical (along Y)
        phase: phase offset in radians (e.g. pi for half-wave shift)

    Returns:
        list of [(x, y), ...] polylines
    """
    ds = wavelength / pts_per_wave
    paths = []

    if direction == 0:
        y = inset
        zigzag = 1
        while y <= height - inset + 1e-9:
            xs = np.arange(inset, width - inset + ds, ds)
            ys = y + amplitude * np.sin(2 * np.pi * xs / wavelength + phase)
            coords = list(zip(xs.tolist(), ys.tolist()))
            if zigzag == -1:
                coords = coords[::-1]
            paths.append(coords)
            y += span
            zigzag *= -1
    else:
        x = inset
        zigzag = 1
        while x <= width - inset + 1e-9:
            ys = np.arange(inset, height - inset + ds, ds)
            xs = x + amplitude * np.sin(2 * np.pi * ys / wavelength + phase)
            coords = list(zip(xs.tolist(), ys.tolist()))
            if zigzag == -1:
                coords = coords[::-1]
            paths.append(coords)
            x += span
            zigzag *= -1

    return paths


def write_svg(output_path, width, height, paths, inset):
    """Write paths to SVG."""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}mm" height="{height}mm" '
        f'viewBox="0 0 {width} {height}">'
    )
    # Contour
    x0, y0, x1, y1 = inset, inset, width - inset, height - inset
    lines.append('  <g id="contour" fill="none" stroke="#000" stroke-width="0.05">')
    lines.append(f'    <polyline points="{x0},{y0} {x1},{y0} {x1},{y1} {x0},{y1} {x0},{y0}"/>')
    lines.append('  </g>')
    # Stripes
    lines.append('  <g id="stripes" fill="none" stroke="#000" stroke-width="0.05">')
    for path in paths:
        pts = " ".join(f"{x:.4f},{y:.4f}" for x, y in path)
        lines.append(f'    <polyline points="{pts}"/>')
    lines.append('  </g>')
    lines.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write("\n".join(lines))
    return output_path


# ============================================================================
# Main
# ============================================================================

def interleave_weave_paths(paths_0, paths_90):
    """
    Interleave horizontal and vertical paths:
      H0, V0, H1, V1, H2, V2, ...

    This makes the nozzle alternate between laying a horizontal line
    and a vertical line, so each direction physically goes over/under
    the other — producing a true woven pattern in a single layer.
    """
    woven = []
    n = max(len(paths_0), len(paths_90))
    for i in range(n):
        if i < len(paths_0):
            woven.append(paths_0[i])
        if i < len(paths_90):
            woven.append(paths_90[i])
    return woven


if __name__ == "__main__":
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70)
    print(f"WEAVE TEXTURE  {WIDTH:.0f}x{HEIGHT:.0f}mm  —  {NUM_REPEATS} layers")
    print(f"  span={SPAN}mm  wavelength={WAVELENGTH}mm  amplitude={AMPLITUDE}mm")
    print("=" * 70)

    # 1. Generate 0° and 90° paths
    paths_0 = make_sine_paths_single_dir(
        WIDTH, HEIGHT, SPAN, WAVELENGTH, AMPLITUDE, INSET,
        POINTS_PER_WAVE, direction=0, phase=0.0,
    )
    paths_90 = make_sine_paths_single_dir(
        WIDTH, HEIGHT, SPAN, WAVELENGTH, AMPLITUDE, INSET,
        POINTS_PER_WAVE, direction=90, phase=0.0,
    )
    print(f"  0° paths: {len(paths_0)},  90° paths: {len(paths_90)}")

    # 2. Interleave into woven order: H0, V0, H1, V1, ...
    woven = interleave_weave_paths(paths_0, paths_90)
    print(f"  Woven sequence: {len(woven)} paths per layer")

    # 3. Write single SVG
    svg_path = os.path.join(output_dir, "weave.svg")
    write_svg(svg_path, WIDTH, HEIGHT, woven, INSET)
    print(f"  SVG: {svg_path}")

    # 4. Build model — same woven pattern on each layer
    parsed = parse_svg_to_paths(svg_path, segment_length=0.5)
    model = Model(model_id=1, name="weave")
    model.offset_x = OFFSET_X
    model.offset_y = OFFSET_Y

    for i in range(NUM_REPEATS):
        phase = PHASE_SHIFT * i
        z = LAYER_HEIGHT * (i + 1)

        if phase == 0.0:
            layer_paths = parsed
        else:
            # Regenerate with phase shift
            p0 = make_sine_paths_single_dir(
                WIDTH, HEIGHT, SPAN, WAVELENGTH, AMPLITUDE, INSET,
                POINTS_PER_WAVE, direction=0, phase=phase,
            )
            p90 = make_sine_paths_single_dir(
                WIDTH, HEIGHT, SPAN, WAVELENGTH, AMPLITUDE, INSET,
                POINTS_PER_WAVE, direction=90, phase=phase,
            )
            shifted_svg = os.path.join(output_dir, f"weave_p{phase:.2f}.svg")
            write_svg(shifted_svg, WIDTH, HEIGHT,
                      interleave_weave_paths(p0, p90), INSET)
            layer_paths = parse_svg_to_paths(shifted_svg, segment_length=0.5)

        layer = Layer(layer_id=i + 1, paths=layer_paths,
                      name=f"weave_{i}", z_height=z)
        model.add_layer(layer)
        print(f"  Layer {i}: z={z:.2f}mm phase={phase:.1f}rad")

    # 5. Generate G-code
    print(f"\nGenerating G-code...")
    result = lb.model_to_gcode(
        model=model,
        output_path=output_gcode,
        print_params=print_params,
    )

    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"  GCode:  {result['gcode_path']}")
    print(f"  Layers: {result['num_layers']}")
    print(f"  Paths:  {result['num_paths']}")
    print("=" * 70)
