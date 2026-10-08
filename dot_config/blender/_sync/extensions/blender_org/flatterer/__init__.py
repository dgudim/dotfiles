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

bl_info = {
    "name": "Flatterer to SVG",
    "author": "Sybren A. Stüvel",
    "description": "Flat mesh to SVG exporter for laser cutters",
    "blender": (3, 5, 0),
    "version": (1, 6, 0),
    "location": "3D Viewport > side-panel > Export tab",
    "doc_url": "https://stuvel.eu/software/flatterer/",
    "tracker_url": "https://gitlab.com/dr.sybren/flatterer/-/issues",
    "warning": "",
    "category": "Import-Export",
    "support": "COMMUNITY",
}

is_first_load = "mesh_analysis" not in locals()
if is_first_load:
    from . import svg_export, mesh_analysis, gui, operators
else:
    import importlib

    gui = importlib.reload(gui)
    operators = importlib.reload(operators)
    svg_export = importlib.reload(svg_export)
    mesh_analysis = importlib.reload(mesh_analysis)

import bpy


def update_defaults(prefs: "FlattererPreferences", context: bpy.types.Context) -> None:
    _unregister_scene_props()
    _register_scene_props()


_pack_sort_items = [
    ("SORT_NONE", "No sorting", "Do not sort shapes before trying to pack them"),
    (
        "SORT_AREA",
        "Descending Area",
        "Sort shapes by descending area before trying to pack them",
    ),
    (
        "SORT_PERI",
        "Descending Perimeter",
        "Sort shapes by descending perimeter before trying to pack them",
    ),
    (
        "SORT_DIFF",
        "Difference Of Rectangle Sides",
        "Sort shapes by difference of rectangle sides before trying to pack them",
    ),
    (
        "SORT_SSIDE",
        "Shortest Side",
        "Sort shapes by shortest side before trying to pack them",
    ),
    (
        "SORT_LSIDE",
        "Longest Side",
        "Sort shapes by longest side before trying to pack them",
    ),
    (
        "SORT_RATIO",
        "Ratio Between Sides",
        "Sort shapes by ratio between sides before trying to pack them",
    ),
]


class FlattererPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    laser_width: bpy.props.FloatProperty(  # type: ignore
        name="Laser Beam Width",
        description="Compensate for material removed by the laser. Edges marked as 'sharp' will be "
        "moved by half this amount before exporting to SVG. The actual setting is stored on the "
        "Scene; this is just the default",
        default=0.16,
        min=0.0,
        max=10.0,
        soft_max=1.0,
        subtype="DISTANCE",
        unit="LENGTH",
        update=update_defaults,
    )

    material_width: bpy.props.FloatProperty(  # type: ignore
        name="Material Width",
        description="The shape packing will attempt to fill the material width. The actual setting is stored on the "
        "Scene; this is just the default",
        default=300.0,
        min=0.0,
        soft_max=500.0,
        subtype="DISTANCE",
        unit="LENGTH",
        update=update_defaults,
    )

    material_length: bpy.props.FloatProperty(  # type: ignore
        name="Material Length",
        description="The shape packing will attempt to fill the material length. The actual setting is stored on the "
        "Scene; this is just the default",
        default=300.0,
        min=0.0,
        soft_max=500.0,
        subtype="DISTANCE",
        unit="LENGTH",
        update=update_defaults,
    )

    margin: bpy.props.FloatProperty(  # type: ignore
        name="Margin",
        description="The distance from the edge of the material to the closest shape. The actual setting is stored "
        "on the Scene; this is just the default",
        default=5.0,
        min=0.0,
        soft_max=50.0,
        subtype="DISTANCE",
        unit="LENGTH",
        update=update_defaults,
    )

    material_thickness: bpy.props.FloatProperty(  # type: ignore
        name="Material Thickness",
        description="The thickness of the to-be-cut material. The actual setting is stored on the "
        "Scene; this is just the default",
        default=3.0,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        unit="LENGTH",
        update=update_defaults,
    )

    shape_padding: bpy.props.FloatProperty(  # type: ignore
        name="Shape Padding",
        description="The shape packing will keep this distance as padding around each shape. The padding will be "
        "double between shapes, and single between the shape and the outer edge of the document. The actual setting "
        "is stored on the Scene; this is just the default",
        default=1.0,
        min=0.0,
        max=50.0,
        soft_max=5.0,
        subtype="DISTANCE",
        unit="LENGTH",
        update=update_defaults,
    )
    pack_sort: bpy.props.EnumProperty(  # type: ignore
        name="Pack Sorting",
        items=_pack_sort_items,
        description="The shape packing will sort the bounding boxes of the shapes before trying to pack them. "
        "Different sorting approaches will be useful for different situations (square shapes vs. longer shapes, etc.). "
        "The actual setting is stored on the Scene; this is just the default",
        default="SORT_PERI",
        update=update_defaults,
    )
    pack_may_rotate: bpy.props.BoolProperty(  # type: ignore
        name="Allow Rotation",
        description="Whether the shape packing algorithm is allowed to rotate shapes by 90 degrees or not. "
        "The actual setting is stored on the Scene; this is just the default",
        default=True,
        update=update_defaults,
    )
    open_dir_after_export: bpy.props.BoolProperty(  # type: ignore
        name="Open Directory After Export",
        description="Open a file manager / explorer after the export to SVG has finished",
        default=True,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="This add-on assumes that 1 Blender unit is 1 mm.")

        col = layout.column(align=True)
        col.label(text="Preferences:")
        col.use_property_split = True
        col.prop(self, "open_dir_after_export")

        col = layout.column(align=True)
        col.label(text="Default settings:")
        col.use_property_split = True
        col.prop(self, "laser_width")
        col.prop(self, "material_width")
        col.prop(self, "material_length")
        col.prop(self, "material_thickness")
        col.prop(self, "margin")
        col.prop(self, "shape_padding")
        col.prop(self, "pack_sort")
        col.prop(self, "pack_may_rotate")

        col = layout.column(align=True)
        col.label(
            text="The actual settings are stored on the Scene; these are just the defaults."
        )
        col.label(
            text="New defaults will be in effect after the next Blender restart or add-on reload."
        )


classes = (FlattererPreferences,)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def _register_scene_props() -> None:
    prefs = bpy.context.preferences.addons[__package__].preferences
    bpy.types.Scene.flatterer_laser_width = bpy.props.FloatProperty(
        name="Laser Width",
        description="Compensate for material removed by the laser. Edges marked as 'sharp' will be "
        "moved by half this amount before exporting to SVG",
        default=prefs.laser_width,
        min=0.0,
        max=10.0,
        soft_max=1.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )
    bpy.types.Scene.flatterer_material_width = bpy.props.FloatProperty(
        name="Material Width",
        description="The shape packing will attempt to fill the material width",
        default=prefs.material_width,
        min=0.0,
        max=100000.0,
        soft_max=500.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )
    bpy.types.Scene.flatterer_material_length = bpy.props.FloatProperty(
        name="Material Length",
        description="The shape packing will attempt to fill the material length",
        default=prefs.material_length,
        min=0.0,
        max=100000.0,
        soft_max=500.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )
    bpy.types.Scene.flatterer_material_thickness = bpy.props.FloatProperty(
        name="Material Thickness",
        description="The thickness of the to-be-cut material",
        default=prefs.material_thickness,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )
    bpy.types.Scene.flatterer_margin = bpy.props.FloatProperty(
        name="Margin",
        description="The distance from the edge of the material to the closest shape",
        default=5.0,
        min=0.0,
        soft_max=50.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )
    bpy.types.Scene.flatterer_shape_padding = bpy.props.FloatProperty(
        name="Shape Padding",
        description="The shape packing will keep this distance as padding around each shape. The padding will be "
        "double between shapes, and single between the shape and the outer edge of the document",
        default=prefs.shape_padding,
        min=0.0,
        max=50.0,
        soft_max=5.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )

    bpy.types.Scene.flatterer_pack_sort = bpy.props.EnumProperty(
        name="Pack Sorting",
        items=_pack_sort_items,
        description="The shape packing will sort the bounding boxes of the shapes before trying to pack them. "
        "Different sorting approaches will be useful for different situations (square shapes vs. longer shapes, etc.)",
        default=prefs.pack_sort,
    )
    bpy.types.Scene.flatterer_pack_may_rotate = bpy.props.BoolProperty(
        name="Allow Rotation",
        description="Whether the shape packing algorithm is allowed to rotate shapes by 90 degrees or not",
        default=prefs.pack_may_rotate,
    )


def _unregister_scene_props() -> None:
    del bpy.types.Scene.flatterer_laser_width
    del bpy.types.Scene.flatterer_material_width
    del bpy.types.Scene.flatterer_material_length
    del bpy.types.Scene.flatterer_material_thickness
    del bpy.types.Scene.flatterer_margin
    del bpy.types.Scene.flatterer_shape_padding
    del bpy.types.Scene.flatterer_pack_sort
    del bpy.types.Scene.flatterer_pack_may_rotate


def register() -> None:
    _register()
    gui.register()
    operators.register()

    _register_scene_props()
    bpy.types.Object.flatterer_exclude = bpy.props.BoolProperty(
        name="Exclude from Export",
        description="This object will not be exported to SVG",
        default=False,
    )


def unregister() -> None:
    _unregister_scene_props()
    del bpy.types.Object.flatterer_exclude

    _unregister()
    gui.unregister()
    operators.unregister()
