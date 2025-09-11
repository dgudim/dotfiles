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

from typing import Iterable, Iterator
from pathlib import Path
import contextlib
import copy
import math
import xml.etree.ElementTree as ET

import bpy
from mathutils import Vector

is_first_load = "mesh_analysis" not in locals()
if is_first_load:
    from . import mesh_analysis, packing
else:
    import importlib

    mesh_analysis = importlib.reload(mesh_analysis)
    packing = importlib.reload(packing)

float2 = tuple[float, float]

# <?xml version="1.0" encoding="UTF-8" standalone="no"?>
# <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
# <svg width="391" height="391" viewBox="-70.5 -70.5 391 391" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
# <rect fill="#fff" stroke="#000" x="-70" y="-70" width="390" height="390"/>
# <g opacity="0.8">
#   <rect x="25" y="25" width="200" height="200" fill="lime" stroke-width="4" stroke="pink" />
#   <circle cx="125" cy="125" r="75" fill="orange" />
#   <polyline points="50,150 50,200 200,200 200,100" stroke="red" stroke-width="4" fill="none" />
#   <line x1="50" y1="50" x2="200" y2="200" stroke="blue" stroke-width="4" />
# </g>
# </svg>

NS_SVG = "http://www.w3.org/2000/svg"
NS_SODIPODI = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
NS_INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"


colors = {
    mesh_analysis.MeshType.CUT.name: "red",
    mesh_analysis.MeshType.ENGRAVE.name: "blue",
}


class NoShapes(RuntimeError):
    """Raised when there are no shapes to export."""


def write(
    depsgraph: bpy.types.Depsgraph,
    out_path: Path,
    objects: Iterable[bpy.types.Object],
    options: mesh_analysis.Options,
) -> tuple[int, int]:
    """Export the objects to an SVG file.

    \returns the canvas size of the resulting SVG file, in entire Blender units (assumed mm).
    """
    shapes = _collect_shapes(depsgraph, objects, options)

    ET.register_namespace("", NS_SVG)
    ET.register_namespace("sodipodi", NS_SODIPODI)
    ET.register_namespace("inkscape", NS_INKSCAPE)
    root = ET.Element("svg", {"version": "1.1"})

    # pack_result = packing.pack(shapes, options, debug_svg_root=root)
    pack_result = packing.pack(shapes, options)

    if not pack_result:
        raise NoShapes("No shapes to pack")

    _write_document_sizes(root, options, pack_result)

    # Create an SVG layer per page.
    page_layers = [
        _layer(root, f"page-{page_idx}", f"Page {page_idx}")
        for page_idx in range(1, pack_result.num_pages + 1)
    ]

    # Export shapes
    for shape in shapes:
        layer = page_layers[shape.page_num]
        _write_shape(layer, shape)

    # Export annotations
    if options.shape_table:
        layer_annotations = _layer(root, "layer-annotations", "Annotations")
        _write_shape_table(layer_annotations, shapes, options)
        # _write_shape_labels(layer_annotations, shapes, options)

    tree = ET.ElementTree(root)
    with out_path.open("wb") as outfile:
        tree.write(
            outfile,
            encoding="utf-8",
            xml_declaration=True,
        )

    width = int(options.page_offset(pack_result.num_pages))
    height = int(options.material_length)
    return width, height


def _write_document_sizes(
    root: ET.Element,
    options: mesh_analysis.Options,
    pack_result: packing.PackResult,
) -> None:
    # canvas_size = _compute_canvas_size(pack_result.canvas_bounds, options)
    page_size: tuple[float, float] = (
        int(round(options.material_width)),
        int(round(options.material_length)),
    )
    root.set("width", f"{page_size[0]}mm")
    root.set("height", f"{page_size[1]}mm")
    root.set(
        "viewBox",
        f"0 {-page_size[1]} {page_size[0]} {page_size[1]}",
    )

    #   <sodipodi:namedview>
    #     <inkscape:page
    #        x="0"
    #        y="0"
    #        width="210"
    #        height="297"
    #        id="page377" />
    #     <inkscape:page
    #        x="220"
    #        y="0"
    #        width="210"
    #        height="297"
    #        id="page379" />
    #   </sodipodi:namedview>

    namedview = ET.SubElement(root, "{%s}namedview" % NS_SODIPODI)
    for page_idx in range(pack_result.num_pages):
        ET.SubElement(
            namedview,
            "{%s}page" % NS_INKSCAPE,
            {
                "id": f"page{page_idx}",
                "x": str(options.page_offset(page_idx)),
                "y": "0",
                "width": str(page_size[0]),
                "height": str(page_size[1]),
            },
        )


def _collect_shapes(
    depsgraph: bpy.types.Depsgraph,
    objects: Iterable[bpy.types.Object],
    options: mesh_analysis.Options,
) -> list[mesh_analysis.MeshBoundary]:
    """Convert meshes to 2D shapes and their AABBs."""
    shapes: list[mesh_analysis.MeshBoundary] = []
    for object in objects:
        with _solidify_disabled(depsgraph, object) as ob_eval:
            mesh_boundary = mesh_analysis.flatten_mesh(ob_eval, options)
            shapes.append(mesh_boundary)
    return shapes


def _write_shape(
    root: ET.Element,
    shape: mesh_analysis.MeshBoundary,
) -> None:
    ob_group = ET.SubElement(root, "g", {"id": shape.name})

    # print("_write_shape:")
    poly_iter = shape.polygons_by_type()
    for mesh_idx, (mesh_type, flat_mesh) in enumerate(poly_iter):
        points = " ".join(f"{v.x:.6},{-v.y:.6}" for v in flat_mesh.iter_points())
        # print(f"poly: {points}  (closed={poly_closed})" )

        svg_element = "polygon" if flat_mesh.is_closed else "polyline"
        polygon = ET.SubElement(ob_group, svg_element)
        polygon.set("points", points)
        polygon.set("fill", "none")
        polygon.set("stroke", colors[mesh_type.name])
        polygon.set("stroke-width", "0.1mm")
        polygon.set("id", f"{shape.name}-p{mesh_idx}")

    ob_group.set(
        "transform",
        f"translate({shape.translation.x:.6},{-shape.translation.y:.6}) "
        f"rotate({shape.rotation}) ",
    )


def _layer(
    root: ET.Element,
    layer_id: str,
    layer_name: str,
) -> ET.Element:
    return ET.SubElement(
        root,
        "g",
        {
            "id": layer_id,
            "inkscape:groupmode": "layer",
            "inkscape:label": layer_name,
        },
    )


def _write_shape_table(
    root: ET.Element,
    shapes: list[mesh_analysis.MeshBoundary],
    options: mesh_analysis.Options,
) -> None:
    # Construct the table data as (name, width, height) list.
    table: list[tuple[str, str, str, str]] = []
    for shape in shapes:
        w = shape.aabb.width - options.laser_width
        h = shape.aabb.height - options.laser_width
        surface = (w / 1000.0) * (h / 1000.0)
        item = (shape.name, f"{w:.0f}", f"{h:.0f}", f"{surface:.3f}")
        table.append(item)

    table.sort()  # sort by name
    table.insert(0, ("Shape", "Width (mm)", "Height (mm)", "Surface (m²)"))

    svg_group = ET.SubElement(root, "g", {"id": "flatterer-shape-table"})

    colour = "#f36926"
    columns = [5, 100, 150, 200]
    box_top = 10
    box_width = columns[-1] + box_top
    line_height = 9
    for row_idx, row in enumerate(table):
        y = (row_idx + 2) * line_height

        if row_idx < len(table) - 1:
            line_y = y + 2
            outline = ET.SubElement(
                svg_group,
                "line",
                {
                    "x1": f"{0}",
                    "y1": f"{line_y}",
                    "x2": f"{box_width}",
                    "y2": f"{line_y}",
                    "stroke": colour,
                    "stroke-width": "0.1mm",
                },
            )

        font_weight = "bold" if row_idx == 0 else "normal"
        font_style = f'font-size:4pt; font-family:"Noto Sans", sans-serif; font-weight:{font_weight}'

        for row_idx, value in enumerate(row):
            x = columns[row_idx]
            txt_elt = ET.SubElement(svg_group, "text")
            txt_elt.set("x", f"{x}")
            txt_elt.set("y", f"{y}")
            txt_elt.set("style", font_style)
            if row_idx > 0:
                txt_elt.set("text-anchor", "end")
            txt_elt.text = f"{value}"

    outline = ET.SubElement(svg_group, "rect")
    outline.set("x", "0")
    outline.set("y", f"{box_top}")
    outline.set("width", f"{box_width}")
    outline.set("height", f"{(len(table) + 0.5) * line_height}")
    outline.set("fill", "none")
    outline.set("stroke", colour)
    outline.set("stroke-width", "0.3mm")


def _write_shape_labels(
    root: ET.Element,
    shapes: list[mesh_analysis.MeshBoundary],
    options: mesh_analysis.Options,
) -> None:
    font_style = f'font-size:3pt; font-family:"Noto Sans", sans-serif'

    for shape in shapes:
        label_x = shape.aabb.mid_x
        label_y = shape.aabb.mid_y

        txt_elt = ET.SubElement(
            root,
            "text",
            {
                "x": f"{label_x}mm",
                "y": f"{-label_y}mm",
                "style": font_style,
                "text-anchor": "middle",
                "writing-mode": "tb" if shape.aabb.width < shape.aabb.height else "lr",
            },
        )
        txt_elt.text = shape.name


@contextlib.contextmanager
def _solidify_disabled(
    depsgraph: bpy.types.Depsgraph, object: bpy.types.Object
) -> Iterator[bpy.types.Object]:
    modifier_state = _solidify_disable(object)
    try:
        depsgraph.update()
        yield object.evaluated_get(depsgraph)
    finally:
        _solidify_enable(object, modifier_state)


def _solidify_disable(object: bpy.types.Object) -> dict[str, bool]:
    modifier_state = {}
    for modifier in _solidify_modifiers(object):
        modifier_state[modifier.name] = modifier.show_viewport
        if not modifier.show_viewport:
            continue
        object.update_tag(refresh={"OBJECT", "DATA"})
        modifier.show_viewport = False
    return modifier_state


def _solidify_enable(object: bpy.types.Object, modifier_state: dict[str, bool]) -> None:
    for modifier in _solidify_modifiers(object):
        modifier.show_viewport = modifier_state[modifier.name]


def _solidify_modifiers(object: bpy.types.Object) -> Iterable[bpy.types.Modifier]:
    for modifier in object.modifiers:
        if modifier.type == "SOLIDIFY":
            yield modifier
