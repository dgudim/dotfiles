# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2013-2022 Campbell Barton
# SPDX-FileCopyrightText: 2017-2025 Mikhail Rachinskiy

import bmesh
from bpy.types import Object, Panel

from . import report


def _is_mesh(ob: Object) -> bool:
    return ob is not None and ob.type == "MESH"


class Sidebar:
    bl_category = "3D Print"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.mode in {"OBJECT", "EDIT_MESH"}


class VIEW3D_PT_print3d_analyze(Sidebar, Panel):
    bl_label = "Analyze"

    _type_to_icon = {
        bmesh.types.BMVert: "VERTEXSEL",
        bmesh.types.BMEdge: "EDGESEL",
        bmesh.types.BMFace: "FACESEL",
    }

    def draw_report(self, context):
        layout = self.layout
        info = report.info()

        if info:
            is_edit = context.edit_object is not None

            row = layout.row()
            row.label(text="Result")
            row.operator("wm.print3d_report_clear", text="", icon="X")

            box = layout.box()
            col = box.column()

            for i, (text, data) in enumerate(info):
                if is_edit and data and data[1]:
                    bm_type, _bm_array = data
                    col.operator("mesh.print3d_select_report", text=text, icon=self._type_to_icon[bm_type],).index = i
                else:
                    col.label(text=text)

    def draw(self, context):
        layout = self.layout
        layout.enabled = _is_mesh(context.object)

        props = context.scene.print3d_toolbox

        layout.label(text="Statistics")

        row = layout.row(align=True)
        row.operator("mesh.print3d_info_volume", text="Volume")
        row.operator("mesh.print3d_info_area", text="Area")

        layout.label(text="Checks")

        col = layout.column(align=True)
        col.operator("mesh.print3d_check_solid")
        col.operator("mesh.print3d_check_intersect")
        row = col.row(align=True)
        row.operator("mesh.print3d_check_degenerate")
        row.prop(props, "threshold_zero", text="")
        row = col.row(align=True)
        row.operator("mesh.print3d_check_nonplanar")
        row.prop(props, "angle_nonplanar", text="")
        row = col.row(align=True)
        row.operator("mesh.print3d_check_thick")
        row.prop(props, "thickness_min", text="")
        row = col.row(align=True)
        row.operator("mesh.print3d_check_sharp")
        row.prop(props, "angle_sharp", text="")
        row = col.row(align=True)
        row.operator("mesh.print3d_check_overhang")
        row.prop(props, "angle_overhang", text="")

        layout.operator("mesh.print3d_check_all")

        self.draw_report(context)


class VIEW3D_PT_print3d_cleanup(Sidebar, Panel):
    bl_label = "Clean Up"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.enabled = _is_mesh(context.object)
        layout.operator("mesh.print3d_clean_non_manifold")


class VIEW3D_PT_print3d_edit(Sidebar, Panel):
    bl_label = "Edit"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        is_mesh = _is_mesh(context.object)

        layout.operator("mesh.print3d_hollow")

        row = layout.row()
        row.enabled = is_mesh
        row.operator("object.print3d_align_xy")

        layout.label(text="Scale To")
        row = layout.row(align=True)
        row.enabled = is_mesh
        row.operator("mesh.print3d_scale_to_volume", text="Volume")
        row.operator("mesh.print3d_scale_to_bounds", text="Bounds")


class VIEW3D_PT_print3d_export(Sidebar, Panel):
    bl_label = "Export"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        props = context.scene.print3d_toolbox

        layout.prop(props, "export_path", text="")
        layout.prop(props, "export_format")

        layout.operator("export_scene.print3d_export", icon="EXPORT")

        header, panel = layout.panel("options", default_closed=True)
        header.label(text="Options")
        if panel:
            col = panel.column(heading="General")
            sub = col.column()
            sub.active = props.export_format != "OBJ"
            sub.prop(props, "use_ascii_format")
            col.prop(props, "use_scene_scale")

            col = panel.column(heading="Geometry")
            col.active = props.export_format != "STL"
            col.prop(props, "use_uv")
            col.prop(props, "use_normals", text="Normals")
            col.prop(props, "use_colors", text="Colors")

            col = panel.column(heading="Materials")
            col.prop(props, "use_copy_textures")
