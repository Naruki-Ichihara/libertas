"""Model class for managing multiple layers in 3D printing."""

from typing import List, Optional, Tuple, Iterator, Dict, Any
import numpy as np
from libertas.layer import Layer


class Model:
    """
    Represents a 3D model as a stack of Layer objects.

    A Model manages multiple layers in the Z-axis direction, providing
    functionality for layer stacking, height management, and multi-layer
    operations for 3D printing.

    Attributes:
        model_id: Unique identifier for this model
        layers: List of Layer objects stacked in Z direction
        name: Optional name for the model
        layer_height: Default layer height in mm (can be overridden per layer)
        offset_x: X-axis offset in mm (default: 0.0)
        offset_y: Y-axis offset in mm (default: 0.0)
    """

    def __init__(
        self,
        model_id: int,
        layers: Optional[List[Layer]] = None,
        name: Optional[str] = None,
        layer_height: float = 0.2,
        offset_x: float = 0.0,
        offset_y: float = 0.0
    ):
        """
        Initialize a Model.

        Args:
            model_id: Unique identifier for this model
            layers: List of Layer objects (default: empty list)
            name: Optional name for the model
            layer_height: Default layer height in mm (default: 0.2)
            offset_x: X-axis offset in mm (default: 0.0)
            offset_y: Y-axis offset in mm (default: 0.0)
        """
        self.model_id = model_id
        self.layers = layers if layers is not None else []
        self.name = name if name is not None else f"Model_{model_id}"
        self.layer_height = layer_height
        self.offset_x = offset_x
        self.offset_y = offset_y

        # Update z_heights if not set
        self._update_layer_heights()

    def _update_layer_heights(self):
        """
        Update z_height for layers that don't have it set.

        Assigns z_height based on layer index and default layer_height.
        """
        for i, layer in enumerate(self.layers):
            if layer.z_height is None:
                layer.z_height = (i + 1) * self.layer_height

    def add_layer(self, layer: Layer, z_height: Optional[float] = None):
        """
        Add a layer to the model.

        Args:
            layer: Layer object to add
            z_height: Optional z-height override. If None, uses next sequential height
        """
        if z_height is not None:
            layer.z_height = z_height
        elif layer.z_height is None:
            # Assign next sequential height
            if len(self.layers) == 0:
                layer.z_height = self.layer_height
            else:
                max_z = max(l.z_height for l in self.layers if l.z_height is not None)
                layer.z_height = max_z + self.layer_height

        self.layers.append(layer)

    def insert_layer(self, index: int, layer: Layer, z_height: Optional[float] = None):
        """
        Insert a layer at a specific index.

        Args:
            index: Index at which to insert the layer
            layer: Layer object to insert
            z_height: Optional z-height. If None, will be calculated based on position
        """
        if z_height is not None:
            layer.z_height = z_height
        elif layer.z_height is None:
            layer.z_height = (index + 1) * self.layer_height

        self.layers.insert(index, layer)

    def remove_layer(self, layer_id: int) -> bool:
        """
        Remove a layer by its ID.

        Args:
            layer_id: ID of the layer to remove

        Returns:
            True if layer was found and removed, False otherwise
        """
        for i, layer in enumerate(self.layers):
            if layer.layer_id == layer_id:
                self.layers.pop(i)
                return True
        return False

    def get_layer(self, layer_id: int) -> Optional[Layer]:
        """
        Get a layer by its ID.

        Args:
            layer_id: ID of the layer to retrieve

        Returns:
            Layer object if found, None otherwise
        """
        for layer in self.layers:
            if layer.layer_id == layer_id:
                return layer
        return None

    def get_layer_at_height(self, z_height: float, tolerance: float = 0.01) -> Optional[Layer]:
        """
        Get the layer closest to a specific z-height.

        Args:
            z_height: Target z-height in mm
            tolerance: Maximum distance to consider (default: 0.01mm)

        Returns:
            Layer object if found within tolerance, None otherwise
        """
        min_dist = float('inf')
        closest_layer = None

        for layer in self.layers:
            if layer.z_height is None:
                continue

            dist = abs(layer.z_height - z_height)
            if dist < min_dist and dist <= tolerance:
                min_dist = dist
                closest_layer = layer

        return closest_layer

    def sort_layers_by_height(self):
        """Sort layers by z-height in ascending order."""
        self.layers.sort(key=lambda l: l.z_height if l.z_height is not None else 0)

    def get_height_range(self) -> Tuple[float, float]:
        """
        Get the minimum and maximum z-heights in the model.

        Returns:
            Tuple of (min_z, max_z) in mm
        """
        if not self.layers:
            return (0.0, 0.0)

        z_heights = [l.z_height for l in self.layers if l.z_height is not None]
        if not z_heights:
            return (0.0, 0.0)

        return (min(z_heights), max(z_heights))

    def get_total_height(self) -> float:
        """
        Get the total height of the model.

        Returns:
            Maximum z-height in mm
        """
        min_z, max_z = self.get_height_range()
        return max_z

    def get_bounds(self) -> Tuple[float, float, float, float, float, float]:
        """
        Calculate the 3D bounding box of all layers.

        Returns:
            Tuple of (x_min, y_min, z_min, x_max, y_max, z_max)
        """
        if not self.layers:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        x_min = float('inf')
        y_min = float('inf')
        x_max = float('-inf')
        y_max = float('-inf')

        for layer in self.layers:
            layer_bounds = layer.get_bounds()
            x_min = min(x_min, layer_bounds[0])
            y_min = min(y_min, layer_bounds[1])
            x_max = max(x_max, layer_bounds[2])
            y_max = max(y_max, layer_bounds[3])

        z_min, z_max = self.get_height_range()

        return (x_min, y_min, z_min, x_max, y_max, z_max)

    def set_offset(self, offset_x: float, offset_y: float):
        """
        Set the XY offset for the entire model.

        This offset will be applied when generating GCode, shifting all
        coordinates by the specified amounts.

        Args:
            offset_x: X-axis offset in mm
            offset_y: Y-axis offset in mm
        """
        self.offset_x = offset_x
        self.offset_y = offset_y

    def center_on_bed(self, bed_width: float, bed_depth: float):
        """
        Calculate offset to center the model on a print bed.

        This calculates the offset needed to center the model's bounding box
        on the specified bed dimensions and updates offset_x and offset_y.

        Args:
            bed_width: Print bed width (X dimension) in mm
            bed_depth: Print bed depth (Y dimension) in mm

        Example:
            >>> model.center_on_bed(220, 220)  # Center on Prusa i3 bed
            >>> model.center_on_bed(300, 300)  # Center on CR-10 bed
        """
        bounds = self.get_bounds()
        x_min, y_min, _, x_max, y_max, _ = bounds

        # Calculate model dimensions
        model_width = x_max - x_min
        model_depth = y_max - y_min

        # Calculate center of model
        model_center_x = x_min + model_width / 2
        model_center_y = y_min + model_depth / 2

        # Calculate bed center
        bed_center_x = bed_width / 2
        bed_center_y = bed_depth / 2

        # Calculate offset to move model center to bed center
        self.offset_x = bed_center_x - model_center_x
        self.offset_y = bed_center_y - model_center_y

    def get_center_position(self) -> Tuple[float, float]:
        """
        Get the current center position of the model including offset.

        Returns:
            Tuple of (center_x, center_y) in mm
        """
        bounds = self.get_bounds()
        x_min, y_min, _, x_max, y_max, _ = bounds

        model_center_x = x_min + (x_max - x_min) / 2
        model_center_y = y_min + (y_max - y_min) / 2

        return (model_center_x + self.offset_x, model_center_y + self.offset_y)

    def total_length(self) -> float:
        """
        Calculate total length of all paths in all layers.

        Returns:
            Total length in mm
        """
        return sum(layer.total_length() for layer in self.layers)

    def total_paths(self) -> int:
        """
        Count total number of paths in all layers.

        Returns:
            Total number of paths
        """
        return sum(len(layer) for layer in self.layers)

    def total_nodes(self) -> int:
        """
        Count total number of nodes in all layers.

        Returns:
            Total number of nodes
        """
        return sum(layer.total_nodes() for layer in self.layers)

    def optimize_all_layers(self, start_point: Optional[Tuple[float, float]] = None):
        """
        Optimize path order for all layers.

        Applies both closed and open path optimization to each layer.

        Args:
            start_point: Optional starting point (x, y) for the first layer.
                        Subsequent layers start from the end point of the previous layer.
        """
        current_start = start_point

        for i, layer in enumerate(self.layers):
            print(f"Optimizing layer {i+1}/{len(self.layers)} (z={layer.z_height:.3f}mm)...")

            # Optimize closed paths
            closed_paths = layer.get_closed_paths()
            if len(closed_paths) > 0:
                layer.optimize_closed_path_order(start_point=current_start)

            # Optimize open paths
            open_paths = layer.get_open_paths()
            if len(open_paths) > 0:
                layer.optimize_open_path_order(start_point=current_start)

            # Update start point for next layer (end of last path in current layer)
            if len(layer.paths) > 0:
                last_path = layer.paths[-1]
                current_start = last_path.end_point

    def statistics(self) -> Dict[str, Any]:
        """
        Get statistics about this model.

        Returns:
            Dictionary with model statistics
        """
        total_closed = sum(len(layer.get_closed_paths()) for layer in self.layers)
        total_open = sum(len(layer.get_open_paths()) for layer in self.layers)

        return {
            'model_id': self.model_id,
            'name': self.name,
            'num_layers': len(self.layers),
            'layer_height': self.layer_height,
            'total_height': self.get_total_height(),
            'total_paths': self.total_paths(),
            'total_closed_paths': total_closed,
            'total_open_paths': total_open,
            'total_length': self.total_length(),
            'total_nodes': self.total_nodes(),
            'bounds': self.get_bounds(),
            'height_range': self.get_height_range()
        }

    def clear(self):
        """Remove all layers from this model."""
        self.layers.clear()

    def __len__(self) -> int:
        """Return the number of layers in this model."""
        return len(self.layers)

    def __iter__(self) -> Iterator[Layer]:
        """Iterate over layers in this model."""
        return iter(self.layers)

    def __getitem__(self, index: int) -> Layer:
        """Get layer by index."""
        return self.layers[index]

    def __repr__(self) -> str:
        """String representation of the model."""
        min_z, max_z = self.get_height_range()
        return (f"Model(id={self.model_id}, name='{self.name}', "
                f"layers={len(self.layers)}, "
                f"height={min_z:.3f}-{max_z:.3f}mm, "
                f"paths={self.total_paths()})")
