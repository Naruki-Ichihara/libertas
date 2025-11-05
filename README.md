# Libertas

3Dプリンティングのためのトポロジー最適化ライブラリ - fullcontrolの拡張版

## 概要

Libertasは、構造最適化と無制約な設計を組み合わせた3Dプリンティング用のPythonライブラリです。有限要素法（FEM）ベースのトポロジー最適化を実行し、最適化された形状から直接3DプリンタのGコードを生成できます。

### 主な機能

- **トポロジー最適化**: FEniCSベースの有限要素解析
- **材料サポート**: 等方性・異方性材料の両方に対応
- **メッシュ生成**: 最適化結果から適合メッシュを自動生成
- **GCode生成**: 最適化された形状から直接3Dプリンタ用のGコードを生成
- **視覚化**: 最適化プロセスと結果の可視化ツール

## インストール

### 基本インストール

```bash
pip install -e .
```

### オプション機能付きインストール

```bash
# 開発ツール
pip install -e ".[dev]"

# メッシュ生成機能
pip install -e ".[mesh]"

# 視覚化機能
pip install -e ".[viz]"

# 全ての機能
pip install -e ".[dev,mesh,viz]"
```

### 必要な依存関係

- Python >= 3.10
- NumPy
- Pandas
- Plotly
- Pydantic

## 使い方

### 基本的なワークフロー

Libertasでのトポロジー最適化は以下の4つのステップで構成されます：

#### 1. ジオメトリの定義

```python
import libertas as lb
import pygmsh

# メッシュの生成
with pygmsh.geo.Geometry() as geom:
    geom.add_polygon([
        [0., 0.],
        [15., 0.],
        [15., 5.],
        [0., 5.]
    ], mesh_size=0.1)
    mesh_data = geom.generate_mesh()

# Geometryオブジェクトの作成
geometry = lb.Geometry.from_pygmsh(
    mesh_data,
    save_path="output/mesh.xml"
)
```

#### 2. 境界条件の設定

```python
# 境界条件の作成
bcs = lb.BoundaryConditions(geometry)

# 左端を固定
bcs.fix_x(x=0.0)
bcs.fix_y(x=0.0)

# 荷重を適用
bcs.apply_load(
    selector=lambda x, y: x > 14.8 and y < 0.01,
    force=(0, -1),  # 下向きの力
    marker=1
)
```

#### 3. 材料の定義

```python
# 異方性材料
material = lb.OrthotropicMaterial(
    E1=6.158e3,  # 第1方向のヤング率
    E2=2.845e3,  # 第2方向のヤング率
    G12=741,     # せん断弾性係数
    nu12=0.22,   # ポアソン比
    name="複合材料"
)
```

#### 4. 最適化の実行

```python
# 最適化問題の設定
problem = lb.TopologyOptimization(
    geometry=geometry,
    material=material,
    boundaries=bcs,
    target_density=0.60,              # 目標材料密度
    penalty_exponent=3,                # SIMP法のペナルティ指数
    filter_radius_density=0.4,         # 密度フィルタ半径
    filter_radius_orientation=0.2,     # 配向フィルタ半径
    output_dir="output/example"
)

# 最適化の実行
result = problem.optimize(
    algorithm="MMA",        # MMA（移動漸近線法）
    max_iterations=200,     # 最大反復回数
    tolerance=1e-5,         # 収束判定基準
    density_initial=0.60    # 初期密度
)

# 結果の表示
result.summary()
result.plot_convergence()
```

### 完全なサンプルコード

```python
import libertas as lb
import pygmsh

# ジオメトリパラメータ
L = 15  # 長さ (mm)
H = 5   # 高さ (mm)

# メッシュ生成
with pygmsh.geo.Geometry() as geom:
    geom.add_polygon([
        [0., 0.], [L, 0.], [L, H], [0., H]
    ], mesh_size=0.1)
    mesh_data = geom.generate_mesh()

geometry = lb.Geometry.from_pygmsh(mesh_data)

# 境界条件
bcs = lb.BoundaryConditions(geometry)
bcs.fix_x(x=0.0)
bcs.fix_y(x=0.0)
bcs.apply_load(
    selector=lambda x, y: x > L-0.2 and y < 0.01,
    force=(0, -1),
    marker=1
)

# 材料定義
material = lb.OrthotropicMaterial(
    E1=6.158e3, E2=2.845e3, G12=741, nu12=0.22
)

# 最適化
problem = lb.TopologyOptimization(
    geometry=geometry,
    material=material,
    boundaries=bcs,
    target_density=0.60,
    output_dir="output"
)

result = problem.optimize(
    algorithm="MMA",
    max_iterations=200,
    tolerance=1e-5
)

# 結果の可視化
result.summary()
result.plot_convergence()
```

## 高度な機能

### メッシュ抽出

最適化結果から適合メッシュを生成：

```python
# 最適化結果からメッシュを抽出
mesh_data = result.extract_mesh(
    threshold=0.5,      # 密度しきい値
    max_area=0.1,       # 最大三角形面積
    min_angle=25.0,     # 最小角度制約
    smoothness=0.02     # ベジェ曲線の滑らかさ
)
```

または、直接FEniCSメッシュから生成（オプションの`mesh`依存関係が必要）：

```python
# FEniCS密度関数から直接メッシュ生成
from libertas.pytop import pytop as pt

mesh = pt.Mesh("output/mesh.xml")
U = pt.FunctionSpace(mesh, 'CG', 1)
density = pt.read_fenics_function_from_file(
    "output/xml/density", U, "density"
)

new_mesh = lb.mesh_from_density(
    density, U, mesh,
    threshold=0.5,
    resolution=30.0,
    save_path="output/generated_mesh.xml"
)
```

詳細は[メッシュファクトリAPIドキュメント](docs/mesh_factory.md)を参照してください。

### GCode生成

最適化された形状からGコードを生成：

```python
# SVGから3DプリンタのGコードを生成
from libertas import svg_to_gcode, PrintParams

# プリンタパラメータの設定
params = PrintParams(
    nozzle_temp=210,
    bed_temp=60,
    layer_height=0.2,
    nozzle_diameter=0.4
)

# GCode生成
gcode = svg_to_gcode(
    "output/contour.svg",
    params=params,
    layer_count=10
)

# ファイルに保存
with open("output.gcode", "w") as f:
    f.write(gcode)
```

## プロジェクト構成

```
libertas/
├── libertas/           # メインパッケージ
│   ├── geometry.py     # ジオメトリ管理
│   ├── boundaries.py   # 境界条件
│   ├── materials.py    # 材料定義
│   ├── problem.py      # 最適化問題
│   ├── postprocess.py  # 後処理ツール
│   ├── gcode.py        # GCode生成
│   ├── path.py         # パス管理
│   ├── layer.py        # レイヤー管理
│   ├── model.py        # 3Dモデル
│   └── pytop/          # FEniCSラッパー
├── examples/           # サンプルコード
├── tests/              # テスト
└── docs/               # ドキュメント
```

## サンプル

`examples/`ディレクトリに実用的なサンプルが含まれています：

- `example_libertas.py` - 基本的なトポロジー最適化
- `simple_xml_to_gcode.py` - メッシュからGCode生成
- `test_layer_to_csv.py` - レイヤーデータの処理

## ドキュメント

詳細なAPIドキュメントは`docs/`ディレクトリにあります：

- [メッシュファクトリAPI](docs/mesh_factory.md) - 最適化結果からのメッシュ生成

## 開発

### テストの実行

```bash
pytest
```

### コードフォーマット

```bash
black libertas
ruff check libertas
```

### 型チェック

```bash
mypy libertas
```

## ライセンス

このプロジェクトはGPL-3.0-or-laterライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 貢献

Issue、Pull Request、フィードバックを歓迎します！

## リポジトリ

- Homepage: https://github.com/Naruki-Ichihara/libertas
- Issues: https://github.com/Naruki-Ichihara/libertas/issues

## 関連技術

- **FEniCS**: 有限要素解析
- **pygmsh**: メッシュ生成
- **fullcontrol**: 3Dプリンティング制御
- **MMA**: 移動漸近線法（最適化アルゴリズム）
