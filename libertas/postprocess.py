"""Postprocessing utilities for libertas optimization results."""

from typing import Optional, Tuple, List, Dict
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET

try:
    import pytop as pt
except ImportError:
    pt = None


def read_density_from_xml(
    xml_dir: str,
    resolution: Optional[Tuple[int, int]] = None,
    interpolation: str = "linear"
) -> Tuple[np.ndarray, dict]:
    """
    Read density field from XML files and convert to numpy image array.

    This function requires FEniCS (pytop) to properly map DOF indices to vertices.
    For a FEniCS-free alternative, the DOF-to-vertex mapping would need to be
    reconstructed from the mesh connectivity, which is complex for CG elements.

    Args:
        xml_dir: Directory containing mesh.xml and density.xml
        resolution: Target resolution (width, height) for output image.
                   If None, uses mesh resolution.
        interpolation: Interpolation method - "linear" or "nearest"

    Returns:
        Tuple of (density_image, metadata)
        - density_image: 2D numpy array with density values [0, 1]
        - metadata: Dictionary with mesh bounds, resolution, etc.

    Example:
        >>> density_img, meta = read_density_from_xml("output/example_libertas/xml")
        >>> print(f"Shape: {density_img.shape}, Range: [{density_img.min():.3f}, {density_img.max():.3f}]")

    Note:
        This function requires FEniCS/pytop to be installed for correct DOF mapping.
    """
    if pt is None:
        raise ImportError(
            "FEniCS (pytop) is required for read_density_from_xml(). "
            "The DOF-to-vertex mapping requires FEniCS function space information."
        )

    xml_dir = Path(xml_dir)
    mesh_file = xml_dir / "mesh.xml"
    density_file = xml_dir / "density.xml"

    if not mesh_file.exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_file}")
    if not density_file.exists():
        raise FileNotFoundError(f"Density file not found: {density_file}")

    # Load mesh using FEniCS
    mesh = pt.Mesh(str(mesh_file))

    # Create function space (CG1 - continuous Galerkin degree 1)
    V = pt.FunctionSpace(mesh, "CG", 1)

    # Load density function
    density_func = pt.Function(V)
    density_input = pt.File(str(density_file))
    density_input >> density_func

    # Get density values at vertices (this properly handles DOF-to-vertex mapping)
    densities = density_func.compute_vertex_values(mesh)

    # Get vertex coordinates
    coords = mesh.coordinates()

    # Get mesh bounds
    x_min, y_min = coords.min(axis=0)
    x_max, y_max = coords.max(axis=0)

    # Determine resolution
    if resolution is None:
        # Estimate resolution from mesh density
        x_unique = np.unique(coords[:, 0])
        y_unique = np.unique(coords[:, 1])
        resolution = (len(x_unique), len(y_unique))

    width, height = resolution

    # Create regular grid
    x_grid = np.linspace(x_min, x_max, width)
    y_grid = np.linspace(y_min, y_max, height)
    X, Y = np.meshgrid(x_grid, y_grid)

    # Interpolate density values onto regular grid
    if interpolation == "linear":
        from scipy.interpolate import griddata

        density_image = griddata(
            coords, densities, (X, Y), method="linear", fill_value=0.0
        )
    elif interpolation == "nearest":
        from scipy.interpolate import griddata

        density_image = griddata(
            coords, densities, (X, Y), method="nearest", fill_value=0.0
        )
    else:
        raise ValueError(f"Unknown interpolation method: {interpolation}")

    # Flip so that row 0 corresponds to y_max (top of domain),
    # matching the standard image convention expected by extract_contour_svg.
    density_image = np.flipud(density_image)

    # Prepare metadata
    metadata = {
        "bounds": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "resolution": resolution,
        "num_vertices": mesh.num_vertices(),
        "num_cells": mesh.num_cells(),
        "density_range": (float(densities.min()), float(densities.max())),
        "interpolation": interpolation,
    }

    return density_image, metadata


def read_density_from_xml_fenics(xml_dir: str) -> Tuple[np.ndarray, dict]:
    """
    Read density field using FEniCS directly (requires FEniCS installation).

    This method uses FEniCS to load the mesh and function, providing
    more accurate interpolation for visualization.

    Args:
        xml_dir: Directory containing mesh.xml and density.xml

    Returns:
        Tuple of (density_array, metadata)
        - density_array: 1D array of density values at mesh vertices
        - metadata: Dictionary with mesh information

    Note:
        This function requires FEniCS (pytop) to be installed.
    """
    if pt is None:
        raise ImportError(
            "FEniCS (pytop) is required for this function. "
            "Use read_density_from_xml() for a FEniCS-free alternative."
        )

    xml_dir = Path(xml_dir)
    mesh_file = xml_dir / "mesh.xml"
    density_file = xml_dir / "density.xml"

    # Load mesh
    mesh = pt.Mesh(str(mesh_file))

    # Create function space
    V = pt.FunctionSpace(mesh, "CG", 1)

    # Load density function
    density_func = pt.Function(V)
    density_input = pt.File(str(density_file))
    density_input >> density_func

    # Get vertex values
    density_array = density_func.compute_vertex_values(mesh)

    # Get mesh coordinates
    coords = mesh.coordinates()

    # Metadata
    metadata = {
        "num_vertices": mesh.num_vertices(),
        "num_cells": mesh.num_cells(),
        "bounds": {
            "x_min": float(coords[:, 0].min()),
            "x_max": float(coords[:, 0].max()),
            "y_min": float(coords[:, 1].min()),
            "y_max": float(coords[:, 1].max()),
        },
        "density_range": (float(density_array.min()), float(density_array.max())),
    }

    return density_array, metadata


def plot_density(
    density_image: np.ndarray,
    metadata: Optional[dict] = None,
    cmap: str = "gray",
    save_path: Optional[str] = None,
    show: bool = True,
    figsize: Tuple[int, int] = (12, 4),
    title: str = "Density Distribution"
) -> None:
    """
    Plot density image using matplotlib.

    Args:
        density_image: 2D numpy array with density values
        metadata: Optional metadata dictionary from read_density_from_xml
        cmap: Colormap name (default: "gray")
        save_path: If provided, save figure to this path
        show: Whether to display the figure
        figsize: Figure size (width, height)
        title: Plot title

    Example:
        >>> density_img, meta = read_density_from_xml("output/example_libertas/xml")
        >>> plot_density(density_img, meta, save_path="density.png")
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for plotting. Install with: pip install matplotlib")

    _, ax = plt.subplots(figsize=figsize)

    if metadata and "bounds" in metadata:
        bounds = metadata["bounds"]
        extent = [bounds["x_min"], bounds["x_max"], bounds["y_min"], bounds["y_max"]]
        im = ax.imshow(density_image, cmap=cmap, origin="lower", extent=extent, vmin=0, vmax=1)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
    else:
        im = ax.imshow(density_image, cmap=cmap, origin="upper", vmin=0, vmax=1)
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")

    ax.set_title(title)
    ax.set_aspect("equal")

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Density", rotation=270, labelpad=15)

    # Add metadata text if available
    if metadata:
        info_text = f"Resolution: {metadata.get('resolution', 'N/A')}\n"
        info_text += f"Vertices: {metadata.get('num_vertices', 'N/A')}\n"
        density_range = metadata.get('density_range', (0, 0))
        info_text += f"Range: [{density_range[0]:.2e}, {density_range[1]:.2e}]"
        ax.text(
            1.15,
            0.5,
            info_text,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="center",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Figure saved to: {save_path}")

    if show:
        plt.show()
    else:
        plt.close()


def save_density_image(
    density_image: np.ndarray, output_path: str, normalize: bool = True
) -> None:
    """
    Save density image as PNG file.

    Args:
        density_image: 2D numpy array with density values
        output_path: Output file path (e.g., "density.png")
        normalize: Whether to normalize values to [0, 255] range

    Example:
        >>> density_img, _ = read_density_from_xml("output/example_libertas/xml")
        >>> save_density_image(density_img, "density.png")
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required for saving images. Install with: pip install Pillow")

    # Flip vertically since PIL/image coordinates have origin at top-left
    # but our density_image has origin at bottom-left (matching physical coordinates)
    img_data = np.flipud(density_image)

    if normalize:
        # Normalize to 0-255 range
        img_data = ((img_data - img_data.min()) /
                    (img_data.max() - img_data.min() + 1e-10) * 255)
    else:
        img_data = np.clip(img_data * 255, 0, 255)

    img_data = img_data.astype(np.uint8)
    img = Image.fromarray(img_data, mode="L")
    img.save(output_path)
    print(f"Image saved to: {output_path}")


def extract_contour_svg(
    density_image: np.ndarray,
    metadata: dict,
    output_path: str,
    threshold: float = 0.5,
    smoothness: float = 0.01,
    fill_color: str = "#000000",
    invert: bool = False,
    corner_angle: float = 140.0
) -> None:
    """
    Extract contour lines from density field and save as SVG with smooth Bézier curves.

    Uses connected component labeling (pixel binding) to detect closed regions
    where density is above/below threshold. Outputs smooth contour outlines as SVG paths
    using cubic Bézier curves while preserving sharp corners.

    Args:
        density_image: 2D numpy array with density values from read_density_from_xml
        metadata: Metadata dictionary from read_density_from_xml (contains bounds)
        output_path: Output SVG file path (e.g., "contour.svg")
        threshold: Density threshold value (default: 0.5)
        smoothness: Bézier smoothness parameter (0.01-0.1, smaller = smoother)
                   Represents fraction of contour length per Bézier segment.
                   Use 0 for polyline output (no smoothing).
        fill_color: Stroke color for contour lines (default: black)
        invert: If True, extract regions where density < threshold instead
        corner_angle: Corner detection threshold in degrees (default: 140°)
                     Angles sharper than this are preserved as corners.
                     Smaller values = more corners preserved (e.g., 120° for very sharp only)

    Example:
        >>> density_img, meta = read_density_from_xml("output/example_libertas/xml")
        >>> # Extract smooth contours with sharp corners preserved
        >>> extract_contour_svg(density_img, meta, "contour.svg", threshold=0.5,
        ...                     smoothness=0.02, corner_angle=140.0)
        >>> # Extract contours of void regions where density < 0.5
        >>> extract_contour_svg(density_img, meta, "void_contour.svg", threshold=0.5, invert=True)
    """
    try:
        from skimage import measure
        from scipy import ndimage
    except ImportError:
        raise ImportError(
            "scikit-image and scipy are required for contour extraction. "
            "Install with: pip install scikit-image scipy"
        )

    # Get bounds from metadata
    if "bounds" not in metadata:
        raise ValueError("Metadata must contain 'bounds' information")

    bounds = metadata["bounds"]
    x_min, x_max = bounds["x_min"], bounds["x_max"]
    y_min, y_max = bounds["y_min"], bounds["y_max"]

    height, width = density_image.shape

    # Create binary mask
    if invert:
        binary_mask = (density_image < threshold).astype(np.uint8)
        pad_value = 1  # Pad with 1 (solid) to close void regions at boundary
    else:
        binary_mask = (density_image > threshold).astype(np.uint8)
        pad_value = 0  # Pad with 0 (void) to close solid regions at boundary

    # Add 1-pixel border with inverse value to properly close boundary regions
    # This ensures regions touching the boundary form closed contours
    padded_mask = np.pad(binary_mask, pad_width=1, mode='constant', constant_values=pad_value)

    # Label connected components to identify separate closed regions
    labeled_mask, num_features = ndimage.label(padded_mask)

    # Find contours for each connected component
    contours = []
    for label_id in range(1, num_features + 1):
        component_mask = (labeled_mask == label_id).astype(float)
        component_contours = measure.find_contours(component_mask, 0.5)
        contours.extend(component_contours)

    # Build SVG content
    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{x_max - x_min:.6f}" height="{y_max - y_min:.6f}" '
        f'viewBox="{x_min:.6f} {y_min:.6f} {x_max - x_min:.6f} {y_max - y_min:.6f}">'
    )

    # Add description
    comparison = "<" if invert else ">"
    svg_lines.append(f'  <desc>Solid regions where density {comparison} {threshold}</desc>')

    # Create group for contour outlines (stroke only, no fill)
    svg_lines.append(f'  <g id="solid_regions" fill="none" stroke="{fill_color}" stroke-width="0.05">')

    # Convert contours to physical coordinates and create SVG paths
    num_paths = 0
    for contour in contours:
        if len(contour) < 3:
            continue

        # Adjust contour coordinates to account for padding (subtract 1 pixel offset)
        adjusted_contour = contour - 1.0

        # Convert from image coordinates (row, col) to physical coordinates (x, y)
        # contour is (N, 2) array where contour[:, 0] is row (y) and contour[:, 1] is col (x)
        # Image coordinates: row 0 at top, row -1 at bottom
        # Physical coordinates: y_min at bottom, y_max at top
        # Therefore, need to flip Y: physical_y = y_max - (row/height) * (y_max - y_min)
        physical_x = x_min + (adjusted_contour[:, 1] / width) * (x_max - x_min)
        physical_y = y_max - (adjusted_contour[:, 0] / height) * (y_max - y_min)

        # Clip to domain boundaries to handle padding effects
        physical_x = np.clip(physical_x, x_min, x_max)
        physical_y = np.clip(physical_y, y_min, y_max)

        vertices = np.column_stack([physical_x, physical_y])

        # Snap boundary-to-interior transitions to the domain edge.
        #
        # Gaussian smoothing causes the density to decay gradually near
        # boundary endpoints, so the iso-contour peels away from the
        # domain edge over several pixels instead of turning sharply.
        # We fix this by detecting every transition where the contour
        # leaves (or arrives at) a domain boundary edge and projecting
        # the first interior point onto that edge.  This replaces the
        # gradual curve with a sharp right-angle corner.
        #
        # We also insert missing domain corner vertices when the contour
        # moves from one boundary edge to another (e.g. left -> top).
        bnd_tol = (x_max - x_min) / width * 2  # ~2 pixels in physical coords

        def _on_edge(pt):
            """Return set of boundary edge names the point lies on."""
            edges = set()
            if abs(pt[0] - x_min) < bnd_tol:
                edges.add("left")
            if abs(pt[0] - x_max) < bnd_tol:
                edges.add("right")
            if abs(pt[1] - y_min) < bnd_tol:
                edges.add("bottom")
            if abs(pt[1] - y_max) < bnd_tol:
                edges.add("top")
            return edges

        def _snap_to_edge(pt, edge):
            """Project *pt* onto the named boundary edge."""
            snapped = pt.copy()
            if edge == "left":
                snapped[0] = x_min
            elif edge == "right":
                snapped[0] = x_max
            elif edge == "bottom":
                snapped[1] = y_min
            elif edge == "top":
                snapped[1] = y_max
            return snapped

        _domain_corner = {
            frozenset(("left",  "bottom")): np.array([x_min, y_min]),
            frozenset(("left",  "top")):    np.array([x_min, y_max]),
            frozenset(("right", "bottom")): np.array([x_max, y_min]),
            frozenset(("right", "top")):    np.array([x_max, y_max]),
        }

        new_vertices = [vertices[0]]
        for i in range(1, len(vertices)):
            prev_edges = _on_edge(vertices[i - 1])
            curr_edges = _on_edge(vertices[i])

            # Case 1: boundary -> interior  (contour leaves the edge)
            # Snap the first interior point onto the edge so the corner
            # is sharp instead of rounded.
            if prev_edges and not curr_edges:
                for edge in prev_edges:
                    snapped = _snap_to_edge(vertices[i], edge)
                    if np.linalg.norm(snapped - vertices[i - 1]) > bnd_tol:
                        new_vertices.append(snapped)
                        break  # one snap is enough

            # Case 2: interior -> boundary  (contour arrives at the edge)
            # Snap the last interior point onto the edge.
            elif not prev_edges and curr_edges:
                for edge in curr_edges:
                    snapped = _snap_to_edge(vertices[i - 1], edge)
                    if np.linalg.norm(snapped - vertices[i]) > bnd_tol:
                        new_vertices.append(snapped)
                        break

            # Case 3: boundary -> different boundary  (domain corner)
            elif prev_edges and curr_edges and prev_edges != curr_edges:
                key = frozenset(prev_edges | curr_edges)
                corner = _domain_corner.get(key)
                if corner is not None:
                    if (np.linalg.norm(vertices[i - 1] - corner) > bnd_tol and
                            np.linalg.norm(vertices[i] - corner) > bnd_tol):
                        new_vertices.append(corner)

            new_vertices.append(vertices[i])
        vertices = np.array(new_vertices)

        if len(vertices) < 3:
            continue

        # Build SVG path using Bézier curves or polyline
        if smoothness > 0:
            # Fit Bézier curves to the contour with corner preservation
            bezier_curves = path_to_bezier_segments(
                vertices,
                smoothness=smoothness,
                corner_angle_threshold=corner_angle
            )
            if not bezier_curves:
                continue
            path_data = bezier_segments_to_svg_path(bezier_curves, close_path=True)
        else:
            # Use simple polyline (no smoothing)
            path_data = f"M {vertices[0, 0]:.6f},{vertices[0, 1]:.6f}"
            for i in range(1, len(vertices)):
                path_data += f" L {vertices[i, 0]:.6f},{vertices[i, 1]:.6f}"
            path_data += " Z"  # Close path

        svg_lines.append(f'    <path d="{path_data}"/>')
        num_paths += 1

    svg_lines.append('  </g>')
    svg_lines.append('</svg>')

    # Write SVG file
    svg_content = '\n'.join(svg_lines)
    with open(output_path, 'w') as f:
        f.write(svg_content)

    print(f"SVG solid region saved to: {output_path}")
    print(f"  Threshold: {threshold} ({'<' if invert else '>'})")
    print(f"  Bounds: x=[{x_min:.2f}, {x_max:.2f}], y=[{y_min:.2f}, {y_max:.2f}]")
    print(f"  Number of closed regions: {num_paths}")


def fit_bezier_curve_segment(points: np.ndarray) -> tuple:
    """
    Fit a cubic Bézier curve to a sequence of points.

    Uses a simple heuristic: control points are placed at 1/3 and 2/3 along
    the tangent directions at the start and end points.

    Args:
        points: Nx2 array of path vertices to fit

    Returns:
        (P0, P1, P2, P3) - Four control points for cubic Bézier curve
    """
    if len(points) < 2:
        raise ValueError("Need at least 2 points to fit Bézier curve")

    P0 = points[0]  # Start point
    P3 = points[-1]  # End point

    if len(points) == 2:
        # Simple linear interpolation for control points
        P1 = P0 + (P3 - P0) / 3
        P2 = P0 + 2 * (P3 - P0) / 3
        return P0, P1, P2, P3

    # Estimate tangent at start using first few points
    tangent_start = points[min(2, len(points)-1)] - points[0]
    tangent_start = tangent_start / (np.linalg.norm(tangent_start) + 1e-10)

    # Estimate tangent at end using last few points
    tangent_end = points[-1] - points[max(0, len(points)-3)]
    tangent_end = tangent_end / (np.linalg.norm(tangent_end) + 1e-10)

    # Place control points along tangents
    chord_length = np.linalg.norm(P3 - P0)
    alpha = chord_length * 0.33  # Control point distance scaling

    P1 = P0 + alpha * tangent_start
    P2 = P3 - alpha * tangent_end

    return P0, P1, P2, P3


def detect_corners(points: np.ndarray, angle_threshold: float = 140.0) -> np.ndarray:
    """
    Detect corner points in a path based on angle changes.

    Args:
        points: Nx2 array of path vertices
        angle_threshold: Maximum angle in degrees to be considered a corner (default: 140°)
                        Smaller values = more corners detected

    Returns:
        Boolean array indicating which points are corners
    """
    n = len(points)
    if n < 3:
        return np.zeros(n, dtype=bool)

    is_corner = np.zeros(n, dtype=bool)

    # For closed paths, check all points including wrap-around
    for i in range(n):
        # Get previous, current, and next points (with wrap-around)
        prev_pt = points[(i - 1) % n]
        curr_pt = points[i]
        next_pt = points[(i + 1) % n]

        # Calculate vectors
        v1 = prev_pt - curr_pt
        v2 = next_pt - curr_pt

        # Calculate angle between vectors
        v1_norm = np.linalg.norm(v1)
        v2_norm = np.linalg.norm(v2)

        if v1_norm < 1e-10 or v2_norm < 1e-10:
            continue

        cos_angle = np.dot(v1, v2) / (v1_norm * v2_norm)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle_deg = np.degrees(np.arccos(cos_angle))

        # Mark as corner if angle is less than threshold
        if angle_deg < angle_threshold:
            is_corner[i] = True

    return is_corner


def path_to_bezier_segments(points: np.ndarray, smoothness: float = 0.01,
                            corner_angle_threshold: float = 140.0) -> list:
    """
    Convert a path to a series of cubic Bézier curve segments with sharp corners preserved.

    Args:
        points: Nx2 array of path vertices
        smoothness: Controls segment length (smaller = more segments, smoother)
                   Represents fraction of total path length per segment
        corner_angle_threshold: Angle threshold for corner detection in degrees (default: 140°)
                               Smaller values = more corners preserved

    Returns:
        List of (P0, P1, P2, P3) tuples, each defining a cubic Bézier curve
    """
    if len(points) < 2:
        return []

    # Check if path is closed
    is_closed = np.allclose(points[0], points[-1], atol=1e-6)
    if is_closed:
        points = points[:-1]  # Remove duplicate closing point

    if len(points) < 2:
        return []

    # Detect corners in the path
    is_corner = detect_corners(points, angle_threshold=corner_angle_threshold)

    # Find indices of corner points
    corner_indices = np.where(is_corner)[0]

    # If no corners detected or very few points, fall back to simple segmentation
    if len(corner_indices) == 0:
        # Use simple arc-length based segmentation
        return _bezier_segments_simple(points, smoothness, is_closed)

    # Split path at corners and fit Bézier curves to each segment
    bezier_curves = []

    # Add start point if not a corner
    if not is_corner[0]:
        split_points = [0]
    else:
        split_points = []

    # Add all corner points
    split_points.extend(corner_indices.tolist())

    # Add end point for closed paths
    if is_closed:
        split_points.append(len(points))
    else:
        if not is_corner[-1]:
            split_points.append(len(points))

    # Ensure unique and sorted
    split_points = sorted(set(split_points))

    # Fit Bézier curves between split points
    for i in range(len(split_points)):
        start_idx = split_points[i]
        end_idx = split_points[(i + 1) % len(split_points)] if is_closed else (
            split_points[i + 1] if i + 1 < len(split_points) else len(points)
        )

        if is_closed and end_idx <= start_idx:
            # Wrap around for closed paths
            segment_points = np.vstack([points[start_idx:], points[:end_idx+1]])
        else:
            segment_points = points[start_idx:end_idx+1]

        if len(segment_points) >= 2:
            # For corner-to-corner segments, subdivide if needed based on smoothness
            segment_length = np.sum(np.linalg.norm(np.diff(segment_points, axis=0), axis=1))
            target_length = segment_length * smoothness
            num_subsegments = max(1, int(np.ceil(segment_length / target_length)))

            if num_subsegments == 1:
                bezier_curves.append(fit_bezier_curve_segment(segment_points))
            else:
                # Subdivide this segment
                subseg_beziers = _bezier_segments_simple(segment_points, smoothness, False)
                bezier_curves.extend(subseg_beziers)

        if not is_closed and i + 1 >= len(split_points):
            break

    return bezier_curves


def _bezier_segments_simple(points: np.ndarray, smoothness: float, is_closed: bool) -> list:
    """
    Simple arc-length based Bézier segmentation without corner detection.

    Args:
        points: Nx2 array of path vertices
        smoothness: Smoothness parameter
        is_closed: Whether the path is closed

    Returns:
        List of Bézier curve tuples
    """
    # Calculate cumulative arc length
    segments = np.diff(points, axis=0)
    segment_lengths = np.linalg.norm(segments, axis=1)
    cumulative_length = np.concatenate([[0], np.cumsum(segment_lengths)])
    total_length = cumulative_length[-1]

    if total_length < 1e-10:
        return []

    # Determine number of Bézier segments based on smoothness
    target_segment_length = total_length * smoothness
    num_bezier_segments = max(1, int(np.ceil(total_length / target_segment_length)))

    bezier_curves = []

    for i in range(num_bezier_segments):
        # Determine range of original points for this Bézier segment
        t_start = i / num_bezier_segments
        t_end = (i + 1) / num_bezier_segments

        # Handle closed paths by wrapping around
        if is_closed and i == num_bezier_segments - 1:
            # Last segment connects back to first point
            length_start = t_start * total_length
            length_end = total_length

            # Find points in this range
            idx_start = np.searchsorted(cumulative_length, length_start)
            idx_end = len(points)

            # Include wrap-around to start
            segment_points = np.vstack([
                points[idx_start:],
                points[:1]  # Wrap to first point
            ])
        else:
            length_start = t_start * total_length
            length_end = t_end * total_length

            idx_start = np.searchsorted(cumulative_length, length_start)
            idx_end = np.searchsorted(cumulative_length, length_end) + 1
            idx_end = min(idx_end, len(points))

            segment_points = points[idx_start:idx_end]

        if len(segment_points) >= 2:
            bezier_curves.append(fit_bezier_curve_segment(segment_points))

    return bezier_curves


def bezier_segments_to_svg_path(bezier_curves: list, close_path: bool = True) -> str:
    """
    Convert a list of cubic Bézier curve segments to SVG path data.

    Args:
        bezier_curves: List of (P0, P1, P2, P3) tuples
        close_path: Whether to close the path with 'Z' command

    Returns:
        SVG path data string (e.g., "M x,y C x1,y1 x2,y2 x,y C ...")
    """
    if not bezier_curves:
        return ""

    path_parts = []

    # Start with first curve
    P0, P1, P2, P3 = bezier_curves[0]
    path_parts.append(f"M {P0[0]:.6f},{P0[1]:.6f}")
    path_parts.append(f"C {P1[0]:.6f},{P1[1]:.6f} {P2[0]:.6f},{P2[1]:.6f} {P3[0]:.6f},{P3[1]:.6f}")

    # Add remaining curves (skip M command, just add C commands)
    for P0, P1, P2, P3 in bezier_curves[1:]:
        path_parts.append(f"C {P1[0]:.6f},{P1[1]:.6f} {P2[0]:.6f},{P2[1]:.6f} {P3[0]:.6f},{P3[1]:.6f}")

    if close_path:
        path_parts.append("Z")

    return " ".join(path_parts)


def simplify_path_douglas_peucker(points: np.ndarray, tolerance: float) -> np.ndarray:
    """
    Simplify an open path using the Douglas-Peucker algorithm.

    Args:
        points: Nx2 array of path vertices (open path)
        tolerance: Maximum distance threshold

    Returns:
        Simplified Mx2 array of vertices (M <= N)
    """
    if len(points) < 3:
        return points

    # Find the point with maximum distance from line between first and last
    start = points[0]
    end = points[-1]

    dists = np.abs(
        np.cross(end - start, start - points) / (np.linalg.norm(end - start) + 1e-10)
    )

    max_dist_idx = np.argmax(dists)
    max_dist = dists[max_dist_idx]

    if max_dist > tolerance:
        # Recursively simplify segments
        left = simplify_path_douglas_peucker(points[:max_dist_idx + 1], tolerance)
        right = simplify_path_douglas_peucker(points[max_dist_idx:], tolerance)
        return np.vstack([left[:-1], right])
    else:
        # All points between start and end are within tolerance
        return np.array([start, end])


def simplify_path_douglas_peucker_closed(points: np.ndarray, tolerance: float) -> np.ndarray:
    """
    Simplify a closed path (polygon) using the Douglas-Peucker algorithm.

    For closed paths, we need to find the farthest point from the closing edge
    and use that as the starting point for simplification.

    Args:
        points: Nx2 array of path vertices (closed path, last point should NOT equal first)
        tolerance: Maximum distance threshold

    Returns:
        Simplified Mx2 array of vertices (M <= N)
    """
    if len(points) < 3:
        return points

    # For closed paths, first find the point farthest from the line connecting
    # first and last points (which are adjacent in the closed loop)
    start = points[0]
    end = points[-1]

    # Calculate distances from all points to the line between first and last
    dists = np.abs(
        np.cross(end - start, start - points) / (np.linalg.norm(end - start) + 1e-10)
    )

    max_dist_idx = np.argmax(dists)

    # Rotate the path so that the farthest point becomes the start
    # This ensures the closing edge has minimal deviation
    if max_dist_idx > 0:
        rotated_points = np.vstack([points[max_dist_idx:], points[:max_dist_idx]])
    else:
        rotated_points = points

    # Now apply standard Douglas-Peucker to the rotated open path
    simplified = simplify_path_douglas_peucker(rotated_points, tolerance)

    return simplified


def sample_cubic_bezier(P0: np.ndarray, P1: np.ndarray, P2: np.ndarray,
                        P3: np.ndarray, num_samples: int = 20) -> np.ndarray:
    """
    Sample points along a cubic Bézier curve.

    Args:
        P0, P1, P2, P3: Control points of cubic Bézier curve
        num_samples: Number of points to sample along the curve

    Returns:
        Nx2 array of sampled points
    """
    t = np.linspace(0, 1, num_samples)
    t = t.reshape(-1, 1)

    # Cubic Bézier formula: B(t) = (1-t)³P0 + 3(1-t)²tP1 + 3(1-t)t²P2 + t³P3
    points = (
        (1 - t)**3 * P0 +
        3 * (1 - t)**2 * t * P1 +
        3 * (1 - t) * t**2 * P2 +
        t**3 * P3
    )

    return points


def parse_svg_path_to_points(path_data: str, samples_per_curve: int = 20) -> np.ndarray:
    """
    Parse SVG path data and sample points along Bézier curves.

    Args:
        path_data: SVG path data string (e.g., "M x,y C ... Z")
        samples_per_curve: Number of points to sample per Bézier segment

    Returns:
        Nx2 array of points along the path
    """
    import re

    # Remove extra whitespace and normalize
    path_data = re.sub(r'\s+', ' ', path_data.strip())

    # Parse commands
    commands = re.findall(r'[MmLlCcZz][^MmLlCcZz]*', path_data)

    points = []
    current_pos = np.array([0.0, 0.0])

    for cmd in commands:
        cmd_type = cmd[0]
        coords_str = cmd[1:].strip()

        if cmd_type == 'M':
            # Move to absolute position
            coords = [float(x) for x in re.findall(r'[-+]?[0-9]*\.?[0-9]+', coords_str)]
            current_pos = np.array([coords[0], coords[1]])
            points.append(current_pos.copy())

        elif cmd_type == 'L':
            # Line to absolute position
            coords = [float(x) for x in re.findall(r'[-+]?[0-9]*\.?[0-9]+', coords_str)]
            current_pos = np.array([coords[0], coords[1]])
            points.append(current_pos.copy())

        elif cmd_type == 'C':
            # Cubic Bézier curve (absolute)
            coords = [float(x) for x in re.findall(r'[-+]?[0-9]*\.?[0-9]+', coords_str)]

            # Parse control points
            P0 = current_pos
            P1 = np.array([coords[0], coords[1]])
            P2 = np.array([coords[2], coords[3]])
            P3 = np.array([coords[4], coords[5]])

            # Sample along Bézier curve (skip first point to avoid duplicates)
            sampled = sample_cubic_bezier(P0, P1, P2, P3, samples_per_curve)
            points.extend(sampled[1:])  # Skip first point

            current_pos = P3

        elif cmd_type in ['Z', 'z']:
            # Close path - already handled by loop closure
            pass

    return np.array(points)


def _filter_boundary_points(
    points: np.ndarray,
    min_spacing: float,
    corner_angle: float = 140.0
) -> np.ndarray:
    """
    Filter boundary points to enforce minimum spacing between vertices.

    This prevents tiny triangles near boundaries by removing vertices that
    are too close together, while preserving corner points.

    Args:
        points: Nx2 array of boundary points (closed loop)
        min_spacing: Minimum distance between consecutive points
        corner_angle: Angle threshold in degrees - preserve corners sharper than this

    Returns:
        Filtered Mx2 array of boundary points (M <= N)
    """
    if len(points) < 3:
        return points

    # Detect corners first
    is_corner = np.zeros(len(points), dtype=bool)
    corner_threshold_rad = np.deg2rad(corner_angle)

    for i in range(len(points)):
        prev_idx = (i - 1) % len(points)
        next_idx = (i + 1) % len(points)

        # Vectors from current point to neighbors
        v1 = points[prev_idx] - points[i]
        v2 = points[next_idx] - points[i]

        # Normalize vectors
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 > 1e-10 and norm2 > 1e-10:
            v1 = v1 / norm1
            v2 = v2 / norm2

            # Calculate angle
            dot = np.clip(np.dot(v1, v2), -1.0, 1.0)
            angle = np.arccos(dot)

            # Mark as corner if angle is sharp (less than threshold)
            if angle < corner_threshold_rad:
                is_corner[i] = True

    # Filter points while preserving corners
    filtered = [points[0]]  # Always keep first point
    filtered_is_corner = [is_corner[0]]

    for i in range(1, len(points)):
        # Calculate distance from last kept point
        dist = np.linalg.norm(points[i] - filtered[-1])

        # Keep point if it's a corner OR far enough from last kept point
        if is_corner[i] or dist >= min_spacing:
            filtered.append(points[i])
            filtered_is_corner.append(is_corner[i])

    # Check distance between last and first point
    if len(filtered) > 1:
        dist_to_first = np.linalg.norm(filtered[-1] - filtered[0])
        # Only remove if it's not a corner and too close to first
        if dist_to_first < min_spacing and not filtered_is_corner[-1]:
            filtered.pop()

    return np.array(filtered) if len(filtered) >= 3 else points


def mesh_from_svg(
    svg_path: str,
    output_path: str,
    max_area: Optional[float] = None,
    min_angle: float = 20.0,
    min_edge_length: Optional[float] = None,
    min_boundary_spacing: Optional[float] = None,
    boundary_corner_angle: float = 140.0,
    samples_per_curve: int = 20
) -> Dict:
    """
    Generate triangular mesh from SVG contours using Triangle library.

    Args:
        svg_path: Path to input SVG file
        output_path: Output mesh file path (supports .obj, .stl, .ply, .mesh, .xml formats)
        max_area: Maximum triangle area constraint (None = no constraint)
        min_angle: Minimum angle constraint in degrees (default: 20°)
        min_edge_length: Minimum edge length constraint. If specified, overrides max_area
                        to ensure edges are at least this long. Useful for controlling
                        mesh resolution. (None = no constraint)
        min_boundary_spacing: Minimum spacing between boundary vertices. Filters boundary
                             points that are too close together to avoid tiny elements
                             near boundaries. Corner points are always preserved regardless
                             of spacing. (None = no filtering)
        boundary_corner_angle: Angle threshold in degrees for corner detection during
                              boundary filtering. Corners sharper than this angle are
                              always preserved even if closer than min_boundary_spacing.
                              (default: 140°)
        samples_per_curve: Number of samples per Bézier curve segment

    Returns:
        Dictionary containing mesh data:
            - vertices: Nx2 array of vertex coordinates
            - triangles: Mx3 array of triangle vertex indices
            - edges: Kx2 array of boundary edge vertex indices

    Example:
        >>> # Control by area
        >>> mesh_data = mesh_from_svg(
        ...     "contour.svg",
        ...     "mesh.obj",
        ...     max_area=0.01,
        ...     min_angle=25.0
        ... )
        >>> # Control by minimum edge length
        >>> mesh_data = mesh_from_svg(
        ...     "contour.svg",
        ...     "mesh.obj",
        ...     min_edge_length=0.05,  # Edges at least 0.05 units
        ...     min_angle=25.0
        ... )
        >>> print(f"Generated {len(mesh_data['triangles'])} triangles")

    Supported formats:
        - .obj: Wavefront OBJ (3D visualization)
        - .stl: STL format (3D printing)
        - .ply: PLY format (point cloud processing)
        - .mesh: Medit format (FEM solvers)
        - .xml: FEniCS XML format (topology optimization with FEniCS/pytop)
    """
    try:
        import triangle
    except ImportError:
        raise ImportError(
            "triangle library is required for mesh generation. "
            "Install with: pip install triangle"
        )

    # Parse SVG file
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Get SVG viewBox to determine coordinate system bounds
    viewbox_str = root.get('viewBox', '')
    if viewbox_str:
        viewbox_parts = viewbox_str.split()
        if len(viewbox_parts) == 4:
            svg_x_min = float(viewbox_parts[0])
            svg_y_min = float(viewbox_parts[1])
            svg_width = float(viewbox_parts[2])
            svg_height = float(viewbox_parts[3])
            svg_y_max = svg_y_min + svg_height
        else:
            svg_y_min = None
            svg_y_max = None
    else:
        svg_y_min = None
        svg_y_max = None

    # Find all path elements
    # Handle both with and without namespace
    paths = root.findall('.//{http://www.w3.org/2000/svg}path')
    if not paths:
        paths = root.findall('.//path')

    if not paths:
        raise ValueError(f"No paths found in SVG file: {svg_path}")

    # Extract boundary contours
    all_segments = []
    all_vertices = []
    contour_info = []  # Store info about each contour
    vertex_offset = 0

    for path in paths:
        path_data = path.get('d', '')
        if not path_data:
            continue

        # Sample points along the path
        contour_points = parse_svg_path_to_points(path_data, samples_per_curve)

        if len(contour_points) < 3:
            continue

        # Flip Y coordinates to convert from SVG coordinate system (origin at top)
        # to physical coordinate system (origin at bottom)
        if svg_y_min is not None and svg_y_max is not None:
            contour_points[:, 1] = svg_y_max - (contour_points[:, 1] - svg_y_min)

        # Filter boundary points if min_boundary_spacing is specified
        if min_boundary_spacing is not None and min_boundary_spacing > 0:
            num_before = len(contour_points)
            contour_points = _filter_boundary_points(
                contour_points,
                min_boundary_spacing,
                corner_angle=boundary_corner_angle
            )
            num_after = len(contour_points)
            if num_before != num_after:
                print(f"  Boundary filtering: {num_before} → {num_after} points ({num_before - num_after} removed, corners preserved)")

        if len(contour_points) < 3:
            continue

        # Add vertices
        num_points = len(contour_points)
        all_vertices.append(contour_points)

        # Create segments (edges) for this contour
        # Close the loop: last point connects to first
        segments = []
        for i in range(num_points):
            start_idx = vertex_offset + i
            end_idx = vertex_offset + ((i + 1) % num_points)
            segments.append([start_idx, end_idx])

        all_segments.extend(segments)

        # Store contour info (points, area, centroid)
        contour_info.append({
            'points': contour_points,
            'vertex_start': vertex_offset,
            'vertex_end': vertex_offset + num_points
        })

        vertex_offset += num_points

    if not all_vertices:
        raise ValueError("No valid contours found in SVG")

    # Combine all vertices
    vertices = np.vstack(all_vertices)
    segments = np.array(all_segments, dtype=np.int32)

    # Identify contour types using signed area
    # The largest contour is the outer solid boundary
    # Smaller contours inside are holes (voids)

    contour_areas = []
    for info in contour_info:
        points = info['points']

        # Calculate signed area using shoelace formula
        x = points[:, 0]
        y = points[:, 1]
        signed_area = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
        signed_area += 0.5 * (x[-1] * y[0] - x[0] * y[-1])

        info['signed_area'] = signed_area
        contour_areas.append(abs(signed_area))

    # Find the largest contour - this is the outer solid boundary
    max_area_idx = np.argmax(contour_areas)
    largest_contour_area = contour_areas[max_area_idx]

    # The largest contour is the outer boundary (solid)
    # Smaller contours are holes (voids)
    outer_boundary_idx = max_area_idx
    hole_indices = []

    for i, info in enumerate(contour_info):
        if i != outer_boundary_idx and abs(info['signed_area']) < 0.5 * largest_contour_area:
            hole_indices.append(i)

    if hole_indices:
        print(f"  Detected {len(hole_indices)} hole(s) inside solid boundary")

    # Use only the outer boundary for segments
    info = contour_info[outer_boundary_idx]
    points = info['points']
    num_points = len(points)

    all_vertices_filtered = [points]
    all_segments_filtered = []

    # Create segments for outer boundary
    for i in range(num_points):
        start_idx = i
        end_idx = (i + 1) % num_points
        all_segments_filtered.append([start_idx, end_idx])

    # Add hole contours as internal boundaries
    vertex_offset = num_points
    for idx in hole_indices:
        info = contour_info[idx]
        points = info['points']
        num_points_hole = len(points)

        all_vertices_filtered.append(points)

        # Create segments for hole
        for i in range(num_points_hole):
            start_idx = vertex_offset + i
            end_idx = vertex_offset + ((i + 1) % num_points_hole)
            all_segments_filtered.append([start_idx, end_idx])

        vertex_offset += num_points_hole

    vertices = np.vstack(all_vertices_filtered)
    segments = np.array(all_segments_filtered, dtype=np.int32)

    # Specify hole points (centroids of void regions)
    holes = []
    for idx in hole_indices:
        info = contour_info[idx]
        centroid = np.mean(info['points'], axis=0)
        holes.append(centroid)

    holes = np.array(holes) if holes else None

    # Prepare input for Triangle
    tri_input = {
        'vertices': vertices,
        'segments': segments
    }

    if holes is not None and len(holes) > 0:
        tri_input['holes'] = holes
        print(f"  Detected {len(holes)} hole(s)")

    # Enforce min_edge_length by setting a floor on max_area.
    # Triangle cannot enforce a minimum edge length directly, but we can
    # prevent max_area from being so small that tiny edges are forced.
    # For an equilateral triangle: area = (sqrt(3)/4) * edge^2 ≈ 0.433 * edge^2
    if min_edge_length is not None:
        area_floor = 0.433 * (min_edge_length ** 2)
        if max_area is None:
            max_area = area_floor
            print(f"  Min edge length: {min_edge_length:.4f} → Max area floor: {max_area:.6f}")
        elif max_area < area_floor:
            print(f"  Min edge length: {min_edge_length:.4f} → Raising max_area "
                  f"from {max_area:.6f} to {area_floor:.6f}")
            max_area = area_floor
        else:
            print(f"  Min edge length: {min_edge_length:.4f} (max_area={max_area:.6f} already satisfies)")

    # Build Triangle options string
    # 'p' - triangulate a Planar Straight Line Graph
    # 'q' - quality mesh with minimum angle constraint
    # 'a' - maximum area constraint
    # 'D' - Delaunay triangulation (conforming)
    options = f'pq{min_angle}'

    if max_area is not None:
        options += f'a{max_area}'

    # Generate mesh
    print(f"Generating mesh with Triangle...")
    print(f"  Input vertices: {len(vertices)}")
    print(f"  Input segments: {len(segments)}")
    print(f"  Options: {options}")

    tri_output = triangle.triangulate(tri_input, options)

    mesh_vertices = tri_output['vertices']
    mesh_triangles = tri_output['triangles']
    mesh_edges = tri_output.get('segments', segments)

    print(f"  Output vertices: {len(mesh_vertices)}")
    print(f"  Output triangles: {len(mesh_triangles)}")

    # Save mesh to file
    _save_mesh(output_path, mesh_vertices, mesh_triangles, mesh_edges)

    return {
        'vertices': mesh_vertices,
        'triangles': mesh_triangles,
        'edges': mesh_edges
    }


def _save_mesh(output_path: str, vertices: np.ndarray, triangles: np.ndarray,
               edges: np.ndarray) -> None:
    """
    Save mesh to file in various formats.

    Args:
        output_path: Output file path
        vertices: Nx2 or Nx3 array of vertices
        triangles: Mx3 array of triangle indices
        edges: Kx2 array of edge indices (optional)
    """
    from pathlib import Path

    ext = Path(output_path).suffix.lower()

    # Ensure 3D vertices (add z=0 if 2D)
    if vertices.shape[1] == 2:
        vertices_3d = np.column_stack([vertices, np.zeros(len(vertices))])
    else:
        vertices_3d = vertices

    if ext == '.obj':
        _save_obj(output_path, vertices_3d, triangles)
    elif ext == '.stl':
        _save_stl(output_path, vertices_3d, triangles)
    elif ext == '.ply':
        _save_ply(output_path, vertices_3d, triangles)
    elif ext == '.mesh':
        _save_mesh_format(output_path, vertices, triangles, edges)
    elif ext == '.xml':
        _save_xml(output_path, vertices, triangles)
    else:
        raise ValueError(f"Unsupported mesh format: {ext}")

    print(f"Mesh saved to: {output_path}")


def _save_obj(path: str, vertices: np.ndarray, triangles: np.ndarray) -> None:
    """Save mesh in OBJ format."""
    with open(path, 'w') as f:
        f.write("# Generated by libertas\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for tri in triangles:
            # OBJ indices are 1-based
            f.write(f"f {tri[0]+1} {tri[1]+1} {tri[2]+1}\n")


def _save_stl(path: str, vertices: np.ndarray, triangles: np.ndarray) -> None:
    """Save mesh in ASCII STL format."""
    with open(path, 'w') as f:
        f.write("solid libertas_mesh\n")
        for tri in triangles:
            v0, v1, v2 = vertices[tri]
            # Calculate normal
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(normal)
            if norm_len > 1e-10:
                normal = normal / norm_len
            else:
                normal = np.array([0, 0, 1])

            f.write(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {v0[0]:.6f} {v0[1]:.6f} {v0[2]:.6f}\n")
            f.write(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}\n")
            f.write(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write("endsolid libertas_mesh\n")


def _save_ply(path: str, vertices: np.ndarray, triangles: np.ndarray) -> None:
    """Save mesh in PLY format."""
    with open(path, 'w') as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(vertices)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write(f"element face {len(triangles)}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")

        for v in vertices:
            f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        for tri in triangles:
            f.write(f"3 {tri[0]} {tri[1]} {tri[2]}\n")


def _save_mesh_format(path: str, vertices: np.ndarray, triangles: np.ndarray,
                     edges: np.ndarray) -> None:
    """Save mesh in .mesh format (Medit format)."""
    with open(path, 'w') as f:
        f.write("MeshVersionFormatted 1\n")
        f.write("Dimension 2\n\n")

        f.write(f"Vertices\n{len(vertices)}\n")
        for v in vertices:
            f.write(f"{v[0]:.6f} {v[1]:.6f} 0\n")

        f.write(f"\nTriangles\n{len(triangles)}\n")
        for tri in triangles:
            f.write(f"{tri[0]+1} {tri[1]+1} {tri[2]+1} 0\n")

        f.write(f"\nEdges\n{len(edges)}\n")
        for edge in edges:
            f.write(f"{edge[0]+1} {edge[1]+1} 1\n")

        f.write("\nEnd\n")


def _save_xml(path: str, vertices: np.ndarray, triangles: np.ndarray) -> None:
    """
    Save mesh in FEniCS XML format.

    This creates a 2D triangular mesh in FEniCS-compatible XML format
    that can be read with dolfin.Mesh() or pytop.Mesh().

    Args:
        path: Output XML file path
        vertices: Nx2 array of vertex coordinates
        triangles: Mx3 array of triangle vertex indices
    """
    with open(path, 'w') as f:
        f.write('<?xml version="1.0"?>\n')
        f.write('<dolfin xmlns:dolfin="http://fenicsproject.org">\n')
        f.write('  <mesh celltype="triangle" dim="2">\n')

        # Write vertices
        f.write(f'    <vertices size="{len(vertices)}">\n')
        for i, v in enumerate(vertices):
            f.write(f'      <vertex index="{i}" x="{v[0]:.16e}" y="{v[1]:.16e}"/>\n')
        f.write('    </vertices>\n')

        # Write cells (triangles)
        f.write(f'    <cells size="{len(triangles)}">\n')
        for i, tri in enumerate(triangles):
            f.write(f'      <triangle index="{i}" v0="{tri[0]}" v1="{tri[1]}" v2="{tri[2]}"/>\n')
        f.write('    </cells>\n')

        f.write('  </mesh>\n')
        f.write('</dolfin>\n')


def generate_stripe_pattern(
    xml_dir: str,
    extracted_mesh_path: str,
    stripe_width: float = 0.06,
    refine_levels: int = 2,
    absolute_tol: float = 1e-3,
    output_name: str = "stripe"
) -> None:
    """
    Generate stripe pattern from optimization results using extracted mesh.

    This function takes the density and orientation fields from topology optimization
    and generates a stripe pattern on the extracted solid mesh using pytop's
    sh_stripe_tensor function.

    Args:
        xml_dir: Directory containing optimization results (mesh.xml, density.xml, orientation.xml)
        extracted_mesh_path: Path to extracted mesh XML file (from mesh_from_svg)
        stripe_width: Width of stripes (default: 0.06)
        refine_levels: Number of refinement levels for extracted mesh (default: 2)
        absolute_tol: Absolute tolerance for stripe generation (default: 1e-3)
        output_name: Base name for output files (default: "stripe")

    Returns:
        None (saves stripe pattern to {xml_dir}/{output_name}.xml and .vtu)

    Example:
        >>> # After optimization and mesh extraction
        >>> generate_stripe_pattern(
        ...     xml_dir="output/example/xml",
        ...     extracted_mesh_path="output/example/xml/mesh_from_density.xml",
        ...     stripe_width=0.06,
        ...     refine_levels=2
        ... )
        >>> # Output: output/example/xml/stripe.xml and stripe.vtu

    Note:
        - Requires pytop with sh_stripe_tensor from pytop.toolkit.dehomogenization
        - The extracted mesh should represent the solid regions (density > threshold)
        - Density and orientation are projected from original mesh to extracted mesh
        - Refinement improves stripe pattern resolution
    """
    if pt is None:
        raise ImportError(
            "FEniCS (pytop) is required for stripe pattern generation. "
            "This function requires pytop.toolkit.dehomogenization.sh_stripe_tensor"
        )

    try:
        from pytop.toolkit.dehomogenization import sh_stripe_tensor
    except ImportError:
        raise ImportError(
            "sh_stripe_tensor not found. "
            "Make sure pytop.toolkit.dehomogenization is available."
        )

    xml_dir = Path(xml_dir)

    # Load original optimization mesh
    print(f"\n{'='*60}")
    print("Generating Stripe Pattern from Extracted Mesh")
    print(f"{'='*60}")
    print("\n1. Loading original optimization mesh and results...")

    mesh_orig = pt.Mesh(str(xml_dir / "mesh.xml"))
    print(f"   Original mesh: {mesh_orig.num_vertices()} vertices, {mesh_orig.num_cells()} cells")

    # Load extracted mesh and refine
    print(f"\n2. Loading extracted mesh: {extracted_mesh_path}")
    mesh_extracted = pt.Mesh(str(extracted_mesh_path))
    print(f"   Extracted mesh: {mesh_extracted.num_vertices()} vertices, {mesh_extracted.num_cells()} cells")

    # Refine extracted mesh
    print(f"\n3. Refining extracted mesh ({refine_levels} levels)...")
    mesh_refined = mesh_extracted
    for i in range(refine_levels):
        mesh_refined = pt.refine(mesh_refined)
        print(f"   Level {i+1}: {mesh_refined.num_vertices()} vertices, {mesh_refined.num_cells()} cells")

    # Create function spaces
    print("\n4. Creating function spaces...")
    U_orig = pt.FunctionSpace(mesh_orig, 'CG', 1)
    V_orig = pt.VectorFunctionSpace(mesh_orig, 'CG', 1, dim=3)
    U_refined = pt.FunctionSpace(mesh_refined, 'CG', 1)
    V_refined = pt.VectorFunctionSpace(mesh_refined, 'CG', 1, dim=3)

    # Load density and orientation from original mesh
    print("\n5. Loading density and orientation fields...")
    rho = pt.read_fenics_function_from_file(str(xml_dir / "density"), U_orig, "density")
    tens = pt.read_fenics_function_from_file(str(xml_dir / "orientation"), V_orig, "orientation")
    print("   Density and orientation loaded")

    # Allow extrapolation for projection
    rho.set_allow_extrapolation(True)
    tens.set_allow_extrapolation(True)

    # Project to refined extracted mesh
    print("\n6. Projecting fields to refined mesh...")
    rho_refined = pt.project(rho, U_refined, annotate=False)
    tens_refined = pt.project(tens, V_refined, annotate=False)
    print("   Projection complete")

    # Generate stripe pattern
    print(f"\n7. Generating stripe pattern (width={stripe_width}, tol={absolute_tol})...")
    stripe = sh_stripe_tensor(
        mesh_refined,
        tens_refined,
        rho_refined,
        stripe_width,
        absolute_tol=absolute_tol
    )
    print("   Stripe pattern generated")

    # Save results
    print(f"\n8. Saving stripe pattern and refined mesh...")

    # Save refined mesh to XML (if refinement was used)
    if refine_levels > 0:
        refined_mesh_path = xml_dir / f"mesh_refined_r{refine_levels}.xml"
        try:
            import dolfin
            dolfin.File(str(refined_mesh_path)) << mesh_refined
            print(f"   Refined mesh saved to: {refined_mesh_path}")
        except Exception as e:
            print(f"   Warning: Could not save refined mesh: {e}")

    # Save stripe pattern XML in xml directory
    xml_output_path = xml_dir / output_name
    try:
        import dolfin
        xml_file = dolfin.File(str(xml_output_path) + ".xml")
        xml_file << stripe
        print(f"   Stripe XML saved to: {xml_output_path}.xml")
    except Exception as e:
        print(f"   Warning: Could not save XML format: {e}")

    # Save HDF5 and XDMF in h5 subdirectory
    h5_dir = xml_dir.parent / "h5"
    h5_dir.mkdir(exist_ok=True)
    h5_output_path = h5_dir / output_name

    # Save as HDF5/XDMF format
    try:
        import dolfin
        xdmf_file = dolfin.XDMFFile(str(h5_output_path) + ".xdmf")
        xdmf_file.write(stripe)
        xdmf_file.close()
        print(f"   XDMF/HDF5 saved to: {h5_output_path}.xdmf")
        print(f"                       {h5_output_path}.h5")
    except Exception as e:
        print(f"   Warning: Could not save HDF5/XDMF format: {e}")

    print(f"\n{'='*60}")
    print("Stripe Pattern Generation Complete!")
    print(f"{'='*60}")
    print(f"\nOutput files:")
    print(f"  - {xml_output_path}.xml (Stripe pattern - FEniCS XML)")
    if refine_levels > 0:
        refined_mesh_path = xml_dir / f"mesh_refined_r{refine_levels}.xml"
        print(f"  - {refined_mesh_path} (Refined mesh - FEniCS XML)")
    print(f"  - {h5_output_path}.xdmf (Stripe pattern - XDMF)")
    print(f"  - {h5_output_path}.h5 (Stripe pattern - HDF5)")
    print(f"\nView in ParaView:")
    print(f"  paraview {h5_output_path}.xdmf")
    if refine_levels > 0:
        refined_mesh_path = xml_dir / f"mesh_refined_r{refine_levels}.xml"
        print(f"\nTo load stripe in Python (use refined mesh):")
        print(f"  mesh = pt.Mesh('{refined_mesh_path}')")
        print(f"  U = pt.FunctionSpace(mesh, 'CG', 1)")
        print(f"  stripe = pt.read_fenics_function_from_file('{xml_output_path}', U, '{output_name}')")
    print(f"{'='*60}\n")


def _rotate_orientation_tensor(
    tens: "pt.Function",
    theta_rad: float,
    V: "pt.FunctionSpace",
) -> "pt.Function":
    """Rotate an orientation tensor vector (a11, a22, a12) by a fixed angle.

    The orientation tensor is stored as a 3-component vector ``[a11, a22, a12]``
    representing the symmetric 2x2 matrix ``[[a11, a12], [a12, a22]]``.
    A rotation by θ gives::

        a' = R(θ) @ a @ R(θ)^T

    which expands to::

        a'11 = c² a11 + s² a22 - 2sc a12
        a'22 = s² a11 + c² a22 + 2sc a12
        a'12 = sc (a11 - a22) + (c² - s²) a12

    Args:
        tens: FEniCS vector Function with components (a11, a22, a12).
        theta_rad: Rotation angle in radians.
        V: VectorFunctionSpace (dim=3) on the same mesh.

    Returns:
        New FEniCS Function with rotated components.
    """
    import math
    c = math.cos(theta_rad)
    s = math.sin(theta_rad)
    c2, s2, sc = c * c, s * s, s * c

    rotated_expr = pt.as_vector([
        c2 * tens[0] + s2 * tens[1] - 2 * sc * tens[2],
        s2 * tens[0] + c2 * tens[1] + 2 * sc * tens[2],
        sc * (tens[0] - tens[1]) + (c2 - s2) * tens[2],
    ])
    rotated = pt.project(rotated_expr, V, annotate=False)
    return rotated


def generate_stacked_stripe_patterns(
    xml_dir: str,
    extracted_mesh_path: str,
    stacking_sequence: list,
    stripe_width: float = 0.06,
    refine_levels: int = 2,
    absolute_tol: float = 1e-3,
    output_prefix: str = "stripe",
) -> dict:
    """Generate stripe patterns for each unique ply angle in a stacking sequence.

    For a stacking sequence such as ``[0, 90, 90, 0]``, the optimized
    orientation tensor is rotated by each *unique* offset and fed into
    ``sh_stripe_tensor`` independently.  Duplicate angles are detected so
    that the expensive PDE solve runs only once per unique offset.

    Args:
        xml_dir: Directory containing ``mesh.xml``, ``density.xml``, ``orientation.xml``.
        extracted_mesh_path: Path to extracted mesh XML file.
        stacking_sequence: Layer angle offsets in **degrees** (e.g. ``[0, 90, 90, 0]``).
        stripe_width: Stripe hatch spacing in mesh units.
        refine_levels: Mesh refinement levels for the extracted mesh.
        absolute_tol: Convergence tolerance for Swift-Hohenberg solver.
        output_prefix: Base name for output files.  Files are named
            ``{output_prefix}_{angle}deg`` (e.g. ``stripe_0deg``).

    Returns:
        Dictionary mapping each ply index to its output info::

            {
                "plies": [
                    {"index": 0, "angle": 0,  "output_name": "stripe_0deg", ...},
                    {"index": 1, "angle": 90, "output_name": "stripe_90deg", ...},
                    ...
                ],
                "unique_angles": [0, 90],
                "mesh_path": "<refined mesh path>",
            }
    """
    import math

    if pt is None:
        raise ImportError("FEniCS (pytop) is required for stacked stripe generation.")

    try:
        from pytop.toolkit.dehomogenization import sh_stripe_tensor
    except ImportError:
        raise ImportError(
            "sh_stripe_tensor not found. "
            "Make sure pytop.toolkit.dehomogenization is available."
        )

    xml_dir = Path(xml_dir)

    # --- Identify unique angles -----------------------------------------------
    unique_angles = sorted(set(stacking_sequence))
    angle_to_output = {a: f"{output_prefix}_{a}deg" for a in unique_angles}

    print(f"\n{'='*60}")
    print("Stacked Stripe Pattern Generation")
    print(f"{'='*60}")
    print(f"  Stacking sequence : {stacking_sequence}")
    print(f"  Unique angles     : {unique_angles}")
    print(f"  Stripe width      : {stripe_width}")
    print(f"  Refine levels     : {refine_levels}")

    # --- Load meshes and fields (once) ----------------------------------------
    print("\n1. Loading original mesh and fields...")
    mesh_orig = pt.Mesh(str(xml_dir / "mesh.xml"))
    U_orig = pt.FunctionSpace(mesh_orig, 'CG', 1)
    V_orig = pt.VectorFunctionSpace(mesh_orig, 'CG', 1, dim=3)

    rho = pt.read_fenics_function_from_file(str(xml_dir / "density"), U_orig, "density")
    tens = pt.read_fenics_function_from_file(str(xml_dir / "orientation"), V_orig, "orientation")
    rho.set_allow_extrapolation(True)
    tens.set_allow_extrapolation(True)

    # --- Load and refine extracted mesh (once) --------------------------------
    print(f"\n2. Loading extracted mesh: {extracted_mesh_path}")
    mesh_extracted = pt.Mesh(str(extracted_mesh_path))
    mesh_refined = mesh_extracted
    for i in range(refine_levels):
        mesh_refined = pt.refine(mesh_refined)
    print(f"   Refined mesh: {mesh_refined.num_vertices()} vertices, "
          f"{mesh_refined.num_cells()} cells")

    U_refined = pt.FunctionSpace(mesh_refined, 'CG', 1)
    V_refined = pt.VectorFunctionSpace(mesh_refined, 'CG', 1, dim=3)

    # --- Project density (once) -----------------------------------------------
    print("\n3. Projecting density to refined mesh...")
    rho_refined = pt.project(rho, U_refined, annotate=False)

    # --- Project base orientation (once) and rotate per unique angle ----------
    print("\n4. Projecting orientation to refined mesh...")
    tens_refined = pt.project(tens, V_refined, annotate=False)

    # Save refined mesh
    refined_mesh_path = None
    if refine_levels > 0:
        refined_mesh_path = xml_dir / f"mesh_refined_r{refine_levels}.xml"
        try:
            import dolfin
            dolfin.File(str(refined_mesh_path)) << mesh_refined
        except Exception:
            pass

    h5_dir = xml_dir.parent / "h5"
    h5_dir.mkdir(exist_ok=True)

    # --- Generate stripe for each unique angle --------------------------------
    generated = {}  # angle -> output_name
    for angle_deg in unique_angles:
        theta_rad = angle_deg * math.pi / 180.0
        output_name = angle_to_output[angle_deg]

        print(f"\n5. Generating stripe for {angle_deg}° offset...")

        if abs(theta_rad) < 1e-12:
            tens_rotated = tens_refined
        else:
            tens_rotated = _rotate_orientation_tensor(tens_refined, theta_rad, V_refined)

        stripe = sh_stripe_tensor(
            mesh_refined,
            tens_rotated,
            rho_refined,
            stripe_width,
            absolute_tol=absolute_tol,
        )

        # Save XML
        xml_output = xml_dir / output_name
        try:
            import dolfin
            dolfin.File(str(xml_output) + ".xml") << stripe
            print(f"   Saved: {xml_output}.xml")
        except Exception as e:
            print(f"   Warning: Could not save XML: {e}")

        # Save XDMF/HDF5
        h5_output = h5_dir / output_name
        try:
            import dolfin
            xdmf = dolfin.XDMFFile(str(h5_output) + ".xdmf")
            xdmf.write(stripe)
            xdmf.close()
            print(f"   Saved: {h5_output}.xdmf")
        except Exception as e:
            print(f"   Warning: Could not save XDMF: {e}")

        generated[angle_deg] = output_name

    # --- Build result mapping -------------------------------------------------
    plies = []
    for idx, angle_deg in enumerate(stacking_sequence):
        plies.append({
            "index": idx,
            "angle": angle_deg,
            "output_name": generated[angle_deg],
            "stripe_xml": str(xml_dir / generated[angle_deg]),
        })

    result = {
        "plies": plies,
        "unique_angles": unique_angles,
        "mesh_path": str(refined_mesh_path or extracted_mesh_path),
    }

    print(f"\n{'='*60}")
    print("Stacked Stripe Generation Complete!")
    print(f"{'='*60}")
    print(f"\nGenerated {len(unique_angles)} unique stripe patterns "
          f"for {len(stacking_sequence)} plies:")
    for ply in plies:
        print(f"  Ply {ply['index']}: {ply['angle']:+d}° → {ply['output_name']}")
    print(f"{'='*60}\n")

    return result


def stripe_to_image(
    stripe_xml_path: str,
    mesh_path: str,
    resolution: Optional[Tuple[int, int]] = None,
    auto_resolution: int = 100,
    refine_levels: int = 0,
    density_xml_path: Optional[str] = None,
    apply_density_mask: bool = True,
    compute_edges: bool = False,
    edge_threshold: float = 1e-3
) -> Tuple[np.ndarray, Dict]:
    """
    Convert stripe pattern from XML to numpy image array.

    Reads a stripe pattern function from FEniCS XML format and interpolates it
    onto a regular grid to create a 2D image array. Optionally multiplies with
    density field to show stripes only in solid regions.

    Args:
        stripe_xml_path: Path to stripe XML file (without .xml extension)
        mesh_path: Path to mesh XML file (base mesh, will be refined to match stripe)
        resolution: Target resolution (width, height). If None, auto-calculated
                   from mesh bounds using auto_resolution pixels per unit
        auto_resolution: Pixels per unit length when resolution is None (default: 100)
        refine_levels: Number of refinement levels applied when stripe was generated.
                      The mesh will be refined this many times to match stripe DOFs.
                      (default: 0)
        density_xml_path: Path to density XML file (without .xml extension).
                         If provided, stripe is multiplied by density to show
                         stripes only in solid regions. (default: None)
        apply_density_mask: If True and density_xml_path is provided, multiply
                           stripe by density field. (default: True)

    Returns:
        Tuple of (stripe_image, metadata)
        - stripe_image: 2D numpy array (height, width) with stripe values
        - metadata: Dictionary with bounds, resolution, value range

    Example:
        >>> # Basic usage with density masking
        >>> stripe_img, meta = stripe_to_image(
        ...     "xml/stripe",
        ...     "mesh.xml",
        ...     resolution=(300, 100),
        ...     refine_levels=1,  # Must match stripe generation
        ...     density_xml_path="xml/density"  # Multiply with density
        ... )
        >>> print(f"Shape: {stripe_img.shape}")
        >>> print(f"Range: [{stripe_img.min():.3f}, {stripe_img.max():.3f}]")

    Note:
        Requires FEniCS (pytop) to be installed.
        The refine_levels must match the value used in generate_stripe_pattern().
    """
    if pt is None:
        raise ImportError(
            "FEniCS (pytop) is required for stripe_to_image(). "
            "Install pytop to use this function."
        )

    # Try to load pre-refined mesh if it exists
    mesh_path_obj = Path(mesh_path)
    if refine_levels > 0:
        # Check if refined mesh exists in same directory
        refined_mesh_path = mesh_path_obj.parent / f"mesh_refined_r{refine_levels}.xml"
        if refined_mesh_path.exists():
            print(f"Loading pre-refined mesh: {refined_mesh_path}")
            mesh = pt.Mesh(str(refined_mesh_path))
        else:
            # Refine on the fly
            print(f"Refining mesh on the fly ({refine_levels} levels)...")
            mesh = pt.Mesh(str(mesh_path))
            for i in range(refine_levels):
                mesh = pt.refine(mesh)
    else:
        mesh = pt.Mesh(str(mesh_path))

    # Create function space
    U = pt.FunctionSpace(mesh, 'CG', 1)

    # Load stripe pattern
    stripe = pt.read_fenics_function_from_file(str(stripe_xml_path), U, "stripe")

    # Load density if provided
    density = None
    if density_xml_path is not None and apply_density_mask:
        # Load original mesh for density (density is on original optimization mesh)
        stripe_xml_path_obj = Path(stripe_xml_path)
        xml_dir = stripe_xml_path_obj.parent
        orig_mesh_path = xml_dir / "mesh.xml"

        if orig_mesh_path.exists():
            mesh_orig = pt.Mesh(str(orig_mesh_path))
            U_orig = pt.FunctionSpace(mesh_orig, 'CG', 1)
            density = pt.read_fenics_function_from_file(str(density_xml_path), U_orig, "density")
            density.set_allow_extrapolation(True)
            print(f"Loaded density from: {density_xml_path}.xml")
        else:
            print(f"Warning: Original mesh not found at {orig_mesh_path}, skipping density masking")

    # Get mesh bounds
    coords = mesh.coordinates()
    x_min, y_min = coords.min(axis=0)
    x_max, y_max = coords.max(axis=0)

    # Calculate resolution if not provided
    if resolution is None:
        width = int((x_max - x_min) * auto_resolution)
        height = int((y_max - y_min) * auto_resolution)
        resolution = (width, height)

    # Create regular grid
    x = np.linspace(x_min, x_max, resolution[0])
    y = np.linspace(y_min, y_max, resolution[1])
    X, Y = np.meshgrid(x, y)

    # Interpolate stripe values onto grid
    stripe_array = np.zeros(resolution[::-1])  # (height, width)

    # Allow extrapolation for points slightly outside mesh
    stripe.set_allow_extrapolation(True)

    for i in range(resolution[1]):  # height
        for j in range(resolution[0]):  # width
            try:
                point = pt.Point(X[i, j], Y[i, j])
                stripe_val = stripe(point)

                # Multiply by density if provided
                if density is not None:
                    try:
                        density_val = density(point)
                        stripe_val *= density_val
                    except:
                        stripe_val = 0.0  # Outside density mesh

                stripe_array[i, j] = stripe_val
            except:
                stripe_array[i, j] = 0.0  # Outside mesh

    # Flip so that row 0 corresponds to y_max (top of domain),
    # matching the standard image convention expected by stripe_to_svg.
    stripe_array = np.flipud(stripe_array)

    # Prepare metadata
    metadata = {
        'resolution': resolution,
        'bounds': {
            'x_min': float(x_min),
            'x_max': float(x_max),
            'y_min': float(y_min),
            'y_max': float(y_max)
        },
        'value_range': {
            'min': float(stripe_array.min()),
            'max': float(stripe_array.max())
        },
        'mesh_vertices': mesh.num_vertices(),
        'mesh_cells': mesh.num_cells()
    }

    return stripe_array, metadata


def stripe_to_svg(
    stripe_xml_path: str,
    mesh_path: str,
    output_svg_path: str,
    resolution: Optional[Tuple[int, int]] = None,
    auto_resolution: int = 100,
    refine_levels: int = 0,
    density_xml_path: Optional[str] = None,
    density_threshold: float = 0.5,
    contour_level: float = 0.0,
    stroke_color: str = "#000000",
    stroke_width: float = 0.01,
    min_path_length: float = 0.2,
    show_density_contour: bool = False,
    density_contour_color: str = "#FF0000",
    density_contour_width: float = 0.02,
    density_offset: float = 0.0,
    scale_factor: float = 1.0
) -> Dict:
    """
    Extract contour lines from stripe pattern and save as SVG.

    Converts stripe pattern from XML to image array, extracts contour lines
    at a specified level (default: 0 for zero-crossings), and optionally clips
    by density threshold to show contours only in solid regions.

    Args:
        stripe_xml_path: Path to stripe XML file (without .xml extension)
        mesh_path: Path to mesh XML file (base mesh, will be refined to match stripe)
        output_svg_path: Output SVG file path
        resolution: Target resolution (width, height). If None, auto-calculated
        auto_resolution: Pixels per unit length when resolution is None (default: 100)
        refine_levels: Number of refinement levels applied when stripe was generated
        density_xml_path: Path to density XML file (without .xml extension).
                         If provided, contours are clipped to solid regions
                         where density > density_threshold
        density_threshold: Density threshold for clipping (default: 0.5)
        contour_level: Contour level to extract (default: 0.0 for zero-crossings)
        stroke_color: SVG stroke color (default: "#000000")
        stroke_width: SVG stroke width (default: 0.01)
        min_path_length: Minimum path length to keep in mm (default: 0.2).
                        Paths shorter than this threshold will be filtered out.
                        Set to 0.0 to keep all paths.
        show_density_contour: If True, overlay density contour on the SVG (default: False).
                             Only works when density_xml_path is provided.
        density_contour_color: SVG stroke color for density contour (default: "#FF0000" red)
        density_contour_width: SVG stroke width for density contour (default: 0.02)
        density_offset: Offset distance in mm to shrink the density boundary inward (default: 0.0).
                       Positive values move the boundary inward, creating a safety margin.
                       This affects stripe clipping but NOT the displayed density contour.
        scale_factor: Scale factor to enlarge the entire SVG (default: 1.0).
                     For example, 2.0 will double the size of the output.

    Returns:
        Dictionary with metadata:
            - num_contours: Number of contour segments
            - total_points: Total number of points in all contours
            - bounds: Domain bounds (x_min, x_max, y_min, y_max)
            - resolution: Image resolution used
            - density_threshold: Density threshold used (if applicable)
            - solid_fraction: Fraction of solid region (if density clipping used)

    Example:
        >>> # Basic usage: extract zero-contours without density clipping
        >>> stripe_to_svg(
        ...     "xml/stripe",
        ...     "mesh.xml",
        ...     "contours.svg",
        ...     refine_levels=1
        ... )
        >>> # With density clipping
        >>> stripe_to_svg(
        ...     "xml/stripe",
        ...     "xml/mesh.xml",
        ...     "contours_clipped.svg",
        ...     refine_levels=1,
        ...     density_xml_path="xml/density",
        ...     density_threshold=0.5
        ... )

    Note:
        Requires FEniCS (pytop) and scikit-image to be installed.
    """
    if pt is None:
        raise ImportError(
            "FEniCS (pytop) is required for stripe_to_svg(). "
            "Install pytop to use this function."
        )

    try:
        from skimage import measure
    except ImportError:
        raise ImportError(
            "scikit-image is required for contour extraction. "
            "Install with: pip install scikit-image"
        )

    # Convert stripe to image array
    print(f"Converting stripe pattern to image array...")
    stripe_array, metadata = stripe_to_image(
        stripe_xml_path=stripe_xml_path,
        mesh_path=mesh_path,
        resolution=resolution,
        auto_resolution=auto_resolution,
        refine_levels=refine_levels,
        density_xml_path=None,  # Don't multiply in stripe_to_image
        apply_density_mask=False
    )

    bounds = metadata['bounds']
    x_min, x_max = bounds['x_min'], bounds['x_max']
    y_min, y_max = bounds['y_min'], bounds['y_max']
    height, width = stripe_array.shape

    # Apply density masking if requested
    density_mask = None
    density_array = None
    solid_fraction = None
    if density_xml_path is not None:
        print(f"Loading density field for clipping (threshold={density_threshold})...")

        # Load density from mesh
        # Density is always on the original optimization mesh in xml/ directory
        from pathlib import Path
        density_xml_path_obj = Path(density_xml_path)
        xml_dir = density_xml_path_obj.parent
        orig_mesh_path = xml_dir / "mesh.xml"

        if orig_mesh_path.exists():
            mesh_orig = pt.Mesh(str(orig_mesh_path))
            U_orig = pt.FunctionSpace(mesh_orig, 'CG', 1)
            density_func = pt.read_fenics_function_from_file(
                str(density_xml_path), U_orig, "density"
            )
            density_func.set_allow_extrapolation(True)

            # Interpolate density onto the same grid
            x = np.linspace(x_min, x_max, width)
            y = np.linspace(y_min, y_max, height)
            X, Y = np.meshgrid(x, y)

            density_array = np.zeros((height, width))
            for i in range(height):
                for j in range(width):
                    try:
                        point = pt.Point(X[i, j], Y[i, j])
                        density_val = density_func(point)
                        density_array[i, j] = density_val
                    except:
                        density_array[i, j] = 0.0

            # Flip so row 0 = y_max (image convention), consistent with stripe_array
            density_array = np.flipud(density_array)

            # Create binary mask directly from density array (no padding)
            # This prevents paths from connecting along boundaries
            density_mask_original = (density_array > density_threshold).astype(float)

            solid_fraction = density_mask_original.sum() / density_mask_original.size
            print(f"   Solid region fraction: {solid_fraction:.1%}")

            # Apply offset to density mask if requested
            density_mask = density_mask_original.copy()
            if density_offset > 0:
                print(f"   Applying density offset: {density_offset:.3f}mm inward...")

                try:
                    from scipy import ndimage
                    from skimage import measure

                    # Calculate offset in pixels
                    # Average pixel size in physical units
                    pixel_size_x = (x_max - x_min) / width
                    pixel_size_y = (y_max - y_min) / height
                    pixel_size = (pixel_size_x + pixel_size_y) / 2.0
                    offset_pixels = density_offset / pixel_size

                    # Apply offset to solid regions:
                    # - Shrink from outside boundaries (erosion)
                    # - Expand into holes (dilation of holes = erosion of solid)
                    # This is equivalent to eroding the solid regions from ALL boundaries
                    struct_size = int(np.ceil(offset_pixels * 2))
                    if struct_size % 2 == 0:
                        struct_size += 1  # Make it odd
                    y_struct, x_struct = np.ogrid[-struct_size//2:struct_size//2+1,
                                                   -struct_size//2:struct_size//2+1]
                    struct_element = (x_struct**2 + y_struct**2 <= offset_pixels**2)

                    # Erode solid regions - this shrinks from both outside AND holes
                    density_mask = ndimage.binary_erosion(
                        density_mask_original.astype(bool),
                        structure=struct_element
                    ).astype(float)

                    offset_fraction = density_mask.sum() / density_mask.size
                    print(f"   After offset - solid region fraction: {offset_fraction:.1%}")

                except ImportError:
                    print("   Warning: scipy required for density offset. Install scipy to use this feature.")
                    print("   Continuing without offset...")
                    density_mask = density_mask_original.copy()

            # Mask stripe array
            stripe_masked = stripe_array.copy()
            stripe_masked[density_mask == 0] = np.nan
        else:
            print(f"Warning: Mesh not found at {orig_mesh_path}, skipping density masking")
            stripe_masked = stripe_array
    else:
        stripe_masked = stripe_array

    # Extract contours
    print(f"Extracting contour lines at level={contour_level}...")

    # Prepare array for contour finding
    # NaN values (outside density mask) will be set to a large value to exclude them from contouring
    stripe_for_contours = stripe_masked.copy()
    stripe_for_contours[np.isnan(stripe_for_contours)] = 1e10  # Set NaN to large value outside range

    # Find contours at the specified level
    # Contours will only be found where stripe_for_contours has valid values (not 1e10)
    contours = measure.find_contours(stripe_for_contours, level=contour_level)

    print(f"   Found {len(contours)} initial contour segments")

    # Filter contours: remove any segments that go outside the density mask
    # This ensures that paths outside the offset density boundary are completely deleted
    if density_mask is not None:
        print(f"   Filtering contours by density mask...")

        # Create a stricter mask by eroding the density mask slightly
        # This removes paths that run along the density boundary
        try:
            from scipy import ndimage

            # Erode by 1 pixel to create a buffer zone at boundaries
            # This ensures paths running along boundaries are excluded
            strict_mask = ndimage.binary_erosion(
                density_mask.astype(bool),
                structure=np.ones((3, 3))  # 3x3 structuring element
            ).astype(float)

            print(f"   Applied boundary buffer for stricter filtering")
        except ImportError:
            # If scipy not available, use the original mask
            strict_mask = density_mask

        filtered_contours = []

        for contour in contours:
            if len(contour) < 2:
                continue

            # Split the contour into segments where ALL points are within the strict mask
            current_segment = []

            for point in contour:
                row, col = int(np.round(point[0])), int(np.round(point[1]))

                # Check bounds and strict mask
                if 0 <= row < height and 0 <= col < width and strict_mask[row, col] > 0:
                    # Point is safely inside solid region - add to current segment
                    current_segment.append(point)
                else:
                    # Point is outside or at boundary - end current segment if valid
                    if len(current_segment) >= 2:
                        filtered_contours.append(np.array(current_segment))
                    current_segment = []

            # Add final segment if it exists
            if len(current_segment) >= 2:
                filtered_contours.append(np.array(current_segment))

        print(f"   After density filtering: {len(contours)} -> {len(filtered_contours)} segments")
        contours = filtered_contours
    else:
        print(f"   Found {len(contours)} contour segments")

    # Filter by path length if requested
    if min_path_length > 0:
        filtered_contours = []
        for contour in contours:
            if len(contour) < 2:
                continue

            # Calculate path length
            path_length = 0.0
            for i in range(len(contour) - 1):
                # Convert to physical coordinates
                x1 = x_min + (contour[i, 1] / width) * (x_max - x_min)
                y1 = y_max - (contour[i, 0] / height) * (y_max - y_min)
                x2 = x_min + (contour[i+1, 1] / width) * (x_max - x_min)
                y2 = y_max - (contour[i+1, 0] / height) * (y_max - y_min)

                # Euclidean distance
                path_length += np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

            # Keep only if path length exceeds threshold
            if path_length >= min_path_length:
                filtered_contours.append(contour)

        print(f"   Filtered by length (min={min_path_length:.3f}mm): "
              f"{len(contours)} -> {len(filtered_contours)} segments")
        contours = filtered_contours

    # Build SVG
    print(f"Building SVG...")

    # Apply scale factor
    scaled_width = (x_max - x_min) * scale_factor
    scaled_height = (y_max - y_min) * scale_factor
    scaled_x_min = x_min * scale_factor
    scaled_y_min = y_min * scale_factor
    scaled_x_max = x_max * scale_factor
    scaled_y_max = y_max * scale_factor

    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{scaled_width:.6f}mm" height="{scaled_height:.6f}mm" '
        f'viewBox="{scaled_x_min:.6f} {scaled_y_min:.6f} {scaled_width:.6f} {scaled_height:.6f}">'
    )

    # Add description
    desc = f'Contour lines at level={contour_level} from stripe pattern'
    if density_xml_path is not None:
        desc += f', clipped by density > {density_threshold}'
    svg_lines.append(f'  <desc>{desc}</desc>')

    # Create group for contour lines
    svg_lines.append(
        f'  <g id="stripe_contours" fill="none" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width}">'
    )

    # Convert contours to SVG polylines
    total_points = 0
    for contour in contours:
        if len(contour) < 2:
            continue

        # Convert from image coordinates to physical coordinates
        # Note: Image row 0 is at top, but physical y=0 is at bottom, so flip y
        physical_x = (x_min + (contour[:, 1] / width) * (x_max - x_min)) * scale_factor
        physical_y = (y_max - (contour[:, 0] / height) * (y_max - y_min)) * scale_factor  # Flip y-axis

        # Build SVG polyline
        points_str = " ".join([f"{x:.6f},{y:.6f}" for x, y in zip(physical_x, physical_y)])
        svg_lines.append(f'    <polyline points="{points_str}"/>')

        total_points += len(contour)

    svg_lines.append('  </g>')

    # Add density contour if requested
    num_density_contours = 0
    if show_density_contour and density_xml_path is not None and density_array is not None:
        print(f"Extracting density contour at threshold={density_threshold}...")

        # Pad density array with zeros at boundaries to ensure closed contours at mesh edges
        # This is the same approach as used in svg_to_mesh generation
        density_padded = np.pad(density_array, pad_width=1, mode='constant', constant_values=0)

        # Find contours at density threshold on padded array
        density_contours = measure.find_contours(density_padded, level=density_threshold)
        print(f"   Found {len(density_contours)} density contour segments")

        # Add density contour group
        svg_lines.append(
            f'  <g id="density_contours" fill="none" '
            f'stroke="{density_contour_color}" stroke-width="{density_contour_width}">'
        )

        # Convert density contours to SVG polylines
        for contour in density_contours:
            if len(contour) < 2:
                continue

            # Adjust contour coordinates to account for padding (subtract 1 pixel offset)
            contour_adjusted = contour - 1.0

            # Convert from image coordinates to physical coordinates
            # Note: Image row 0 is at top, but physical y=0 is at bottom, so flip y
            physical_x = (x_min + (contour_adjusted[:, 1] / width) * (x_max - x_min)) * scale_factor
            physical_y = (y_max - (contour_adjusted[:, 0] / height) * (y_max - y_min)) * scale_factor  # Flip y-axis

            # Build SVG polyline
            points_str = " ".join([f"{x:.6f},{y:.6f}" for x, y in zip(physical_x, physical_y)])
            svg_lines.append(f'    <polyline points="{points_str}"/>')
            num_density_contours += 1

        svg_lines.append('  </g>')

    svg_lines.append('</svg>')

    # Write SVG file
    svg_content = '\n'.join(svg_lines)
    with open(output_svg_path, 'w') as f:
        f.write(svg_content)

    print(f"SVG saved to: {output_svg_path}")

    # Prepare result metadata
    result = {
        'num_contours': len(contours),
        'total_points': total_points,
        'bounds': bounds,
        'resolution': metadata['resolution'],
        'contour_level': contour_level
    }

    if density_xml_path is not None:
        result['density_threshold'] = density_threshold
        result['solid_fraction'] = solid_fraction

    if show_density_contour:
        result['num_density_contours'] = num_density_contours

    return result
