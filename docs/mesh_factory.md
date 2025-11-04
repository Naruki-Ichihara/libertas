# Mesh Factory - API Documentation

The `libertas.mesh_factory` module provides utilities for generating conforming meshes from topology optimization results.

## Overview

After topology optimization, you may want to create a new mesh that conforms to the optimized material distribution. The mesh factory provides three main functions:

1. `density_to_image()` - Convert FEniCS density function to numpy image array
2. `image_to_mesh()` - Generate mesh from image array via contour extraction
3. `mesh_from_density()` - Combined function (density → mesh in one call)

## Installation

The mesh factory requires additional dependencies:

```bash
pip install -e ".[mesh]"
```

This installs:
- `pygmsh` - Mesh generation
- `meshio` - Mesh I/O
- `scikit-image` - Contour extraction
- `scipy` - Interpolation and smoothing
- `pillow` - Image handling

## Functions

### `mesh_from_density()`

Generate conforming mesh directly from FEniCS density function (recommended).

**Signature:**
```python
mesh_from_density(
    density: pt.Function,
    function_space: pt.FunctionSpace,
    mesh: pt.Mesh,
    threshold: float = 0.5,
    resolution: float = 30.0,
    refinement: int = 3,
    mesh_size: float = 0.1,
    smoothing: float = 10.0,
    point_reduction: float = 0.2,
    save_path: str = None,
    mpi_comm: object = None
) -> pt.Mesh
```

**Parameters:**
- `density`: FEniCS density function from topology optimization
- `function_space`: Function space of the density function
- `mesh`: Original mesh associated with density
- `threshold`: Density threshold for material vs void (default: 0.5)
- `resolution`: Pixels per mm for contour extraction (default: 30.0)
- `refinement`: Mesh refinement level before conversion (default: 3)
- `mesh_size`: Element size for generated mesh in mm (default: 0.1)
- `smoothing`: B-spline smoothing factor (default: 10.0)
- `point_reduction`: Point reduction factor, e.g., 0.2 = keep 20% (default: 0.2)
- `save_path`: Optional path to save mesh (e.g., "mesh.xml")
- `mpi_comm`: MPI communicator (default: MPI.comm_world)

**Returns:**
- `mesh`: Generated FEniCS mesh

**Example:**
```python
import libertas as lb
from libertas.pytop import pytop as pt

# Load density
mesh = pt.Mesh("mesh.xml")
U = pt.FunctionSpace(mesh, 'CG', 1)
density = pt.read_fenics_function_from_file("density", U, "density")

# Generate conforming mesh
new_mesh = lb.mesh_from_density(
    density, U, mesh,
    threshold=0.5,
    save_path="generated_mesh.xml"
)
```

---

### `density_to_image()`

Convert FEniCS density function to regular pixel image (numpy array).

**Signature:**
```python
density_to_image(
    density: pt.Function,
    function_space: pt.FunctionSpace,
    mesh: pt.Mesh,
    resolution: float = 30.0,
    refinement: int = 0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]
```

**Parameters:**
- `density`: FEniCS density function
- `function_space`: Function space of the density
- `mesh`: Mesh associated with density
- `resolution`: Pixels per mm (default: 30.0)
- `refinement`: Number of mesh refinement iterations (default: 0)

**Returns:**
- `density_image`: 2D numpy array, shape (ny, nx)
- `x_grid`: X coordinates of pixel centers, shape (nx,)
- `y_grid`: Y coordinates of pixel centers, shape (ny,)

**Example:**
```python
# Convert to image
img, x, y = lb.density_to_image(density, U, mesh, resolution=30)

# Visualize with matplotlib
import matplotlib.pyplot as plt
plt.imshow(img, cmap='gray', extent=[x[0], x[-1], y[0], y[-1]])
plt.colorbar()
plt.show()
```

---

### `image_to_mesh()`

Generate conforming mesh from density image via contour extraction.

**Signature:**
```python
image_to_mesh(
    density_image: np.ndarray,
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    threshold: float = 0.5,
    mesh_size: float = 0.1,
    smoothing: float = 10.0,
    point_reduction: float = 0.2,
    padding: int = 1,
    mpi_comm: object = None
) -> pt.Mesh
```

**Parameters:**
- `density_image`: 2D density image from `density_to_image()`
- `x_grid`: X coordinates of pixel centers
- `y_grid`: Y coordinates of pixel centers
- `threshold`: Density threshold (default: 0.5)
- `mesh_size`: Element size in mm (default: 0.1)
- `smoothing`: B-spline smoothing factor (default: 10.0)
- `point_reduction`: Point reduction factor (default: 0.2)
- `padding`: Zero-padding width in pixels (default: 1)
- `mpi_comm`: MPI communicator

**Returns:**
- `mesh`: Generated FEniCS mesh

**Example:**
```python
# Two-step process
img, x, y = lb.density_to_image(density, U, mesh)
new_mesh = lb.image_to_mesh(img, x, y, threshold=0.5, mesh_size=0.1)
```

---

## Usage Examples

### Basic Usage

```python
import libertas as lb
from libertas.pytop import pytop as pt

# Load optimization results
mesh = pt.Mesh("output/mesh.xml")
U = pt.FunctionSpace(mesh, 'CG', 1)
density = pt.read_fenics_function_from_file(
    "output/xml/density", U, "density"
)

# Generate mesh (one function call)
new_mesh = lb.mesh_from_density(
    density, U, mesh,
    threshold=0.5,
    save_path="output/generated_mesh.xml"
)
```

### Custom Quality Settings

```python
# Fast/coarse mesh (quick preview)
coarse = lb.mesh_from_density(
    density, U, mesh,
    resolution=10,      # Low resolution
    refinement=1,       # Minimal refinement
    mesh_size=0.2,      # Larger elements
    smoothing=5.0,
    point_reduction=0.3
)

# High quality mesh (production)
fine = lb.mesh_from_density(
    density, U, mesh,
    resolution=50,      # High resolution
    refinement=4,       # More refinement
    mesh_size=0.05,     # Smaller elements
    smoothing=15.0,
    point_reduction=0.1
)
```

### Image Processing Workflow

```python
# Convert to image for custom processing
img, x, y = lb.density_to_image(density, U, mesh, resolution=30)

# Apply custom image processing (e.g., filtering, morphology)
import scipy.ndimage as ndi
smoothed_img = ndi.gaussian_filter(img, sigma=2)

# Generate mesh from processed image
new_mesh = lb.image_to_mesh(
    smoothed_img, x, y,
    threshold=0.5,
    mesh_size=0.1
)
```

### Integration with Geometry Class

```python
# Create Geometry object from generated mesh
geometry = lb.Geometry.from_fenics(new_mesh)

# Use in topology optimization workflow
problem = lb.TopologyOptimization(
    geometry=geometry,
    material=material,
    boundaries=bcs
)
```

## Parameter Guide

### Resolution
Controls pixel density for contour extraction:
- **10-20**: Fast, coarse contours
- **30-50**: Good balance (recommended)
- **100+**: Very fine, slow

### Threshold
Controls material/void boundary:
- **0.3-0.4**: More material
- **0.5**: Balanced (recommended)
- **0.6-0.7**: Less material

### Refinement
Number of mesh refinement iterations:
- **0-1**: Fast, coarse
- **2-3**: Good quality (recommended)
- **4+**: Very fine, slow

### Mesh Size
Element size for generated mesh (mm):
- **0.2+**: Coarse mesh, fast
- **0.05-0.1**: Good balance (recommended)
- **<0.05**: Very fine, slow

### Smoothing
B-spline smoothing factor:
- **0**: No smoothing (pixelated)
- **5-10**: Slight smoothing
- **10-20**: Moderate (recommended)
- **50+**: Heavy smoothing (may lose detail)

### Point Reduction
Fraction of points to keep:
- **None**: No reduction
- **0.1-0.3**: Significant reduction (recommended)
- **0.5+**: May lose detail

## Error Handling

```python
try:
    new_mesh = lb.mesh_from_density(density, U, mesh)
except ValueError as e:
    # No contours found - try adjusting threshold
    print(f"Error: {e}")
    new_mesh = lb.mesh_from_density(
        density, U, mesh,
        threshold=0.3  # Lower threshold
    )
except ImportError as e:
    # Missing dependencies
    print("Install mesh dependencies: pip install -e '.[mesh]'")
```

## See Also

- [Geometry API](geometry.md) - Mesh and geometry handling
- [Workflow Guide](../WORKFLOW.md) - Complete optimization workflow
- [Examples](../examples/) - Complete working examples
