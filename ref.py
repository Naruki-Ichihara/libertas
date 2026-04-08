import math
import datetime

class CFRTPGcodeGenerator:
    def __init__(self, center_x, center_y, width, length, layer_height, sequence):
        self.center_x = center_x
        self.center_y = center_y
        self.width = width
        self.length = length
        self.layer_height = layer_height
        self.sequence = sequence

        # ワークの境界座標
        self.xmin = center_x - width / 2.0
        self.xmax = center_x + width / 2.0
        self.ymin = center_y - length / 2.0
        self.ymax = center_y + length / 2.0
        self.zmax = layer_height * len(sequence)

        # === 調整用パラメーター ===
        self.e_factor_infill = 0.0245     # インフィル 1mmあたりの押出量
        self.e_factor_perimeter = 0.0250  # Perimeter 1mmあたりの押出量
        self.infill_pitch = 0.402         # インフィルのピッチ (元の0.804だと隙間ができるため半値に設定)
        self.fiber_cut_distance = 23.73   # 端からカット位置までの距離 (mm)
        # ==========================

    def generate(self, filename="output.gcode"):
        with open(filename, 'w') as f:
            self._write_header(f)

            for i, layer_type in enumerate(self.sequence):
                z = (i + 1) * self.layer_height
                f.write(f";========================\n")
                f.write(f"; - START OF ZCHUNK #{i+1}, range=[{z:.2f}, {z:.2f}] ({layer_type} Layer) -\n")
                f.write(f";========================\n")

                if layer_type == 'P':
                    self._write_polymer_layer(f, z, i)
                elif layer_type == 'F':
                    self._write_fiber_layer(f, z, i)

                f.write(f";========================\n")
                f.write(f"; - END OF ZCHUNK #{i+1} -\n")
                f.write(f";========================\n\n")

            self._write_footer(f)
        print(f"[{filename}] の生成が完了しました！ (総層数: {len(self.sequence)}層)")

    def _write_header(self, f):
        now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')
        header = f"""; 9Code-Version = 1.0
; Creation-Date = {now}
; Creator = CFRTP Python Generator
; Slicing-Engine = Custom Python Script
; -- Parts --
; xmin = {self.xmin:.3f}
; xmax = {self.xmax:.3f}
; ymin = {self.ymin:.3f}
; ymax = {self.ymax:.3f}
; zmin = 0.000
; zmax = {self.zmax:.3f}
; -- End Parts --

;*-- START CODE --
CLEAR_PAUSE
G21 ; set units to millimeters
G90 ; use absolute coordinates
M83 ; extruder relative mode
SET_PIN PIN=lamps VALUE=0.7

M104 S130 T0 ; set fiber extruder temperature
M140 S160 ; set bed temp
G28 ; Home all axes
M109 S130 T0 ; set fiber extruder temp
G28 W ; re-home FG after it has heated up
M190 S160 ; wait for bed temp
M104 S360 T0 ; set fiber extruder temp
M104 S285 T1 ; set 75% polymer nozzle temp
G29 ; Meshbed leveling
G0 Z3.0000 F5500
M109 S380 T1 ; wait for first layer polymer temperature
M109 S360 T0 ; wait for FG printing temperature

T1 ; change to polymer extruder
G0 X100.0000 Y3.0000 Z0.5000 F5500 ; go outside print area
G1 X60.0000 E9.0000 F1000 ; intro line
G1 X20.0000 E12.5000 F1000 ; intro line
G92 E0.0
SET_RETRACTION RETRACT_LENGTH=9.0 RETRACT_SPEED=40.0
SET_HEATER_TEMPERATURE HEATER=print_chamber target=100.0
SET_HEATER_TEMPERATURE HEATER=material_chamber target=85.0
;*-- END OF START CODE --
"""
        f.write(header)

    def _generate_45deg_infill(self, xmin, xmax, ymin, ymax, pitch, angle_deg):
        """領域を埋める45度(または-45度)のインフィル線分を計算"""
        points = []
        if angle_deg == 45:
            c_start = xmin - ymax
            c_end = xmax - ymin
        else:
            c_start = xmin + ymin
            c_end = xmax + ymax

        c = c_start
        direction = 1

        while c <= c_end + 1e-6:
            intersections = []
            if angle_deg == 45:
                y1 = xmin - c
                if ymin - 1e-6 <= y1 <= ymax + 1e-6: intersections.append((xmin, y1))
                y2 = xmax - c
                if ymin - 1e-6 <= y2 <= ymax + 1e-6: intersections.append((xmax, y2))
                x1 = ymin + c
                if xmin + 1e-6 < x1 < xmax - 1e-6: intersections.append((x1, ymin))
                x2 = ymax + c
                if xmin + 1e-6 < x2 < xmax - 1e-6: intersections.append((x2, ymax))
            else:
                y1 = c - xmin
                if ymin - 1e-6 <= y1 <= ymax + 1e-6: intersections.append((xmin, y1))
                y2 = c - xmax
                if ymin - 1e-6 <= y2 <= ymax + 1e-6: intersections.append((xmax, y2))
                x1 = c - ymin
                if xmin + 1e-6 < x1 < xmax - 1e-6: intersections.append((x1, ymin))
                x2 = c - ymax
                if xmin + 1e-6 < x2 < xmax - 1e-6: intersections.append((x2, ymax))

            unique_intersections = []
            for p in intersections:
                if not any(math.dist(p, up) < 1e-5 for up in unique_intersections):
                    unique_intersections.append(p)

            if len(unique_intersections) == 2:
                p1, p2 = unique_intersections
                if direction == 1:
                    p1, p2 = sorted([p1, p2], key=lambda p: p[0])
                else:
                    p1, p2 = sorted([p1, p2], key=lambda p: p[0], reverse=True)
                points.append((p1, p2))

            c += pitch
            direction *= -1

        return points

    def _write_polymer_layer(self, f, z, layer_idx):
        f.write(f"G0 Z{z:.4f} ; to next layer transition\n")

        # 前の層がFiberだった場合のノズル温度リカバリー
        if layer_idx > 0 and self.sequence[layer_idx-1] == 'F':
            f.write(";- START OF POLYMER STRETCH INITIALIZATION -\n")
            f.write("G10 S1\n")
            f.write("M104 S380 T1 ; set polymer nozzle temperature\n")
            f.write("SET_STATE_TARGET STATE=buffer TARGET=0\n")
            f.write("G91\nG0 Z3.0000 F5500\nG90\nM83\n")
            f.write("M109 S380 T1\nM104 S380 T1\nT1\n")
            f.write(";- END OF POLYMER STRETCH INITIALIZATION -\n")

        # 4つのPerimeterを生成 (外側から内側へ)
        inset = 2.003

        # 最初のPerimeterの開始点へ明示的に移動 (斜め線回避)
        f.write(";- START OF POLYMER STRETCH INITIALIZATION -\n")
        f.write(f"G10\nG0 Z{z + 0.8:.4f} F5500 ; lift Z\n")
        f.write(f"G0 X{self.xmin + inset:.4f} Y{self.ymax - inset:.4f}\n")
        f.write(f"G0 Z{z:.4f} ; restore layer Z\n")
        f.write("G1 F1800\nG11\n")
        f.write(";- END OF POLYMER STRETCH INITIALIZATION -\n")

        for p in range(4):
            p_xmin = self.xmin + inset
            p_xmax = self.xmax - inset
            p_ymin = self.ymin + inset
            p_ymax = self.ymax - inset

            # 2番目以降のPerimeter開始点への移動
            if p > 0:
                f.write(";- START OF POLYMER STRETCH INITIALIZATION -\n")
                f.write(f"G0 Z{z + 0.8:.4f} F5500 ; lift Z\n")
                f.write(f"G0 X{p_xmin:.4f} Y{p_ymax:.4f}\n")
                f.write(f"G0 Z{z:.4f} ; restore layer Z\n")
                f.write("G1 F1800\n")
                f.write(";- END OF POLYMER STRETCH INITIALIZATION -\n")

            f.write(f";------------------------\n; - START OF POLYMER STRETCH #{p} (Perimeter) -\n;------------------------\n")
            pts = [(p_xmin, p_ymax), (p_xmin, p_ymin), (p_xmax, p_ymin), (p_xmax, p_ymax)]
            curr_pos = pts[0]
            for nx, ny in pts[1:] + [pts[0]]:
                dist = math.dist(curr_pos, (nx, ny))
                e_val = dist * self.e_factor_perimeter
                f.write(f"G1 X{nx:.4f} Y{ny:.4f} E{e_val:.4f} ; perimeter\n")
                curr_pos = (nx, ny)
            f.write(f";------------------------\n; - END OF POLYMER STRETCH #{p} -\n;------------------------\n")

            inset -= 0.568

        # Infillのバウンディングボックス
        infill_xmin = self.xmin + 2.071
        infill_xmax = self.xmax - 2.071
        infill_ymin = self.ymin + 2.071
        infill_ymax = self.ymax - 2.071

        # 層ごとに45度と-45度を交互に生成
        angle = 45 if layer_idx % 2 == 0 else -45
        infill_lines = self._generate_45deg_infill(infill_xmin, infill_xmax, infill_ymin, infill_ymax, self.infill_pitch, angle_deg=angle)

        if infill_lines:
            start_p = infill_lines[0][0]
            f.write(";- START OF POLYMER STRETCH INITIALIZATION -\n")
            f.write(f"G10\nG0 Z{z+0.8:.4f} F5500\n")
            f.write(f"G0 X{start_p[0]:.4f} Y{start_p[1]:.4f}\n") # インフィル開始点へ明示的に移動
            f.write(f"G0 Z{z:.4f}\nG1 F3600\nG11\n")
            f.write(";- END OF POLYMER STRETCH INITIALIZATION -\n")

            f.write(f";------------------------\n; - START OF POLYMER STRETCH #4 (Infill {angle}-deg) -\n;------------------------\n")

            curr_pos = start_p
            for i, line in enumerate(infill_lines):
                # 折り返しのステップ移動
                if i > 0:
                    dist = math.dist(curr_pos, line[0])
                    if dist > 1e-4:
                        e_val = dist * self.e_factor_infill
                        f.write(f"G1 X{line[0][0]:.4f} Y{line[0][1]:.4f} E{e_val:.4f} ; infill step\n")

                # スキャン線（斜め）移動
                dist = math.dist(line[0], line[1])
                if dist > 1e-4:
                    e_val = dist * self.e_factor_infill
                    f.write(f"G1 X{line[1][0]:.4f} Y{line[1][1]:.4f} E{e_val:.4f} ; infill\n")

                curr_pos = line[1]

            f.write(f";------------------------\n; - END OF POLYMER STRETCH #4 -\n;------------------------\n")

    def _write_fiber_layer(self, f, z, layer_idx):
        f.write(f"G0 Z{z:.4f} ; to next layer transition\n")
        f.write(";- START OF Fiber STRETCH INITIALIZATION -\n")
        if layer_idx > 0 and self.sequence[layer_idx-1] == 'P':
            f.write("G10 S1\n")
            f.write("M104 S200 T1 ; cool down polymer nozzle\n")
            f.write("G10\nG91\nG0 Z3.0000 F5500\nG90\nM83\n")
            f.write("T0 ; change to fiber guide\n")
            f.write(f"SET_STATE_TARGET STATE=buffer TARGET={z:.2f}\n")
        f.write(";- END OF Fiber STRETCH INITIALIZATION -\n")

        # Fiber領域を矩形寸法内に完全一致させる
        f_xmin = self.xmin + 0.5
        f_xmax = self.xmax - 0.5
        pass_count = int(math.floor(f_xmax - f_xmin)) + 1

        y_start = self.ymin
        y_end = self.ymax

        direction = 1 # 1: Y+, -1: Y-
        current_x = f_xmin

        for p in range(pass_count):
            f.write(f";------------------------\n; - START OF Fiber STRETCH (Pass {p+1}/{pass_count}) -\n;------------------------\n")
            f.write("USE_ABSOLUTE_ROTARY_POSITION\n")

            if direction == 1:
                anchor_y = y_start - 21.3461
                cut_y = y_end - self.fiber_cut_distance  # 端から23.73mmの位置

                f.write(f"G0 X{current_x:.4f} Y{anchor_y:.4f} Z{z+3.0:.4f} W90.0000 F5500\n")
                f.write("USE_RELATIVE_ROTARY_POSITION\n")
                f.write("G0 E23.5000 F1000\n")
                f.write(f"G1 X{current_x:.4f} Y{y_start:.4f} Z{z:.4f} F1000\n")
                f.write("G4 P100 ;anchoring dwell\n")
                dist = cut_y - y_start
                f.write(f"G1 X{current_x:.4f} Y{cut_y:.4f} Z{z:.4f} E{dist*0.993:.4f} F1000\n")
                f.write("cut_filament\n")
                f.write(f"G1 X{current_x:.4f} Y{y_end:.4f} Z{z:.4f} W0.0000 F700\n") # 端まで引き切る
                f.write(f"G0 X{current_x:.4f} Y{y_end + 5.0:.4f} Z{z:.4f} W0.0000 F700 ;Ironing out move\n")
            else:
                anchor_y = y_end + 21.3461
                cut_y = y_start + self.fiber_cut_distance # 端から23.73mmの位置

                f.write(f"G0 X{current_x:.4f} Y{anchor_y:.4f} Z{z+3.0:.4f} W-90.0000 F5500\n")
                f.write("USE_RELATIVE_ROTARY_POSITION\n")
                f.write("G0 E23.5000 F1000\n")
                f.write(f"G1 X{current_x:.4f} Y{y_end:.4f} Z{z:.4f} F1000\n")
                f.write("G4 P100 ;anchoring dwell\n")
                dist = y_end - cut_y
                f.write(f"G1 X{current_x:.4f} Y{cut_y:.4f} Z{z:.4f} E{dist*0.993:.4f} F1000\n")
                f.write("cut_filament\n")
                f.write(f"G1 X{current_x:.4f} Y{y_start:.4f} Z{z:.4f} W0.0000 F700\n") # 端まで引き切る
                f.write(f"G0 X{current_x:.4f} Y{y_start - 5.0:.4f} Z{z:.4f} W0.0000 F700 ;Ironing out move\n")

            f.write(f";------------------------\n; - END OF Fiber STRETCH -\n;------------------------\n")
            current_x += 1.0
            direction *= -1

    def _write_footer(self, f):
        footer = """;*-- END CODE --
G90
M83
USE_ABSOLUTE_ROTARY_POSITION
G1 Z100.0000 W0.0000 F6000 ; move to anchoring start
USE_RELATIVE_ROTARY_POSITION
M104 S0 T0 ; turn off fiber guide
M104 S0 T1 ; turn off polymer nozzle
M140 S0 ; turn off bed
set_state_target state=buffer target=0 ; turn off buffer
set_heater_temperature heater=print_chamber target=0 ; turn off chamber heater
;*-- END OF END CODE --
"""
        f.write(footer)


if __name__ == "__main__":
    # =============== パラメーター設定 =================
    CENTER_X = 175.0        # 造形中心 X座標
    CENTER_Y = 135.0        # 造形中心 Y座標
    WIDTH = 15.0            # 試験片の幅 (mm)
    LENGTH = 200.0          # 試験片の長さ (mm)
    LAYER_HEIGHT = 0.15     # 1層あたりの厚さ (mm)

    SEQUENCE = ['P', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F']
    # =================================================

    generator = CFRTPGcodeGenerator(
        center_x=CENTER_X,
        center_y=CENTER_Y,
        width=WIDTH,
        length=LENGTH,
        layer_height=LAYER_HEIGHT,
        sequence=SEQUENCE
    )
    generator.generate("ASTM_UD_Tensile_Custom.gcode")