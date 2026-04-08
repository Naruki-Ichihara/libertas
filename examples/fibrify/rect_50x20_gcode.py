"""
Generate gcode for a simple 50x20mm rectangle:
  - Polymer layers: perimeter + 0° infill
  - Fiber layers: straight lines along Y direction, spaced 1mm in X
  - Stack: P → F → P → F  (2 repeats)

SVGs are generated programmatically, then fed to FibrifierModel.
"""

import libertas as lb
import os

# ============================================================================
# Configuration (ref.py based)
# ============================================================================

output_dir = "outputs/rect_50x20"
os.makedirs(output_dir, exist_ok=True)

# Rectangle dimensions
WIDTH = 20.0     # X direction (mm)
LENGTH = 50.0    # Y direction (mm)

# Machine placement — rectangle center on bed
CENTER_X = 175.0
CENTER_Y = 135.0

# Fiber layout
FIBER_PITCH = 1.0       # mm between fiber lines (X spacing)
FIBER_INSET = 0.5       # mm inset from edge for fiber start

# SVG paths
svg_path = f"{output_dir}/rect_50x20.svg"
output_gcode = f"{output_dir}/rect_50x20.gcode"

# ============================================================================
# Step 1: Generate SVG with contour (rectangle) and stripe (fiber lines)
# ============================================================================

print("Generating SVG...")

# Rectangle boundary
xmin, xmax = 0.0, WIDTH
ymin, ymax = 0.0, LENGTH

# Contour: closed rectangle (for perimeter + infill)
contour_pts = f"{xmin},{ymin} {xmax},{ymin} {xmax},{ymax} {xmin},{ymax} {xmin},{ymin}"

# Fiber stripes: vertical lines (Y direction) spaced FIBER_PITCH in X
stripes = []
x = FIBER_INSET
direction = 1  # alternate direction for efficient path ordering
while x <= WIDTH - FIBER_INSET + 1e-6:
    if direction == 1:
        stripes.append(f'    <polyline points="{x:.4f},{ymin:.4f} {x:.4f},{ymax:.4f}"/>')
    else:
        stripes.append(f'    <polyline points="{x:.4f},{ymax:.4f} {x:.4f},{ymin:.4f}"/>')
    x += FIBER_PITCH
    direction *= -1

svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH:.6f}mm" height="{LENGTH:.6f}mm" viewBox="{xmin:.6f} {ymin:.6f} {WIDTH:.6f} {LENGTH:.6f}">
  <desc>Rectangle {WIDTH}x{LENGTH}mm with {len(stripes)} fiber lines</desc>
  <g id="stripe_contours" fill="none" stroke="#000000" stroke-width="0.01">
{chr(10).join(stripes)}
  </g>
  <g id="density_contours" fill="none" stroke="#FF0000" stroke-width="0.02">
    <polyline points="{contour_pts}"/>
  </g>
</svg>"""

with open(svg_path, "w") as f:
    f.write(svg_content)

print(f"  SVG: {svg_path}")
print(f"  Rectangle: {WIDTH}x{LENGTH}mm")
print(f"  Fiber lines: {len(stripes)} (pitch={FIBER_PITCH}mm)")

# ============================================================================
# Step 2: Build layer stack and generate gcode
# ============================================================================

print("\nBuilding layer stack...")

# Offset: place rectangle center at CENTER_X, CENTER_Y
offset_x = CENTER_X - WIDTH / 2.0
offset_y = CENTER_Y - LENGTH / 2.0

params = lb.FibrifierParams(
    offset_x=offset_x,
    offset_y=offset_y,
    layer_height=0.15,

    temperature=lb.FibrifierTemperatureParams(
        cf_print_temp=220,
        pl_print_temp=230,
        bed_temperature=90,
        build_chamber_temperature=90,
        material_storage_temperature=70,
        nozzle_cooldown_temperature=50,
    ),
    speed=lb.FibrifierSpeedParams(
        cf_print_feedrate=600,
        perimeter_speed=40,
        after_cut_speed=75,
        rapid_move_feedrate=5500,
    ),
    extrusion=lb.FibrifierExtrusionParams(
        cf_extrusion_multiplier=0.99,
        pl_extrusion_multiplier=0.68,
    ),
    fiber=lb.FibrifierFiberParams(
        nozzle_dead_length=21.5,
        minimal_printable_length=23.73,
        no_speed_up_length=5.0,
        anchoring_dwell=600,
        anchoring_height=3,
    ),
    retraction=lb.FibrifierRetractionParams(
        retract_length=3.0,
        retract_speed=60,
    ),
)

model = lb.FibrifierModel(params=params)

# P → F → P → F  (2 repeats)
for i in range(2):
    model.add(lb.FibrifierLayer.perimeter(svg_path, infill_angle=0))
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
