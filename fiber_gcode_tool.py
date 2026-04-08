"""
CFRTP Gcode Generator for curved fiber paths from SVG.

Output format matches Fibrifier (9T Labs) gcode exactly.
"""

import math
import datetime
import argparse
import numpy as np
import matplotlib.pyplot as plt
from libertas.svg_parser import parse_svg_to_paths
from libertas.layer import Layer
from libertas.path import Path


# ══════════════════════════════════════════════════════════════════
# Path preparation
# ══════════════════════════════════════════════════════════════════

def load_and_prepare_paths(
    svg_path: str,
    connection_threshold: float = 5.0,
    min_fiber_length: float = 23.73,
    start_point: tuple = None,
    flip_y: bool = True,
    smooth_sigma: float = 3.0,
    decimate_epsilon: float = 0.05,
):
    all_paths = parse_svg_to_paths(svg_path)
    print(f"Loaded {len(all_paths)} paths from SVG")

    import xml.etree.ElementTree as ET
    tree = ET.parse(svg_path)
    root = tree.getroot()
    viewbox = root.attrib.get("viewBox", "0 0 0 0").split()
    svg_height = float(viewbox[3])

    stripe_paths = [p for p in all_paths if p.path_type == "stripe"]
    contour_paths = [p for p in all_paths if p.path_type == "contour"]
    print(f"  Stripe (fiber): {len(stripe_paths)}, Contour (perimeter): {len(contour_paths)}")

    if flip_y:
        stripe_paths = _flip_paths_y(stripe_paths, svg_height)
        contour_paths = _flip_paths_y(contour_paths, svg_height)

    layer = Layer(layer_id=0, paths=stripe_paths)
    travel = layer.optimize_open_path_order(start_point=start_point)
    stripe_paths = [p for p in layer.paths if not p.is_closed]
    print(f"  TSP travel distance: {travel:.2f} mm  ({len(stripe_paths)} open paths)")

    connected = _connect_adjacent_paths(stripe_paths, connection_threshold)
    print(f"  After connection (threshold={connection_threshold} mm): {len(connected)} paths")

    total_before = sum(len(p.nodes) for p in connected)
    simplified = []
    for p in connected:
        new_nodes = simplify_path_nodes(p.nodes, sigma=smooth_sigma, epsilon=decimate_epsilon)
        simplified.append(Path(path_id=p.path_id, nodes=new_nodes, path_type=p.path_type))
    total_after = sum(len(p.nodes) for p in simplified)
    print(f"  Smoothing (σ={smooth_sigma}) + decimation (ε={decimate_epsilon}mm): "
          f"{total_before} → {total_after} points ({100*total_after/total_before:.0f}%)")

    filtered = [p for p in simplified if p.length >= min_fiber_length]
    dropped = len(simplified) - len(filtered)
    print(f"  Dropped {dropped} paths shorter than {min_fiber_length} mm → {len(filtered)} remain")

    return filtered, contour_paths, svg_height


def _flip_paths_y(paths, svg_height):
    flipped = []
    for p in paths:
        new_nodes = [(x, svg_height - y) for x, y in p.nodes]
        fp = Path(path_id=p.path_id, nodes=new_nodes, path_type=p.path_type)
        flipped.append(fp)
    return flipped


def _connect_adjacent_paths(paths, threshold):
    if not paths:
        return []
    groups = []
    current_group = [paths[0]]
    for i in range(1, len(paths)):
        prev = current_group[-1]
        curr = paths[i]
        dx = curr.start_point[0] - prev.end_point[0]
        dy = curr.start_point[1] - prev.end_point[1]
        dist = math.sqrt(dx * dx + dy * dy)
        if dist <= threshold:
            current_group.append(curr)
        else:
            groups.append(current_group)
            current_group = [curr]
    groups.append(current_group)
    merged = []
    for gid, group in enumerate(groups):
        nodes = list(group[0].nodes)
        for p in group[1:]:
            nodes.extend(p.nodes)
        merged.append(Path(path_id=gid, nodes=nodes, path_type="stripe"))
    return merged


# ══════════════════════════════════════════════════════════════════
# Smoothing & decimation
# ══════════════════════════════════════════════════════════════════

def _smooth_nodes(nodes, sigma=3):
    pts = np.array(nodes)
    from scipy.ndimage import gaussian_filter1d
    sx = gaussian_filter1d(pts[:, 0], sigma=sigma, mode="nearest")
    sy = gaussian_filter1d(pts[:, 1], sigma=sigma, mode="nearest")
    sx[0], sy[0] = pts[0, 0], pts[0, 1]
    sx[-1], sy[-1] = pts[-1, 0], pts[-1, 1]
    return list(zip(sx.tolist(), sy.tolist()))


def _rdp_decimate(nodes, epsilon=0.05):
    if len(nodes) <= 2:
        return nodes
    start = np.array(nodes[0])
    end = np.array(nodes[-1])
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)
    if line_len < 1e-12:
        dists = [np.linalg.norm(np.array(p) - start) for p in nodes]
        idx = int(np.argmax(dists))
        if dists[idx] < epsilon:
            return [nodes[0], nodes[-1]]
    else:
        line_unit = line_vec / line_len
        dists = []
        for p in nodes:
            v = np.array(p) - start
            proj = np.dot(v, line_unit)
            perp = np.linalg.norm(v - proj * line_unit)
            dists.append(perp)
        idx = int(np.argmax(dists))
    if dists[idx] > epsilon:
        left = _rdp_decimate(nodes[: idx + 1], epsilon)
        right = _rdp_decimate(nodes[idx:], epsilon)
        return left[:-1] + right
    else:
        return [nodes[0], nodes[-1]]


def simplify_path_nodes(nodes, sigma=3, epsilon=0.05):
    if sigma > 0:
        smoothed = _smooth_nodes(nodes, sigma=sigma)
    else:
        smoothed = nodes
    decimated = _rdp_decimate(smoothed, epsilon=epsilon)
    return decimated


# ══════════════════════════════════════════════════════════════════
# Geometry helpers
# ══════════════════════════════════════════════════════════════════

def _segment_angle_deg(x0, y0, x1, y1):
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


def _compute_smooth_angles(nodes, sigma=2):
    from scipy.ndimage import gaussian_filter1d
    n = len(nodes)
    raw = []
    for i in range(n - 1):
        raw.append(_segment_angle_deg(
            nodes[i][0], nodes[i][1], nodes[i + 1][0], nodes[i + 1][1]))
    raw.append(raw[-1])
    rads = np.deg2rad(raw)
    s_sin = gaussian_filter1d(np.sin(rads), sigma=sigma, mode="nearest")
    s_cos = gaussian_filter1d(np.cos(rads), sigma=sigma, mode="nearest")
    smooth_rads = np.arctan2(s_sin, s_cos)
    return np.rad2deg(smooth_rads).tolist()


def _cumulative_distances_from_end(nodes):
    n = len(nodes)
    dist = np.zeros(n)
    for i in range(n - 2, -1, -1):
        dx = nodes[i + 1][0] - nodes[i][0]
        dy = nodes[i + 1][1] - nodes[i][1]
        dist[i] = dist[i + 1] + math.sqrt(dx * dx + dy * dy)
    return dist


def _find_cut_index(nodes, nozzle_dead_length):
    """Find node index where remaining arc-length to end = nozzle_dead_length."""
    dist_from_end = _cumulative_distances_from_end(nodes)
    for i in range(len(nodes) - 1, 0, -1):
        if dist_from_end[i] >= nozzle_dead_length:
            if i < len(nodes) - 1:
                overshoot = dist_from_end[i] - nozzle_dead_length
                seg_len = dist_from_end[i] - dist_from_end[i + 1]
                if seg_len > 1e-9:
                    t = overshoot / seg_len
                    x = nodes[i][0] + t * (nodes[i + 1][0] - nodes[i][0])
                    y = nodes[i][1] + t * (nodes[i + 1][1] - nodes[i][1])
                    return i, (x, y)
            return i, nodes[i]
    return 0, nodes[0]


def _anchor_point(nodes, anchor_distance):
    x0, y0 = nodes[0]
    x1, y1 = nodes[1]
    dx, dy = x1 - x0, y1 - y0
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 1e-9:
        return (x0, y0 - anchor_distance)
    ux, uy = dx / seg_len, dy / seg_len
    return (x0 - ux * anchor_distance, y0 - uy * anchor_distance)


def _ironing_point(nodes, ironing_distance):
    x0, y0 = nodes[-2]
    x1, y1 = nodes[-1]
    dx, dy = x1 - x0, y1 - y0
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 1e-9:
        return (x1, y1)
    ux, uy = dx / seg_len, dy / seg_len
    return (x1 + ux * ironing_distance, y1 + uy * ironing_distance)


# ══════════════════════════════════════════════════════════════════
# Gcode generation — Fibrifier-compatible format
# ══════════════════════════════════════════════════════════════════

class FibrifierGcodeGenerator:
    """Generate gcode in Fibrifier (9T Labs) format."""

    def __init__(
        self,
        offset_x: float = 175.0,
        offset_y: float = 135.0,
        layer_height: float = 0.15,
        # Fibrifier config parameters (from reference)
        cf_extrusion_multiplier: float = 0.99,
        cf_print_feedrate: int = 600,
        pl_extrusion_multiplier: float = 0.68,
        pl_print_temp: int = 230,
        cf_print_temp: int = 220,
        nozzle_dead_length: float = 21.5,
        nozzle_cooldown_temperature: int = 50,
        anchoring_dwell: int = 600,
        anchoring_height: int = 3,
        after_cut_speed: int = 75,
        no_speed_up_length: float = 5.0,
        rapid_move_feedrate: int = 5500,
        perimeter_speed: int = 40,
        bed_temperature: int = 90,
        build_chamber_temperature: int = 90,
        material_storage_temperature: int = 70,
        retract_length: float = 3.0,
        retract_speed: int = 60,
        minimal_printable_length: float = 23.73,
    ):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.layer_height = layer_height

        # Fibrifier params
        self.cf_em = cf_extrusion_multiplier
        self.cf_feed = cf_print_feedrate
        self.pl_em = pl_extrusion_multiplier
        self.pl_temp = pl_print_temp
        self.cf_temp = cf_print_temp
        self.nozzle_dead_length = nozzle_dead_length
        self.nozzle_cooldown_temp = nozzle_cooldown_temperature
        self.anchor_dwell = anchoring_dwell
        self.anchor_height = anchoring_height
        self.after_cut_speed = after_cut_speed
        self.no_speed_up_length = no_speed_up_length
        self.rapid_feed = rapid_move_feedrate
        self.perimeter_speed = perimeter_speed
        self.bed_temp = bed_temperature
        self.chamber_temp = build_chamber_temperature
        self.material_temp = material_storage_temperature
        self.retract_length = retract_length
        self.retract_speed = retract_speed
        self.min_length = minimal_printable_length

        # Derived
        self.after_cut_feed = int(after_cut_speed / 100.0 * self.cf_feed)  # 75% of cf_feed -> 450
        self.perimeter_feed = int(perimeter_speed / 10.0 * 60)  # mm/s -> mm/min approximation
        # From reference: perimeter F1800 (first layer), F2400 (later)
        # infill F1800 (first layer), F3600 (later)

        # Global stretch counter
        self._stretch_counter = 0

    def _tx(self, x):
        return x + self.offset_x

    def _ty(self, y):
        return y + self.offset_y

    def _next_stretch(self):
        idx = self._stretch_counter
        self._stretch_counter += 1
        return idx

    def generate_multilayer(self, layers, filename="output.gcode"):
        """
        layers: list of dicts with keys:
            'fiber': list of Path (stripe)
            'contour': list of Path (contour)
            'type': 'P' (polymer) or 'F' (fiber) — auto-detected if missing
        Alternating P/F layers like the reference: P, F, P, F, ...
        """
        self._stretch_counter = 0

        with open(filename, "w") as f:
            # Compute bounding box in machine coords
            all_x, all_y = [], []
            for ld in layers:
                for plist in [ld.get("fiber", []), ld.get("contour", [])]:
                    for p in plist:
                        for x, y in p.nodes:
                            all_x.append(self._tx(x))
                            all_y.append(self._ty(y))
            if all_x:
                bbox = (min(all_x), min(all_y), max(all_x), max(all_y))
            else:
                bbox = (0, 0, 0, 0)

            n_layers = len(layers)
            self._write_header(f, bbox=bbox, n_layers=n_layers)
            for layer_idx, layer_data in enumerate(layers):
                z = round((layer_idx + 1) * self.layer_height, 4)
                fiber_paths = layer_data.get("fiber", [])
                contour_paths = layer_data.get("contour", [])
                layer_type = layer_data.get("type", None)

                # Auto-detect type if not specified
                if layer_type is None:
                    layer_type = "F" if fiber_paths else "P"

                f.write(f";========================\n")
                f.write(f"; - START OF ZCHUNK #{layer_idx + 1}, "
                        f"range=[{z:.2f}, {z:.2f}] -\n")
                f.write(f";========================\n")

                if layer_type == "P":
                    self._write_polymer_layer(f, z, layer_idx, contour_paths, layers)
                elif layer_type == "F":
                    self._write_fiber_layer(f, z, layer_idx, fiber_paths, layers)

                # After first layer
                if layer_idx == 0:
                    f.write(f";- after first layer -\n")
                    f.write(f"M104 S{self.cf_temp} T0\n")
                    f.write(f"M140 S{self.bed_temp} ; wait for bed temp\n")
                    f.write(f";- after first layer -\n")

                f.write(f";========================\n")
                f.write(f"; - END OF ZCHUNK #{layer_idx + 1}, "
                        f"range=[{z:.2f}, {z:.2f}] -\n")
                f.write(f";========================\n")

            self._write_footer(f)

        total_fiber = sum(
            sum(p.length for p in ld.get("fiber", []))
            for ld in layers
        )
        print(f"[{filename}] generated: {n_layers} layers, "
              f"{self._stretch_counter} stretches, "
              f"total fiber={total_fiber:.1f}mm")

    # ── Header ──────────────────────────────────────────────

    def _write_header(self, f, bbox=None, n_layers=1):
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        zmax = round(n_layers * self.layer_height, 3)

        # Bounding box (machine coords)
        if bbox:
            xmin, ymin, xmax, ymax = bbox
        else:
            xmin = ymin = xmax = ymax = 0.0

        f.write(f"; 9Code-Version = 1.0\n")
        f.write(f"; Creation-Date = {now}\n")
        f.write(f"; Creator = fiber_gcode_tool.py\n")
        f.write(f"; Slicing-Engine = Custom Python Script\n")
        f.write(f"\n")

        # Parts block
        f.write(f"; -- Parts --\n")
        f.write(f"; generated_part\n")
        f.write(f"; xmin = {xmin:.3f}\n")
        f.write(f"; xmax = {xmax:.3f}\n")
        f.write(f"; ymin = {ymin:.3f}\n")
        f.write(f"; ymax = {ymax:.3f}\n")
        f.write(f"; zmin = 0.000\n")
        f.write(f"; zmax = {zmax:.3f}\n")
        f.write(f"; -- End Parts --\n")
        f.write(f";\n")

        # Full Fibrifier config (all keys from reference, alphabetical order within groups)
        f.write(f";-- Fibrifier Config --\n")
        f.write(f"; bed_shape = 0x0,350x0,350x280,0x280\n")
        f.write(f"; fiber_helix = 0\n")
        f.write(f"; first_layers_at_once = 0\n")
        f.write(f"; gcode_stubs_dir = stubs\n")
        f.write(f"; after_cut_speed = {self.after_cut_speed}\n")
        f.write(f"; anchoring_angle = 9\n")
        f.write(f"; anchoring_dwell = {self.anchor_dwell}\n")
        f.write(f"; anchoring_height = {self.anchor_height}\n")
        f.write(f"; anchoring_length = 2\n")
        f.write(f"; bed_temperature = {self.bed_temp}\n")
        f.write(f"; build_chamber_temperature = {self.chamber_temp}\n")
        f.write(f"; cf_extrusion_multiplier = {self.cf_em}\n")
        f.write(f"; cf_first_layer_temperature = {self.cf_temp}\n")
        f.write(f"; cf_print_feedrate = {self.cf_feed}\n")
        f.write(f"; cf_print_temp = {self.cf_temp}\n")
        f.write(f"; corner_direction_correction_angle_treshold = 30\n")
        f.write(f"; corner_dwell = 0\n")
        f.write(f"; corner_nozzle_lift_slack = 0\n")
        f.write(f"; corner_nozzle_z_lift = 0\n")
        f.write(f"; corner_overshoot_length = 0\n")
        f.write(f"; corner_slack_ratio = 0\n")
        f.write(f"; deposition_offset = 0\n")
        f.write(f"; fiber_height = {self.layer_height}\n")
        f.write(f"; fiber_helix_z_transition = 10\n")
        f.write(f"; fiber_max_extrusion_radius = 100\n")
        f.write(f"; fiber_min_extrusion_radius = 8\n")
        f.write(f"; fiber_min_radius_extrusion_multiplier = {self.cf_em}\n")
        f.write(f"; fiber_width = 1.5\n")
        f.write(f"; first_layer_bed_temperature = {self.bed_temp}\n")
        f.write(f"; first_layer_extrusion_multiplier = 1\n")
        f.write(f"; layer_height = {self.layer_height}\n")
        f.write(f"; material_storage_temperature = {self.material_temp}\n")
        f.write(f"; minimal_extrusion_plastic_stretch = 0.02\n")
        f.write(f"; minimal_printable_length = {self.min_length}\n")
        f.write(f"; no_speed_up_length = {int(self.no_speed_up_length)}\n")
        f.write(f"; nozzle_cooldown_temperature = {self.nozzle_cooldown_temp}\n")
        f.write(f"; nozzle_dead_length = {self.nozzle_dead_length}\n")
        f.write(f"; perimeter_speed = {self.perimeter_speed}\n")
        f.write(f"; pl_extrusion_multiplier = {self.pl_em}\n")
        f.write(f"; pl_first_layer_speed = 30\n")
        f.write(f"; pl_first_layer_temperature = {self.pl_temp}\n")
        f.write(f"; pl_print_temp = {self.pl_temp}\n")
        f.write(f"; plastic_cover_extrusion_multipier = 0.85\n")
        f.write(f"; plastic_cover_feedrate = 60\n")
        f.write(f"; preheat_target_temperature = {self.pl_temp}\n")
        f.write(f"; preheat_time = 60\n")
        f.write(f"; rapid_move_feedrate = {self.rapid_feed}\n")
        f.write(f"; retract_length = {int(self.retract_length)}\n")
        f.write(f"; retract_lift = 0\n")
        f.write(f"; retract_speed = {self.retract_speed}\n")
        f.write(f"; straight_line_feedrate = {self.cf_feed}\n")
        f.write(f"; stretch_beginning_length = 0\n")
        f.write(f"; stretch_beginning_multiplier = 1.2\n")
        f.write(f";-- End Fibrifier Config --\n")
        f.write(f"\n")

        # Start code — matches reference exactly
        f.write(f";*-- START CODE --\n")
        f.write(f"CLEAR_PAUSE ; clear any saved pause states\n")
        f.write(f"\n")
        f.write(f"G21 ; set units to millimeters\n")
        f.write(f"G90 ; use absolute coordinates\n")
        f.write(f"M83 ; extruder relative mode\n")
        f.write(f"\n")
        f.write(f"SET_PIN PIN=lamps VALUE=0.7\n")
        f.write(f"\n")
        f.write(f"M104 S130 T0 ; set fiber extruder temperature\n")
        f.write(f"M140 S{self.bed_temp} ; set bed temp\n")
        f.write(f"\n")
        f.write(f"G28 ; Home all axes\n")
        f.write(f"\n")
        f.write(f"M109 S130 T0 ; set fiber extruder temp\n")
        f.write(f"G28 W ; re-home FG after it has heated up\n")
        f.write(f"\n")
        f.write(f"M190 S{self.bed_temp} ; wait for bed temp\n")
        f.write(f"M104 S{self.cf_temp} T0 ; set fiber extruder temp\n")
        f.write(f"\n")
        pl_75 = int(self.pl_temp * 0.75)
        f.write(f"M104 S{pl_75} T1 ; set 75% polymer nozzle temp\n")
        f.write(f"G29 ; Meshbed leveling\n")
        f.write(f"\n")
        f.write(f"G0 Z3.0000 F{self.rapid_feed}\n")
        f.write(f"\n")
        f.write(f"M109 S{self.pl_temp} T1 ; wait for first layer polymer temeprature\n")
        f.write(f"M109 S{self.cf_temp} T0 ; wait for FG printing temperature\n")
        f.write(f"\n")
        f.write(f"T1 ; change to polymer extruder\n")
        f.write(f"\n")
        f.write(f"G0 X100.0000 Y3.0000 Z0.5000 F{self.rapid_feed} ; go outside print area\n")
        f.write(f"G1 X60.0000 E9.0000 F1000 ; intro line\n")
        f.write(f"G1 X20.0000 E12.5000 F1000 ; intro line\n")
        f.write(f"G92 E0.0\n")
        f.write(f"\n")
        f.write(f"SET_RETRACTION RETRACT_LENGTH={self.retract_length:.1f} "
                f"RETRACT_SPEED={float(self.retract_speed):.1f}\n")
        f.write(f"SET_HEATER_TEMPERATURE HEATER=print_chamber "
                f"target={float(self.chamber_temp):.1f}\n")
        f.write(f"SET_HEATER_TEMPERATURE HEATER=material_chamber "
                f"target={float(self.material_temp):.1f}\n")
        f.write(f";*-- END OF START CODE --\n")

    # ── Polymer layer ───────────────────────────────────────

    def _write_polymer_layer(self, f, z, layer_idx, contour_paths, all_layers):
        """Write a full polymer layer (perimeters + infill)."""

        # If previous layer was fiber, do Fiber→Polymer transition
        if layer_idx > 0:
            prev_type = all_layers[layer_idx - 1].get("type", "F")
            if prev_type == "F":
                self._write_fiber_to_polymer_init(f, z)

        is_first = (layer_idx == 0)
        perimeter_f = 1800 if is_first else 2400
        infill_f = 1800 if is_first else 3600

        for cidx, cp in enumerate(contour_paths):
            stretch_id = self._next_stretch()
            nodes = cp.nodes

            # Determine if this is perimeter or infill based on index
            # In ref: first N are perimeters, rest are infill
            # We treat all contour paths as perimeters
            label = "perimeter"
            feed = perimeter_f

            sx, sy = self._tx(nodes[0][0]), self._ty(nodes[0][1])

            # Initialization block
            # Z-lift: first layer uses Z+0.35, others use same Z
            z_lift = z + 0.35 if is_first else z

            f.write(f";- START OF POLYMER STRETCH INITIALIZATION -\n")
            if cidx == 0 and is_first:
                f.write(f"G10\n")
            elif cidx == 0 and not is_first:
                pass  # transition already handled
            f.write(f"G0 Z{z_lift:.4f} F{self.rapid_feed} ; lift Z\n")
            f.write(f"G0 X{sx:.4f} Y{sy:.4f}\n")
            f.write(f"G0 Z{z:.4f} ; restore layer Z\n")
            f.write(f"G1 F{feed}\n")
            if cidx == 0:
                f.write(f"G11\n")
            f.write(f";- END OF POLYMER STRETCH INITIALIZATION -\n")

            f.write(f";------------------------\n")
            f.write(f"; - START OF POLYMER STRETCH #{stretch_id} -\n")
            f.write(f";------------------------\n")

            prev = nodes[0]
            for nx, ny in nodes[1:]:
                dx = nx - prev[0]
                dy = ny - prev[1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1e-5:
                    e_val = dist * self.pl_em
                    f.write(f"G1 X{self._tx(nx):.4f} Y{self._ty(ny):.4f} "
                            f"E{e_val:.4f} ; {label}\n")
                prev = (nx, ny)

            f.write(f";------------------------\n")
            f.write(f"; - END OF POLYMER STRETCH #{stretch_id} -\n")
            f.write(f";------------------------\n")

    def _write_fiber_to_polymer_init(self, f, z):
        """Fiber→Polymer transition (matches Fibrifier format exactly)."""
        f.write(f";- START OF POLYMER STRETCH INITIALIZATION -\n")
        f.write(f"G10 S1\n")
        f.write(f"; nozzle change gcode for switching from the fiber guide (T0) "
                f"to the polymer nozzle(T1)\n")
        f.write(f"M104 S{self.pl_temp} T1 ; set polymer nozzle temperature\n")
        f.write(f"SET_STATE_TARGET STATE=buffer TARGET=0\n")
        f.write(f"\n")
        f.write(f"G91 ; use relative coordinates\n")
        f.write(f"G0 Z3.0000 F{self.rapid_feed} ; sits currently at heigth +3 over layer\n")
        f.write(f"G90 ; use absolute coordinates\n")
        f.write(f"M83 ; extruder relative mode\n")
        f.write(f"\n")
        f.write(f"M109 S{self.pl_temp} T1 ; wait for polymer nozzle temperature\n")
        f.write(f"M104 S{self.pl_temp} T1 ; set polymer nozzle temperature\n")
        f.write(f"T1 ; change nozzle\n")
        f.write(f"; end of T1 for Shoed-Red-Series\n")

    # ── Fiber layer ─────────────────────────────────────────

    def _write_fiber_layer(self, f, z, layer_idx, fiber_paths, all_layers):
        """Write a full fiber layer."""
        f.write(f"G0 Z{z:.4f} ; to next layer transition\n")

        # Polymer→Fiber transition
        self._write_polymer_to_fiber_init(f, z)

        n_passes = len(fiber_paths)
        for pidx, fp in enumerate(fiber_paths):
            is_last_pass_of_last_fiber_before_polymer = False
            # Check if polymer follows: preheat polymer nozzle during last passes
            next_layer_type = None
            if layer_idx + 1 < len(all_layers):
                next_layer_type = all_layers[layer_idx + 1].get("type", "P")

            self._write_fiber_stretch(
                f, fp, z, pidx, n_passes,
                preheat_polymer=(next_layer_type == "P"),
                is_last_fiber_layer_pass=(pidx >= n_passes - 2),
            )

    def _write_polymer_to_fiber_init(self, f, z):
        """Polymer→Fiber transition (matches Fibrifier format exactly)."""
        f.write(f";- START OF Fiber STRETCH INITIALIZATION -\n")
        f.write(f"G10 S1\n")
        f.write(f"; nozzle change gcode for switching from the polymer nozzle(T1) "
                f"to the fiber guide (T0)\n")
        f.write(f"M104 S{self.nozzle_cooldown_temp} T1 ; cool down polymer nozzle\n")
        f.write(f"G10\n")
        f.write(f"G91 ; use relative coordinates\n")
        f.write(f"G0 Z3.0000 F{self.rapid_feed}\n")
        f.write(f"G90 ; use absolute coordinates\n")
        f.write(f"M83 ; extruder relative mode\n")
        f.write(f"\n")
        f.write(f"T0 ; change to fiber guide\n")
        f.write(f"SET_STATE_TARGET STATE=buffer TARGET={z:.1f}\n")
        f.write(f"; end of T0 for Shoed-Red-Series\n")
        f.write(f";- END OF Fiber STRETCH INITIALIZATION -\n")

    def _write_fiber_stretch(self, f, path, z, pass_idx, total_passes,
                              preheat_polymer=False, is_last_fiber_layer_pass=False):
        stretch_id = self._next_stretch()
        nodes = path.nodes
        n = len(nodes)

        f.write(f";------------------------\n")
        f.write(f"; - START OF Fiber STRETCH #{stretch_id} -\n")
        f.write(f";------------------------\n")

        # Compute cut position
        cut_idx, cut_point = _find_cut_index(nodes, self.nozzle_dead_length)

        # Compute smoothed direction angles
        angles = _compute_smooth_angles(nodes)

        # Anchor point
        anchor = _anchor_point(nodes, self.nozzle_dead_length)
        start_angle = angles[0]

        # Move to anchor position
        f.write(f"USE_ABSOLUTE_ROTARY_POSITION\n")
        f.write(f"G0 X{self._tx(anchor[0]):.4f} Y{self._ty(anchor[1]):.4f} "
                f"Z{z + self.anchor_height:.4f} W{start_angle:.4f} "
                f"F{self.rapid_feed} ;move to anchoring start\n")
        f.write(f"USE_RELATIVE_ROTARY_POSITION\n")
        f.write(f"G0 E23.5000 F{self.cf_feed}\n")

        # Move to start
        f.write(f"G1 X{self._tx(nodes[0][0]):.4f} Y{self._ty(nodes[0][1]):.4f} "
                f"Z{z:.4f} F{self.cf_feed}\n")
        f.write(f"G4 P{self.anchor_dwell} ;anchoring dwell\n")

        # Lay fiber with rotation and extrusion
        prev_angle = start_angle
        prev = nodes[0]
        cut_emitted = False

        # Compute cumulative distance from end for preheat scheduling
        dist_from_end = _cumulative_distances_from_end(nodes)

        for i in range(1, n):
            x, y = nodes[i]
            angle = angles[i]

            # Insert cut point
            if not cut_emitted and i == cut_idx + 1 and cut_point != nodes[cut_idx]:
                cx, cy = cut_point
                dist = math.sqrt((cx - prev[0])**2 + (cy - prev[1])**2)
                if dist > 1e-5:
                    e_val = dist * self.cf_em
                    w_delta = _wrap_angle(angle - prev_angle)
                    w_cmd = f" W{w_delta:.4f}" if abs(w_delta) > 0.01 else ""
                    f.write(f"G1 X{self._tx(cx):.4f} Y{self._ty(cy):.4f} "
                            f"Z{z:.4f} E{e_val:.4f}{w_cmd} F{self.cf_feed}\n")
                    prev = (cx, cy)
                    prev_angle = angle
                f.write(f"cut_filament\n")
                cut_emitted = True

            # Check if we need to emit cut right at this node
            if not cut_emitted and i > cut_idx:
                f.write(f"cut_filament\n")
                cut_emitted = True

            dx = x - prev[0]
            dy = y - prev[1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 1e-5:
                prev = (x, y)
                continue

            w_delta = _wrap_angle(angle - prev_angle)
            past_cut = cut_emitted

            if past_cut:
                # After cut: no extrusion
                remaining = dist_from_end[i] if i < n else 0
                f.write(f"G1 X{self._tx(x):.4f} Y{self._ty(y):.4f} "
                        f"Z{z:.4f} W0.0000 "
                        f"F{self.after_cut_feed}\n")
            else:
                e_val = dist * self.cf_em
                w_cmd = f" W{w_delta:.4f}" if abs(w_delta) > 0.01 else ""
                f.write(f"G1 X{self._tx(x):.4f} Y{self._ty(y):.4f} "
                        f"Z{z:.4f} E{e_val:.4f}{w_cmd} F{self.cf_feed}\n")

            prev = (x, y)
            prev_angle = angle

        if not cut_emitted:
            f.write(f"cut_filament\n")

        # Sum of skipped extrusion comment (matches reference)
        f.write(f"; sum of skipped extrusion after the cut: {self.nozzle_dead_length}\n")

        # Ironing out move
        iron = _ironing_point(nodes, self.no_speed_up_length)
        f.write(f"G0 X{self._tx(iron[0]):.4f} Y{self._ty(iron[1]):.4f} "
                f"Z{z:.4f} W0.0000 F{self.after_cut_feed} ;Ironing out move\n")

        f.write(f";------------------------\n")
        f.write(f"; - END OF Fiber STRETCH #{stretch_id} -\n")
        f.write(f";------------------------\n")

    # ── Footer ──────────────────────────────────────────────

    def _write_footer(self, f):
        f.write(f";*-- END CODE --\n")
        f.write(f"G90\n")
        f.write(f"M83\n")
        f.write(f"USE_ABSOLUTE_ROTARY_POSITION\n")
        f.write(f"G1 Z100.0000 W0.0000 F6000 ; move to anchoring start\n")
        f.write(f"USE_RELATIVE_ROTARY_POSITION\n")
        f.write(f"M104 S0 T0 ; turn off fiber guide\n")
        f.write(f"M104 S0 T1 ; turn off polymer nozzle\n")
        f.write(f"M140 S0 ; turn off bed\n")
        f.write(f"set_state_target state=buffer target=0 ; turn off buffer\n")
        f.write(f"set_heater_temperature heater=print_chamber target=0 "
                f"; turn off chamber heater\n")
        f.write(f";*-- END OF END CODE --\n")
        f.write(f"\n")


def _wrap_angle(a):
    """Wrap angle to [-180, 180]."""
    return (a + 180) % 360 - 180


# ══════════════════════════════════════════════════════════════════
# Visualisation
# ══════════════════════════════════════════════════════════════════

def plot_paths(fiber_paths, contour_paths, title="Connected Fiber Paths"):
    fig, ax = plt.subplots(figsize=(16, 5))
    cmap = plt.cm.tab20
    for cp in contour_paths:
        xs = [n[0] for n in cp.nodes]
        ys = [n[1] for n in cp.nodes]
        ax.plot(xs, ys, color="red", linewidth=0.8, alpha=0.6)
    for idx, fp in enumerate(fiber_paths):
        colour = cmap(idx % 20)
        xs = [n[0] for n in fp.nodes]
        ys = [n[1] for n in fp.nodes]
        ax.plot(xs, ys, color=colour, linewidth=1.0,
                label=f"F{idx} ({fp.length:.1f}mm, {len(fp.nodes)}pts)")
        ax.plot(xs[0], ys[0], "o", color=colour, markersize=4)
        ax.plot(xs[-1], ys[-1], "s", color=colour, markersize=4)
    for i in range(len(fiber_paths) - 1):
        x0, y0 = fiber_paths[i].end_point
        x1, y1 = fiber_paths[i + 1].start_point
        ax.plot([x0, x1], [y0, y1], "--", color="grey", linewidth=0.5, alpha=0.5)
    ax.set_aspect("equal")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_title(title)
    if len(fiber_paths) <= 30:
        ax.legend(fontsize=5, ncol=3, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    return fig, ax


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="CFRTP curved-fiber gcode generator (Fibrifier format)")
    parser.add_argument("svg", nargs="+",
                        help="Input SVG file(s), one per layer (bottom-up)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output gcode file path")
    parser.add_argument("--threshold", type=float, default=5.0,
                        help="Connection threshold in mm (default: 5.0)")
    parser.add_argument("--min-length", type=float, default=23.73,
                        help="Minimum fiber length in mm (default: 23.73)")
    parser.add_argument("--offset-x", type=float, default=175.0,
                        help="Bed offset X (default: 175.0)")
    parser.add_argument("--offset-y", type=float, default=135.0,
                        help="Bed offset Y (default: 135.0)")
    parser.add_argument("--layer-height", type=float, default=0.15,
                        help="Layer height (default: 0.15)")
    parser.add_argument("--smooth-sigma", type=float, default=3.0,
                        help="Gaussian smoothing sigma (default: 3.0)")
    parser.add_argument("--decimate-epsilon", type=float, default=0.05,
                        help="RDP decimation tolerance mm (default: 0.05)")
    parser.add_argument("--no-flip-y", action="store_true",
                        help="Do not flip Y axis")
    parser.add_argument("--plot", type=str, default=None,
                        help="Save path preview plot to file")
    args = parser.parse_args()

    # Each SVG produces 2 layers: P (contour perimeters) + F (fiber stripes)
    layers = []
    all_fiber = []
    all_contour = []
    for i, svg in enumerate(args.svg):
        print(f"\n=== SVG {i + 1}: {svg} ===")
        fiber, contour, svg_h = load_and_prepare_paths(
            svg_path=svg,
            connection_threshold=args.threshold,
            min_fiber_length=args.min_length,
            flip_y=not args.no_flip_y,
            smooth_sigma=args.smooth_sigma,
            decimate_epsilon=args.decimate_epsilon,
        )
        # P layer: contour perimeters only
        layers.append({"fiber": [], "contour": contour, "type": "P"})
        # F layer: fiber stripes only
        layers.append({"fiber": fiber, "contour": [], "type": "F"})
        all_fiber.extend(fiber)
        all_contour.extend(contour)

    output = args.output or "output_fibrifier.gcode"

    # Always save preview plot alongside gcode
    plot_path = args.plot or output.replace(".gcode", "_preview.png")
    fig, ax = plot_paths(all_fiber, all_contour,
                         title=f"{len(args.svg)}-SVG stack ({len(all_fiber)} fiber paths)")
    fig.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot saved to {plot_path}")
    gen = FibrifierGcodeGenerator(
        offset_x=args.offset_x,
        offset_y=args.offset_y,
        layer_height=args.layer_height,
    )
    gen.generate_multilayer(layers, filename=output)


if __name__ == "__main__":
    main()
