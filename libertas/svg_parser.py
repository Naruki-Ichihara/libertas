"""SVG parser for converting SVG files to Path objects."""

from typing import List, Tuple
import xml.etree.ElementTree as ET
from pathlib import Path as FilePath
from libertas.path import Path


def parse_svg_to_paths(svg_file: str, segment_length: float = 0.1) -> List[Path]:
    """
    Parse an SVG file and convert all paths/polylines to Path objects.

    This function reads an SVG file containing paths and polylines, and converts
    them to a list of Path objects. Polylines are already line segments, so they
    are directly converted. For SVG path elements with curves, svgpathtools is
    used to discretize them into line segments at the specified resolution.

    Args:
        svg_file: Path to the SVG file
        segment_length: Maximum length of line segments when discretizing curves (default: 0.1).
                       Smaller values give smoother approximation but more points.

    Returns:
        List of Path objects representing all paths in the SVG

    Example:
        >>> paths = parse_svg_to_paths("output.svg", segment_length=0.05)
        >>> print(f"Loaded {len(paths)} paths")
        >>> for path in paths[:5]:
        ...     print(path)
    """
    # Parse SVG file
    tree = ET.parse(svg_file)
    root = tree.getroot()

    # Handle namespace
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    path_objects = []
    path_id_counter = 0

    # Process all groups in the SVG
    for group in root.findall('.//svg:g', ns):
        group_id = group.get('id', '')

        # Determine path type based on group ID
        if 'stripe' in group_id.lower():
            path_type = 'stripe'
        elif 'density' in group_id.lower() or 'contour' in group_id.lower():
            path_type = 'contour'
        else:
            path_type = 'stripe'  # Default to stripe

        # Process polylines in this group
        for polyline in group.findall('svg:polyline', ns):
            points_str = polyline.get('points')
            if not points_str:
                continue

            # Parse polyline points
            nodes = []
            for point in points_str.strip().split():
                if ',' in point:
                    x, y = map(float, point.split(','))
                    nodes.append((x, y))

            if len(nodes) >= 2:
                path_obj = Path(
                    path_id=path_id_counter,
                    nodes=nodes,
                    path_type=path_type
                )
                path_objects.append(path_obj)
                path_id_counter += 1

        # Process path elements (curves, arcs, etc.) using svgpathtools
        for path_elem in group.findall('svg:path', ns):
            d_attr = path_elem.get('d')
            if not d_attr:
                continue

            try:
                from svgpathtools import parse_path

                # Parse the path
                svg_path = parse_path(d_attr)

                # Discretize the path into line segments
                nodes = discretize_svg_path(svg_path, segment_length)

                if len(nodes) >= 2:
                    path_obj = Path(
                        path_id=path_id_counter,
                        nodes=nodes,
                        path_type=path_type
                    )
                    path_objects.append(path_obj)
                    path_id_counter += 1

            except ImportError:
                print("Warning: svgpathtools not available. Skipping path elements.")
                print("Install with: pip install svgpathtools")
                continue
            except Exception as e:
                print(f"Warning: Failed to parse path element: {e}")
                continue

    return path_objects


def discretize_svg_path(svg_path, segment_length: float = 0.1) -> List[Tuple[float, float]]:
    """
    Discretize an SVG path into line segments.

    Uses svgpathtools to sample points along the path at regular intervals,
    converting curves and arcs into polyline approximations.

    Args:
        svg_path: svgpathtools Path object
        segment_length: Maximum length between consecutive points

    Returns:
        List of (x, y) coordinate tuples
    """
    if len(svg_path) == 0:
        return []

    # Calculate total path length
    total_length = svg_path.length()

    if total_length == 0:
        # Degenerate path
        start = svg_path.point(0)
        return [(start.real, start.imag)]

    # Number of segments needed
    num_segments = max(2, int(total_length / segment_length) + 1)

    # Sample points along the path
    nodes = []
    for i in range(num_segments + 1):
        t = i / num_segments
        point = svg_path.point(t)
        nodes.append((point.real, point.imag))

    return nodes


def save_paths_to_svg(paths: List[Path], output_file: str,
                     width: float, height: float,
                     viewbox: Tuple[float, float, float, float] = None):
    """
    Save a list of Path objects back to an SVG file.

    Args:
        paths: List of Path objects to save
        output_file: Output SVG file path
        width: SVG width
        height: SVG height
        viewbox: Optional viewBox (x_min, y_min, width, height).
                If None, uses (0, 0, width, height)
    """
    if viewbox is None:
        viewbox = (0, 0, width, height)

    # Group paths by type
    stripe_paths = [p for p in paths if p.path_type == 'stripe']
    contour_paths = [p for p in paths if p.path_type == 'contour']

    # Build SVG
    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.6f}mm" height="{height:.6f}mm" '
        f'viewBox="{viewbox[0]:.6f} {viewbox[1]:.6f} {viewbox[2]:.6f} {viewbox[3]:.6f}">'
    )

    # Add stripe paths group
    if stripe_paths:
        svg_lines.append('  <g id="stripe_contours" fill="none" stroke="#000000" stroke-width="0.01">')
        for path in stripe_paths:
            svg_lines.append(f'    {path.to_svg_polyline()}')
        svg_lines.append('  </g>')

    # Add contour paths group
    if contour_paths:
        svg_lines.append('  <g id="density_contours" fill="none" stroke="#FF0000" stroke-width="0.02">')
        for path in contour_paths:
            svg_lines.append(f'    {path.to_svg_polyline(stroke_color="#FF0000", stroke_width=0.02)}')
        svg_lines.append('  </g>')

    svg_lines.append('</svg>')

    # Write to file
    svg_content = '\n'.join(svg_lines)
    with open(output_file, 'w') as f:
        f.write(svg_content)
