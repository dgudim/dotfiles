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

from pathlib import Path
from collections import defaultdict

import bpy
import bmesh
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector


is_first_load = "svg_export" not in locals()
if is_first_load:
    from . import svg_export, mesh_analysis, straightener
else:
    import importlib

    svg_export = importlib.reload(svg_export)
    mesh_analysis = importlib.reload(mesh_analysis)
    straightener = importlib.reload(straightener)


class EXPORT_MESH_OT_svg_outline(bpy.types.Operator, ExportHelper):
    bl_idname = "export_mesh.svg_outline"
    bl_label = "Flatten to SVG Outline"
    bl_description = (
        "Export the outline of the selected mesh objects. "
        "MUST be planar meshes, possibly with holes"
    )
    bl_options = {"REGISTER"}  # No UNDO

    filename_ext = ".svg"

    export_shape_table: bpy.props.BoolProperty(  # type:ignore
        name="Shape Table",
        description="Include a table listing the shapes and their sizes",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return len(cls._exportable_objects(context)) > 0

    def execute(self, context: bpy.types.Context) -> set[str]:
        depsgraph = context.view_layer.depsgraph
        to_export = self._exportable_objects(context)

        scene = context.scene
        options = mesh_analysis.Options(
            laser_width=scene.flatterer_laser_width,
            material_width=scene.flatterer_material_width,
            material_length=scene.flatterer_material_length,
            margin=scene.flatterer_margin,
            shape_padding=scene.flatterer_shape_padding,
            pack_sort=scene.flatterer_pack_sort,
            pack_may_rotate=scene.flatterer_pack_may_rotate,
            shape_table=self.export_shape_table,
        )
        filepath = Path(self.filepath)
        try:
            canvas_size = svg_export.write(depsgraph, filepath, to_export, options)
        except svg_export.NoShapes:
            self.report({"ERROR"}, "No shapes to export, aborting.")
            return {"CANCELLED"}

        self.report(
            {"INFO"}, f"Created {canvas_size[0]} x {canvas_size[1]} mm SVG file"
        )

        prefs = context.preferences.addons[__package__].preferences
        if prefs.open_dir_after_export:
            bpy.ops.wm.path_open(filepath=str(filepath.parent))

        return {"FINISHED"}

    @staticmethod
    def _exportable_objects(context: bpy.types.Context) -> list[bpy.types.Object]:
        return [
            ob
            for ob in context.selected_objects
            if ob.type == "MESH" and not ob.flatterer_exclude
        ]


class FLATTERER_OT_setup_scene(bpy.types.Operator):
    bl_idname = "flatterer.setup_scene"
    bl_label = "Setup Scene for mm"
    bl_description = "Configure the Scene and 3D Viewport for mm units"

    def execute(self, context: bpy.types.Context) -> set[str]:
        # Configure the scene:
        s = context.scene
        s.unit_settings.scale_length = 0.001
        s.unit_settings.length_unit = "MILLIMETERS"

        # Configure the grid in 3D viewports:
        for win in context.window_manager.windows:
            for area in win.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                space_data = area.spaces.active
                space_data.overlay.grid_scale = 0.001

        return {"FINISHED"}


class FLATTERER_OT_add_solidify(bpy.types.Operator):
    bl_idname = "flatterer.add_solidify"
    bl_label = "Add Solidify Modifier"
    bl_description = "Add a solidify modifier to the selected mesh objects"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return any(
            ob.type == "MESH" and ob.mode == "OBJECT" for ob in context.selected_objects
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        for ob in context.selected_objects:
            if ob.type != "MESH":
                continue
            if ob.mode != "OBJECT":
                continue
            self.add_modifier(context, ob)
        return {"FINISHED"}

    def add_modifier(self, context: bpy.types.Context, ob: bpy.types.Object) -> None:
        mod = ob.modifiers.new("Solidify", "SOLIDIFY")
        mod.thickness = 0.001
        mod.offset = 1.0
        mod.use_even_offset = True
        mod.use_quality_normals = True
        mod.use_rim = True
        mod.use_rim_only = False
        mod.show_expanded = False
        mod.material_offset = 1
        mod.material_offset_rim = 1
        mod.show_in_editmode = False

        driver_rna_path = f'modifiers["{mod.name}"].thickness'
        ob.driver_remove(driver_rna_path)  # prevent double drivers
        fcurve = ob.driver_add(driver_rna_path)
        driver = fcurve.driver
        driver.expression = "thickness"
        dvar = driver.variables.new()
        dvar.name = "thickness"
        dvar.type = "SINGLE_PROP"
        dvar.targets[0].id_type = "SCENE"
        dvar.targets[0].id = context.scene
        dvar.targets[0].data_path = f"flatterer_material_thickness"


class FLATTERER_OT_select_export_edges(bpy.types.Operator):
    bl_idname = "flatterer.select_export_edges"
    bl_label = "Select Export Edges"
    bl_description = "Select all edges that will be exported to SVG"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return any(
            ob.type == "MESH" and ob.mode == "EDIT" for ob in context.selected_objects
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        for ob in context.selected_objects:
            if ob.type != "MESH":
                continue
            if ob.mode != "EDIT":
                continue
            mesh_analysis.select_export_edges(ob)
        return {"FINISHED"}


class FLATTERER_OT_island_faces(bpy.types.Operator):
    bl_idname = "flatterer.island_faces"
    bl_label = "Add Faces to Islands"
    bl_description = ""

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return any(
            ob.type == "MESH" and ob.mode == "EDIT" for ob in context.selected_objects
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        for ob in context.selected_objects:
            if ob.type != "MESH":
                continue
            if ob.mode != "EDIT":
                continue

            self.make_islands(ob.data)
        return {"FINISHED"}

    def make_islands(self, mesh: bpy.types.Mesh) -> None:
        vertex_indices = set(range(0, len(mesh.vertices)))

        while vertex_indices:
            bpy.ops.mesh.select_mode(type="VERT")
            bpy.ops.mesh.select_all(action="DESELECT")

            bpy.ops.object.mode_set(mode="OBJECT")
            for loop in mesh.loops:
                vertex_indices.discard(loop.vertex_index)

            if not vertex_indices:
                break

            unconnected_idx = vertex_indices.pop()
            mesh.vertices[unconnected_idx].select = True

            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_linked()
            bpy.ops.mesh.edge_face_add()


class FLATTERER_OT_straighten(bpy.types.Operator):
    bl_idname = "flatterer.align_to_local_axis"
    bl_label = "Align to Local Axis"
    bl_description = "Rotate the mesh so that it aligns with a local coordinate axis"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(  # type: ignore
        "Axis",
        items=[
            ("X", "X", "X-axis"),
            ("Y", "Y", "Y-axis"),
            ("Z", "Z", "Z-axis"),
        ],
    )

    def execute(self, context: bpy.types.Context) -> set[str]:
        user_count_before = context.object.data.users
        try:
            straightener.align_to_local_axis(context.object, self.axis)
        except straightener.AligningAxesError:
            self.report(
                {"WARNING"},
                f"Cannot rotate over the {self.axis} axis, as that is the normal of the mesh",
            )
            # Still return 'FINISHED' as 'CANCELLED' wouldn't show the redo panel.
            return {"FINISHED"}

        if user_count_before > 1 and context.object.data.users == 1:
            self.report(
                {"WARNING"},
                "This operation made a copy of the mesh, and it's now single-user",
            )

        return {"FINISHED"}


class FLATTERER_OT_extrude_finger(bpy.types.Operator):
    bl_idname = "flatterer.extrude_finger"
    bl_label = "Extrude Finger"
    bl_description = "Extrude selected geometry away from the face center"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return any(
            ob.type == "MESH" and ob.mode == "EDIT" for ob in context.objects_in_mode
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        length = context.scene.flatterer_material_thickness
        any_extrusion = False
        for ob in context.objects_in_mode:
            any_extrusion |= self.extrude_fingers(ob, length)

        if not any_extrusion:
            self.report({"ERROR"}, "No selected edges found")
            return {"CANCELLED"}

        # Toggle edit mode back & forth to prevent black faces.
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="EDIT")

        return {"FINISHED"}

    def extrude_fingers(self, object: bpy.types.Object, length: float) -> bool:
        """Returns whether any extrusion was done."""

        mesh = object.data
        bm = bmesh.from_edit_mesh(mesh)

        edges_per_tangent = defaultdict(list)

        # Find the edges to extrude, and the direction to do that in.
        for v in bm.verts:
            for l in v.link_loops:
                e = l.edge
                if e.is_wire or not e.select:
                    continue

                # Assumption: face lies to the left of the loop.
                v_other = e.other_vert(v)
                loop_vec = (v_other.co - v.co).normalized()
                tangent = loop_vec.cross(l.face.normal).normalized()

                edges_per_tangent[tangent.freeze()].append(e)

        # Check the result.
        if not edges_per_tangent:
            return False

        # Perform the extrusion.
        for tangent, edges in edges_per_tangent.items():
            extrude_vec = tangent * length
            geom = bmesh.ops.extrude_edge_only(bm, edges=edges)
            moved_verts = (v for v in geom["geom"] if isinstance(v, bmesh.types.BMVert))
            for vert in moved_verts:
                vert.co += extrude_vec

        # Update the edit mesh.
        bmesh.update_edit_mesh(mesh)
        object.update_from_editmode()

        return True


class FLATTERER_OT_separate_mesh(bpy.types.Operator):
    bl_idname = "flatterer.separate_mesh"
    bl_label = "Separate Mesh into Faces"
    bl_description = "Split up the mesh into an object per face"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        ob = context.edit_object
        in_edit_mode = ob and ob.type == "MESH" and ob.mode == "EDIT"
        return bool(in_edit_mode and bpy.ops.mesh.separate.poll())

    def execute(self, context: bpy.types.Context) -> set[str]:
        mesh = context.edit_object.data
        print("Splitting mesh:")
        while self.split_step(mesh):
            pass
        return {"FINISHED"}

    def split_step(self, mesh: bpy.types.Mesh) -> bool:
        face_indices_per_normal = defaultdict(set)

        # Group faces by their normal.
        for idx, normal in enumerate(mesh.polygon_normals):
            vec = Vector(
                (
                    round(normal.vector.x, 4),
                    round(normal.vector.y, 4),
                    round(normal.vector.z, 4),
                )
            ).freeze()

            face_indices_per_normal[vec].add(idx)

        if len(face_indices_per_normal) < 2:
            # Let's not split off the final group.
            return False

        # Split off the first group. After this, the face indices are all
        # changed anyway, so the entire analysis has to be done from scratch.
        vec, face_indices = face_indices_per_normal.popitem()

        # Select the faces in the group:
        bpy.ops.mesh.select_all(action="DESELECT")
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()  # Necessary after the first split.
        for idx in face_indices:
            face = bm.faces[idx]
            face.select = True
        bm.select_flush(True)
        bmesh.update_edit_mesh(mesh)

        bpy.ops.mesh.separate(type="SELECTED")

        # Toggle edit mode back & forth to ensure edit data is up to date.
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="EDIT")

        return True


class FLATTERER_OT_boolean_cut_active_from_selected(bpy.types.Operator):
    bl_idname = "flatterer.boolean_cut_active_from_selected"
    bl_label = "Cut Active from Selected"
    bl_description = (
        "Add Boolean modifiers to selected mesh objects to cut out the active object"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not cls._others(context):
            return False

        ob = context.object
        return bool(context.mode == "OBJECT" and ob and ob.type == "MESH")

    def execute(self, context: bpy.types.Context) -> set[str]:
        target = context.object

        for ob in self._others(context):
            mod = ob.modifiers.new("Bool Cut", "BOOLEAN")
            mod.object = target
            mod.operation = "DIFFERENCE"

            # Move the operator to before any Solidify modifier.
            with context.temp_override(object=ob):
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

        return {"FINISHED"}

    @staticmethod
    def _others(context: bpy.types.Context) -> list[bpy.types.Object]:
        ob = context.object
        return [
            other_ob
            for other_ob in context.selected_objects
            if other_ob.type == "MESH" and ob != other_ob
        ]


class FLATTERER_OT_boolean_cut_selected_from_active(bpy.types.Operator):
    bl_idname = "flatterer.boolean_cut_selected_from_active"
    bl_label = "Cut Selected from Active"
    bl_description = "Add Boolean modifiers to the active mesh object, to cut out the selected object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not cls._others(context):
            return False

        ob = context.object
        return bool(context.mode == "OBJECT" and ob and ob.type == "MESH")

    def execute(self, context: bpy.types.Context) -> set[str]:
        active = context.object

        for index, target in enumerate(self._others(context)):
            mod = active.modifiers.new("Bool Cut", "BOOLEAN")
            mod.object = target
            mod.operation = "DIFFERENCE"

            # Move the operator to before any Solidify modifier.
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=index)

        return {"FINISHED"}

    @staticmethod
    def _others(context: bpy.types.Context) -> list[bpy.types.Object]:
        ob = context.object
        return [
            other_ob
            for other_ob in context.selected_objects
            if other_ob.type == "MESH" and ob != other_ob
        ]


classes = (
    EXPORT_MESH_OT_svg_outline,
    FLATTERER_OT_setup_scene,
    FLATTERER_OT_add_solidify,
    FLATTERER_OT_select_export_edges,
    FLATTERER_OT_island_faces,
    FLATTERER_OT_straighten,
    FLATTERER_OT_extrude_finger,
    FLATTERER_OT_separate_mesh,
    FLATTERER_OT_boolean_cut_active_from_selected,
    FLATTERER_OT_boolean_cut_selected_from_active,
)
register, unregister = bpy.utils.register_classes_factory(classes)
