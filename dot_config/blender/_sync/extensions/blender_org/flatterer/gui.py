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

import bpy


class FlattererPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Export"


class FLATTERER_PT_sidepanel(FlattererPanel, bpy.types.Panel):
    bl_label = "Flatterer"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(context.scene, "flatterer_laser_width")
        col.prop(context.scene, "flatterer_material_width")
        col.prop(context.scene, "flatterer_material_length")
        col.prop(context.scene, "flatterer_material_thickness")
        col.prop(context.scene, "flatterer_margin")
        col.prop(context.scene, "flatterer_shape_padding")
        col.operator("flatterer.setup_scene")

        col = layout.column(align=True)
        col.use_property_split = False
        col.label(text="Packing Options:")
        col.prop(context.scene, "flatterer_pack_may_rotate")
        col.prop(context.scene, "flatterer_pack_sort", text="")

        layout.operator("export_mesh.svg_outline")


class FLATTERER_PT_objects(FlattererPanel, bpy.types.Panel):
    bl_label = "Object Options"
    bl_parent_id = "FLATTERER_PT_sidepanel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.object)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        col = layout.column(align=True)
        col.prop(context.object, "flatterer_exclude")
        col.operator("flatterer.add_solidify", icon="MOD_SOLIDIFY")
        col.operator("flatterer.align_to_local_axis", icon="EMPTY_AXIS")
        col.operator("flatterer.boolean_cut_active_from_selected", icon="MOD_BOOLEAN")
        col.operator("flatterer.boolean_cut_selected_from_active", icon="MOD_BOOLEAN")


class FLATTERER_PT_edges(FlattererPanel, bpy.types.Panel):
    bl_label = "Edge Options"
    bl_parent_id = "FLATTERER_PT_sidepanel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.object and context.mode == "EDIT_MESH")

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

        col = layout.column(align=True)
        row = col.row(align=True)
        row.split(factor=0.8)
        row.label(text="Kerf Compensation")
        row.operator("mesh.mark_seam", text="", icon="X").clear = False
        row.operator("mesh.mark_seam", text="", icon="CHECKMARK").clear = True

        row = col.row(align=True)
        row.split(factor=0.8)
        row.label(text="Engrave")
        row.operator("mesh.mark_sharp", text="", icon="X").clear = True
        row.operator("mesh.mark_sharp", text="", icon="CHECKMARK").clear = False

        col = layout.column(align=True)
        col.operator("flatterer.select_export_edges")
        col.operator("flatterer.separate_mesh")
        col.operator("flatterer.extrude_finger")


def export_menu(
    self: bpy.types.TOPBAR_MT_file_export, context: bpy.types.Context
) -> None:
    self.layout.operator("export_mesh.svg_outline")


classes = (
    FLATTERER_PT_sidepanel,
    FLATTERER_PT_objects,
    FLATTERER_PT_edges,
)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register() -> None:
    _register()
    bpy.types.TOPBAR_MT_file_export.append(export_menu)


def unregister() -> None:
    _unregister()
    bpy.types.TOPBAR_MT_file_export.remove(export_menu)
