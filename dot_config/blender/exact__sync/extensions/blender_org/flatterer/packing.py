# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import sys
import importlib
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from types import ModuleType

from mathutils import Vector

is_first_load = "mesh_analysis" not in locals()
if is_first_load:
    from . import mesh_analysis
else:
    import importlib

    mesh_analysis = importlib.reload(mesh_analysis)


@dataclass
class PackResult:
    """Result of packing."""

    canvas_bounds: mesh_analysis.AABB
    covered_area: float
    """Area covered by shapes, in mm^2"""
    num_pages: int
    """Number of pages, each (material_width, material_length) in size."""

    @property
    def wasted_space(self) -> int:
        """Area not covered by shapes."""
        return int(round(self.canvas_bounds.area - self.covered_area))

    def __bool__(self) -> bool:
        """Return whether this result is valid.

        If there are no shapes packed, the result is invalid.
        """
        return bool(self.canvas_bounds)


def pack(
    shapes: list[mesh_analysis.MeshBoundary],
    options: mesh_analysis.Options,
    debug_svg_root: Optional[ET.Element] = None,
) -> PackResult:
    """Pack the shapes."""
    # return _linear_pack(shapes, options)
    return _smart_pack(shapes, options, debug_svg_root=debug_svg_root)


def _linear_pack(
    shapes: list[mesh_analysis.MeshBoundary],
    options: mesh_analysis.Options,
) -> mesh_analysis.AABB:
    """Put all the shapes in a single row."""
    next_x = 0.0
    max_y = 0.0
    for shape in shapes:
        shape.translation.x = next_x - shape.aabb.min_x
        next_x += shape.aabb.width + 2 * options.shape_padding
        max_y = max(max_y, shape.aabb.max_y + options.shape_padding)

    return mesh_analysis.AABB(min_x=0, min_y=0, max_x=next_x, max_y=max_y)


def _smart_pack(
    shapes: list[mesh_analysis.MeshBoundary],
    options: mesh_analysis.Options,
    debug_svg_root: Optional[ET.Element] = None,
) -> PackResult:
    """Try to pack as nicely as possible."""

    rectpack = _load_rectpack()

    try:
        sort_algo = getattr(rectpack, options.pack_sort)
    except AttributeError:
        raise ValueError(f"Unknown sorting algorithm {options.pack_sort!r}")

    packer = rectpack.newPacker(
        sort_algo=sort_algo,
        rotation=options.pack_may_rotate,
        bin_algo=rectpack.PackingBin.BBF,
    )

    pack_width = options.material_width - 2 * options.margin
    pack_length = options.material_length - 2 * options.margin
    packer.add_bin(_mm_to_int(pack_width), _mm_to_int(pack_length), count=float("inf"))

    for shape_idx, shape in enumerate(shapes):
        packer.add_rect(
            _mm_to_int(shape.aabb.width + 2 * options.shape_padding),
            _mm_to_int(shape.aabb.height + 2 * options.shape_padding),
            shape_idx,
        )
    packer.pack()

    if debug_svg_root is not None:
        svg_debug = ET.SubElement(debug_svg_root, "g", {"id": "smart-pack-debug"})
        for rect in packer.rect_list():
            _, x, y, w, h, shape_idx = rect
            shape = shapes[shape_idx]
            rect = ET.SubElement(svg_debug, "rect")
            rect.set("x", str(_int_to_mm(x)))
            rect.set("y", str(-_int_to_mm(y + h)))
            rect.set("width", str(_int_to_mm(w)))
            rect.set("height", str(_int_to_mm(h)))
            rect.set("fill", "none")
            rect.set("stroke", "teal")
            rect.set("stroke-width", "0.2")
            rect.set("id", f"debug-{shape.name}")

    covered_areas: list[float] = []
    packed_bounds = mesh_analysis.AABB()
    margin_shift = Vector((options.margin, options.margin))
    print("Rectangles:")
    bin_idx_max = 0
    for rect in packer.rect_list():
        print(f"    {rect}")
        bin_idx, x, y, w, h, shape_idx = rect

        padded_position = Vector((_int_to_mm(x), _int_to_mm(y)))
        padded_position.x += options.page_offset(bin_idx)
        padded_size = Vector((_int_to_mm(w), _int_to_mm(h)))
        packed_bounds.extend(padded_position)
        packed_bounds.extend(padded_position + padded_size)

        position = padded_position + margin_shift
        size = padded_size - 2 * margin_shift
        shape = shapes[shape_idx]
        shape.transform_into(position, size)
        shape.page_num = bin_idx
        covered_areas.append(padded_size.x * padded_size.y)
        bin_idx_max = max(bin_idx_max, bin_idx)

    return PackResult(
        canvas_bounds=packed_bounds,
        covered_area=sum(covered_areas),
        num_pages=bin_idx_max + 1,
    )


# Conversion functions for rectpack, it only handles integers.
def _mm_to_int(mm: float) -> int:
    """Convert float in millimeters to int in micrometers."""
    if not (float("-inf") < mm < float("inf")):
        raise ValueError("sizes must be finite")
    return int(mm * 1000)


def _int_to_mm(int_: int) -> float:
    """Convert int in micrometers to float in millimeters."""
    return int_ / 1000.0


def _load_rectpack() -> ModuleType:
    try:
        return sys.modules["rectpack"]
    except KeyError:
        pass

    old_syspath = sys.path[:]
    my_dir = Path(__file__).absolute().parent

    sys.path.append(str(my_dir / "rectpack-0.2.2-py3.9.egg"))
    rectpack = importlib.import_module("rectpack")
    sys.path = old_syspath

    return rectpack
