"""
Generate gcode for a simple 50x20mm rectangle:
  - Polymer layers: contour + 0° infill
  - Fiber layers: straight lines along Y direction, spaced 1mm in X
  - Stack: P → F → P → F  (2 repeats)
"""

import libertas as lb
import os
from svgpathtools import Line, Path as SvgPath

# ============================================================================
# Configuration
# ============================================================================

output_dir = "outputs/rect_50x20"
os.makedirs(output_dir, exist_ok=True)

WIDTH = 20.0      # X direction (mm)
LENGTH = 50.0     # Y direction (mm)
CENTER_X = 175.0  # Bed center X
CENTER_Y = 135.0  # Bed center Y

FIBER_PITCH = 1.0   # mm between fiber lines
FIBER_INSET = 0.5   # mm inset from edge

svg_path = f"{output_dir}/rect_50x20.svg"
output_gcode = f"{output_dir}/rect_50x20.gcode"

# ============================================================================
# Step 1: Generate SVG
# ============================================================================

print("Generating SVG...")

# Contour: closed rectangle
contour = SvgPath(
    Line(0+0j, WIDTH+0j),
    Line(WIDTH+0j, WIDTH+LENGTH*1j),
    Line(WIDTH+LENGTH*1j, LENGTH*1j),
    Line(LENGTH*1j, 0+0j),
)

# Fiber stripes: vertical lines alternating direction
fibers = []
x = FIBER_INSET
direction = 1
while x <= WIDTH - FIBER_INSET + 1e-6:
    if direction == 1:
        fibers.append(SvgPath(Line(complex(x, 0), complex(x, LENGTH))))
    else:
        fibers.append(SvgPath(Line(complex(x, LENGTH), complex(x, 0))))
    x += FIBER_PITCH
    direction *= -1

result = lb.create_fiber_svg(svg_path, contour=contour, fibers=fibers)
print(f"  {result}")

# ============================================================================
# Step 2: Build layer stack and generate gcode
# ============================================================================

print("\nBuilding layer stack...")

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

model = lb.FibrifierModel(params=params)

for i in range(2):
    model.add(lb.FibrifierLayer.polymer(svg_path, infill_angle=0))
    model.add(lb.FibrifierLayer.fiber(svg_path, threshold=2.0, smooth_sigma=0, decimate_epsilon=0))

model.summary()
result = model.generate(output_gcode, flip_y=False)

# ============================================================================
# Summary
# ============================================================================

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
