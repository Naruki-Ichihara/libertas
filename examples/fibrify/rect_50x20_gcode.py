"""
Generate gcode for a simple 50x20mm rectangle with arbitrary layup.

Layer types:
    P(infill_angle)  — Polymer layer (contour + infill at given angle)
    F(angle)         — Fiber layer (parallel fiber lines at given angle)

Stack them in any order in `stacking_sequence`.
"""

import libertas as lb
import os
import math
import numpy as np
from dataclasses import dataclass
from svgpathtools import Line, Path as SvgPath

# ============================================================================
# Layer spec helpers
# ============================================================================

@dataclass
class P:
    """Polymer layer: contour + infill."""
    infill_angle: float = 0       # infill line angle (degrees)
    pitch: float = 0.8            # infill line spacing (mm)
    inset: float = 0.3            # inset from contour (mm)
    layer_height: float = None    # mm per layer (None = use params default)

    def __repr__(self):
        return f"P({self.infill_angle}°)"


@dataclass
class F:
    """Fiber layer: parallel fiber lines."""
    angle: float = 0              # fiber angle (degrees, 0°=X, 90°=Y)
    threshold: float = 1.0+1e-3       # path connection threshold (mm)
    smooth_sigma: float = 0       # Gaussian smoothing
    decimate_epsilon: float = 0   # RDP decimation tolerance (mm)
    layer_height: float = None    # mm per layer (None = use params default)

    def __repr__(self):
        return f"F({self.angle}°)"


# ============================================================================
# Configuration  —  edit this section to change the print
# ============================================================================

_HERE = os.path.dirname(__file__)
output_dir = os.path.join(_HERE, "outputs", "rect_50x20")
output_gcode = os.path.join(output_dir, "rect_50x20.gcode")

# --- Geometry ---
WIDTH = 50.0        # X direction (mm)
LENGTH = 50.0       # Y direction (mm)
CENTER_X = 175.0    # Bed center X
CENTER_Y = 135.0    # Bed center Y

# --- Fiber ---
FIBER_PITCH = 1.0   # mm between fiber lines
FIBER_INSET = 0.5   # mm inset from edge

# --- Stacking sequence: define freely in any order ---
stacking_sequence = [
    P(infill_angle=0),
    P(infill_angle=90),
    F(angle=0),
    F(angle=90),
    F(angle=0),
    F(angle=90),
]

# --- Print parameters ---
params = lb.FibrifierParams(
    offset_x=CENTER_X - WIDTH / 2.0,
    offset_y=CENTER_Y - LENGTH / 2.0,
    layer_height=0.15,
    temperature=lb.FibrifierTemperatureParams(
        cf_print_temp=360,
        pl_print_temp=380,
        bed_temperature=160,
        build_chamber_temperature=100,
        material_storage_temperature=85,
        nozzle_cooldown_temperature=50,
    ),
    speed=lb.FibrifierSpeedParams(
        cf_print_feedrate=1000,
        perimeter_speed=40,
        after_cut_speed=70,
        rapid_move_feedrate=5500,
    ),
    extrusion=lb.FibrifierExtrusionParams(
        cf_extrusion_multiplier=0.993,
        pl_extrusion_multiplier=0.0250,
    ),
    fiber=lb.FibrifierFiberParams(
        nozzle_dead_length=23.73,
        minimal_printable_length=23.73,
        no_speed_up_length=5.0,
        anchoring_dwell=100,
        anchoring_height=3,
    ),
    retraction=lb.FibrifierRetractionParams(
        retract_length=9.0,
        retract_speed=40,
    ),
)


# ============================================================================
# Fiber SVG generation
# ============================================================================

def make_rect_fiber_svg(
    output_svg: str,
    angle_deg: float,
    width: float = WIDTH,
    length: float = LENGTH,
    pitch: float = FIBER_PITCH,
    inset: float = FIBER_INSET,
) -> dict:
    """
    Generate an SVG with a rectangular contour and parallel fiber lines
    at an arbitrary angle.
    """
    contour = SvgPath(
        Line(0 + 0j, width + 0j),
        Line(width + 0j, width + length * 1j),
        Line(width + length * 1j, length * 1j),
        Line(length * 1j, 0 + 0j),
    )
    fibers = _generate_angled_fibers(width, length, angle_deg, pitch, inset)
    return lb.create_fiber_svg(output_svg, contour=contour, fibers=fibers)


def _generate_angled_fibers(width, length, angle_deg, pitch, inset):
    """
    Generate parallel fiber lines at *angle_deg* inside a rectangle,
    with alternating direction for continuous printing.
    """
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    x0, x1 = inset, width - inset
    y0, y1 = inset, length - inset

    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    scan_proj = corners[:, 0] * (-sin_a) + corners[:, 1] * cos_a
    s_min, s_max = scan_proj.min(), scan_proj.max()

    fiber_proj = corners[:, 0] * cos_a + corners[:, 1] * sin_a
    t_min, t_max = fiber_proj.min(), fiber_proj.max()

    fibers = []
    s = s_min
    direction = 1
    while s <= s_max + 1e-9:
        ox = -sin_a * s
        oy = cos_a * s
        p0 = np.array([ox + cos_a * t_min, oy + sin_a * t_min])
        p1 = np.array([ox + cos_a * t_max, oy + sin_a * t_max])

        clipped = _clip_line_to_rect(p0, p1, x0, y0, x1, y1)
        if clipped is not None:
            (cx0, cy0), (cx1, cy1) = clipped
            if direction == 1:
                fibers.append(SvgPath(Line(complex(cx0, cy0), complex(cx1, cy1))))
            else:
                fibers.append(SvgPath(Line(complex(cx1, cy1), complex(cx0, cy0))))
            direction *= -1
        s += pitch

    return fibers


def _clip_line_to_rect(p0, p1, x0, y0, x1, y1):
    """Cohen-Sutherland line clipping to rectangle [x0,x1]x[y0,y1]."""
    INSIDE, LEFT, RIGHT, BOTTOM, TOP = 0, 1, 2, 4, 8

    def outcode(x, y):
        code = INSIDE
        if x < x0:   code |= LEFT
        elif x > x1: code |= RIGHT
        if y < y0:   code |= BOTTOM
        elif y > y1: code |= TOP
        return code

    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(p1[0]), float(p1[1])
    oc_a = outcode(ax, ay)
    oc_b = outcode(bx, by)

    for _ in range(20):
        if not (oc_a | oc_b):
            return (ax, ay), (bx, by)
        if oc_a & oc_b:
            return None
        oc_out = oc_a or oc_b
        dx, dy = bx - ax, by - ay
        if oc_out & TOP:
            t = (y1 - ay) / dy; nx, ny = ax + t * dx, y1
        elif oc_out & BOTTOM:
            t = (y0 - ay) / dy; nx, ny = ax + t * dx, y0
        elif oc_out & RIGHT:
            t = (x1 - ax) / dx; nx, ny = x1, ay + t * dy
        elif oc_out & LEFT:
            t = (x0 - ax) / dx; nx, ny = x0, ay + t * dy
        if oc_out == oc_a:
            ax, ay = nx, ny; oc_a = outcode(ax, ay)
        else:
            bx, by = nx, ny; oc_b = outcode(bx, by)
    return None


# ============================================================================
# Layer stack builder
# ============================================================================

def build_layup(
    stacking: list,
    params: lb.FibrifierParams,
    svg_dir: str = output_dir,
    width: float = WIDTH,
    length: float = LENGTH,
    fiber_pitch: float = FIBER_PITCH,
    fiber_inset: float = FIBER_INSET,
) -> lb.FibrifierModel:
    """
    Build a FibrifierModel from a stacking sequence of P() and F() specs.

    Args:
        stacking: List of P(...) and F(...) in bottom-up order.
        params: FibrifierParams for the printer.
        svg_dir: Directory for generated SVG files.
        width, length: Rectangle geometry (mm).
        fiber_pitch, fiber_inset: Fiber line spacing and edge inset (mm).

    Returns:
        FibrifierModel with all layers added.
    """
    svg_cache = {}
    model = lb.FibrifierModel(params=params)

    for spec in stacking:
        if isinstance(spec, F):
            if spec.angle not in svg_cache:
                svg_file = os.path.join(svg_dir, f"fiber_{spec.angle:+.0f}deg.svg")
                make_rect_fiber_svg(svg_file, angle_deg=spec.angle,
                                    width=width, length=length,
                                    pitch=fiber_pitch, inset=fiber_inset)
                svg_cache[spec.angle] = svg_file

            model.add(lb.FibrifierLayer.fiber(
                svg_cache[spec.angle],
                threshold=spec.threshold,
                smooth_sigma=spec.smooth_sigma,
                decimate_epsilon=spec.decimate_epsilon,
                layer_height=spec.layer_height,
            ))

        elif isinstance(spec, P):
            if not svg_cache:
                svg_file = os.path.join(svg_dir, "fiber_+0deg.svg")
                make_rect_fiber_svg(svg_file, angle_deg=0,
                                    width=width, length=length,
                                    pitch=fiber_pitch, inset=fiber_inset)
                svg_cache[0] = svg_file

            contour_svg = next(iter(svg_cache.values()))
            model.add(lb.FibrifierLayer.polymer(
                contour_svg,
                infill_angle=spec.infill_angle,
                infill_pitch=spec.pitch,
                infill_inset=spec.inset,
                layer_height=spec.layer_height,
            ))

        else:
            raise ValueError(f"Unknown layer spec: {spec!r}  (use P(...) or F(...))")

    return model


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70)
    seq_str = " / ".join(repr(s) for s in stacking_sequence)
    print(f"RECT {WIDTH:.0f}x{LENGTH:.0f}mm  —  {seq_str}")
    print("=" * 70)

    model = build_layup(stacking_sequence, params)
    model.summary()
    result = model.generate(output_gcode, flip_y=False)

    print("\n" + "=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"  Output:          {result['gcode_path']}")
    print(f"  Preview:         {result['preview_path']}")
    print(f"  Layers:          {result['n_layers']}")
    print(f"  Fiber paths:     {result['n_fiber_paths']}")
    print(f"  Total fiber:     {result['total_fiber_mm']:.1f} mm")
    print(f"  Total stretches: {result['total_stretches']}")
    print("=" * 70)
