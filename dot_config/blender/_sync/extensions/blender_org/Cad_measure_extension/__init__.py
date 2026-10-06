bl_info = {
    "name": "Cad<Measure",
    "author": "Mr.Nobody",
    "version": (0, 0, 1),
    "blender": (4, 4, 1),
    "location": "3D Viewport > Sidebar > Cad<Measure",
    "description": "Cad like measuring tool for blender",
    "category": "Development",
}

import bpy
import os
import math

def import_node_group(blend_path, group_node_name, link=True):
    existing_node_tree = bpy.data.node_groups.get(group_node_name)
    if existing_node_tree:
        return existing_node_tree

    if not os.path.exists(blend_path):
        print(f"Blend file not found: {blend_path}")
        return None

    if link:
        with bpy.data.libraries.load(blend_path, link=True) as (data_from, data_to):
            if group_node_name in data_from.node_groups:
                data_to.node_groups.append(group_node_name)

    ng = bpy.data.node_groups.get(group_node_name)
    if ng:
        ng.use_fake_user = True
    else:
        print(f"❌ Error: Node tree '{group_node_name}' not found after linking.")
    return ng

def add_cad_measure_obj(size, gn_asset_name):
    bpy.ops.mesh.primitive_plane_add(size=size)
    obj = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.merge(type='CENTER')
    bpy.ops.object.mode_set(mode='OBJECT')

    mod = obj.modifiers.new(name="Measuring tool", type="NODES")
    mod.node_group = bpy.data.node_groups.get(gn_asset_name)
    return obj

class MESH_OT_add_cad_measure_single(bpy.types.Operator):
    bl_idname = "mesh.add_cad_measure_single"
    bl_label = "Add CAD Measurement Tool"
    bl_description = "Adds a CAD like dimension tool"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if bpy.context.object and bpy.context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        gn_path = os.path.join(os.path.dirname(__file__), "Node", "Cad V2.0.blend")
        gn_asset_name = "Measurement tool"

        import_node_group(gn_path, gn_asset_name, True)
        obj = add_cad_measure_obj(4.0, gn_asset_name)
        obj.name = "CAD_Measure"
        obj.rotation_euler = (0.0, 0.0, 0.0)

        ts = context.scene.tool_settings
        ts.use_snap = True
        ts.snap_elements = {'VERTEX', 'EDGE', 'EDGE_MIDPOINT'}

        bpy.ops.object.mode_set(mode='EDIT')
        return {"FINISHED"}

class MESH_OT_add_cad_tool_generic(bpy.types.Operator):
    bl_idname = "mesh.add_cad_tool_generic"
    bl_label = "Add CAD Tool"
    bl_options = {"REGISTER", "UNDO"}

    tool_name: bpy.props.StringProperty()

    def execute(self, context):
        if bpy.context.object and bpy.context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        gn_path = os.path.join(os.path.dirname(__file__), "Node", "Cad V2.0.blend")
        import_node_group(gn_path, self.tool_name, True)

        obj = add_cad_measure_obj(4.0, self.tool_name)
        obj.name = f"CAD_{self.tool_name.replace(' ', '_')}"
        obj.rotation_euler = (0.0, 0.0, 0.0)

        ts = context.scene.tool_settings
        ts.use_snap = True
        ts.snap_elements = {'VERTEX', 'EDGE', 'EDGE_MIDPOINT'}

        bpy.ops.object.mode_set(mode='EDIT')
        return {"FINISHED"}

class MESH_OT_add_angle_tool(MESH_OT_add_cad_tool_generic):
    bl_idname = "mesh.add_angle_tool"
    bl_label = "Add Angle Tool"
    bl_description = "Adds an angle tool. (DEMO, only works with three vertex mesh, index specific 0 2 1, in that order)"

    def execute(self, context):
        self.tool_name = "Angle tool (DEMO)"
        return super().execute(context)

class MESH_OT_add_axis_tool(MESH_OT_add_cad_tool_generic):
    bl_idname = "mesh.add_axis_tool"
    bl_label = "Add Axis Tool"
    bl_description = "Adds an axis tool."

    def execute(self, context):
        self.tool_name = "Axis tool"
        return super().execute(context)

class MESH_OT_add_level_dimension_tool(MESH_OT_add_cad_tool_generic):
    bl_idname = "mesh.add_level_dimension_tool"
    bl_label = "Add Level Dimension Tool"
    bl_description = "Adds a Height dimension tool that tells the height from world origin (Don't apply location)"

    def execute(self, context):
        self.tool_name = "Level dimension tool"
        return super().execute(context)

class VIEW3D_OT_cadify_viewport(bpy.types.Operator):
    bl_idname = "view3d.cadify_viewport"
    bl_label = "CADIFY Viewport"
    bl_description = "Toggle CAD-like viewport settings"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        cad_mode = scene.get("cad_mode", False)

        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        if not cad_mode:
                            space.shading.light = "FLAT"
                            space.shading.background_type = "VIEWPORT"
                            space.shading.background_color = (1, 1, 1)
                            space.shading.color_type = 'MATERIAL'
                        else:
                            space.shading.light = "STUDIO"
                            space.shading.background_type = "THEME"
                            space.shading.color_type = 'OBJECT'

        world = bpy.data.worlds.get("World")
        if not world:
            world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
        world.use_nodes = False
        world.color = (1, 1, 1) if not cad_mode else (0.05, 0.05, 0.05)

        scene["cad_mode"] = not cad_mode
        return {'FINISHED'}

class VIEW3D_PT_my_custom_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cad<Measure"
    bl_label = "Cad<Measure"

    def draw(self, context):
        layout = self.layout
        layout.operator("view3d.cadify_viewport", text="CADIFY")
        layout.separator()

        layout.label(text="Add CAD Tools:")
        layout.operator("mesh.add_cad_measure_single", text="Add Measurement Tool")
        layout.operator("mesh.add_angle_tool", text="Add Angle Tool")
        layout.operator("mesh.add_axis_tool", text="Add Axis Tool")
        layout.operator("mesh.add_level_dimension_tool", text="Add Level Dimension Tool")

# Centralized class registration
classes = (
    VIEW3D_PT_my_custom_panel,
    MESH_OT_add_cad_measure_single,
    MESH_OT_add_cad_tool_generic,
    MESH_OT_add_angle_tool,
    MESH_OT_add_axis_tool,
    MESH_OT_add_level_dimension_tool,
    VIEW3D_OT_cadify_viewport,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
