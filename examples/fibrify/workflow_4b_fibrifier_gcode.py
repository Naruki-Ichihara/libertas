"""
Fibrifier G-code Generation for 2-Layer Stacked Laminate

Uses FibrifierModel / FibrifierLayer API to define layer stack:
  P(+10°) → F(+10°) → P(-10°) → F(-10°)

Parameters from ref.py (CFRTP Python Generator).

Run after: workflow_3b (stacked stripe generation).
"""

import libertas as lb

# ============================================================================
# Configuration
# ============================================================================

output_dir = "outputs/cantilever_10"

svg_10 = f"{output_dir}/stripe_paths_10deg.svg"
svg_m10 = f"{output_dir}/stripe_paths_-10deg.svg"

output_gcode = f"{output_dir}/cantilever_stacked_2layer.gcode"

# --- Fibrifier printing parameters (ref.py based) ---
params = lb.FibrifierParams(
    offset_x=95.0,
    offset_y=135.0,
    layer_height=0.15,

    temperature=lb.FibrifierTemperatureParams(
        cf_print_temp=360,
        cf_first_layer_temp=360,
        pl_print_temp=380,
        pl_first_layer_temp=380,
        bed_temperature=160,
        build_chamber_temperature=100,
        material_storage_temperature=85,
        nozzle_cooldown_temperature=50,
        preheat_target_temperature=380,
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
# Define layer stack
# ============================================================================

model = lb.FibrifierModel(params=params)

# --- Ply 1: +10° ---
model.add(lb.FibrifierLayer.polymer(svg_10, infill_angle=45, infill_pitch=0.402, layer_height=0.1))
model.add(lb.FibrifierLayer.fiber(svg_10, threshold=8.0))
model.add(lb.FibrifierLayer.fiber(svg_m10, threshold=8.0))

# ============================================================================
# Generate
# ============================================================================

print("\n" + "=" * 70)
print("FIBRIFIER G-CODE GENERATION")
print("=" * 70)

model.summary()
result = model.generate(output_gcode)

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 70)
print("GENERATION COMPLETE")
print("=" * 70)

print(f"\n  Output gcode:    {result['gcode_path']}")
print(f"  Preview:         {result['preview_path']}")
print(f"  Layers:          {result['n_layers']}")
print(f"  Fiber paths:     {result['n_fiber_paths']}")
print(f"  Contour paths:   {result['n_contour_paths']}")
print(f"  Total fiber:     {result['total_fiber_mm']:.1f} mm")
print(f"  Total stretches: {result['total_stretches']}")

print("\n" + "=" * 70 + "\n")
