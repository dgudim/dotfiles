bl_info = {
    "name": "Aligning Horizontally Mini",
    "author": "KSYN",
    "version": (1, 0, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Object",
    "description": "Aligns selected objects in a grid",
    "warning": "",
    "wiki_url": "",
    "category": "Object",
}

import bpy
import math
from collections import defaultdict

class OBJECT_OT_ArrangeObjectsInGrid(bpy.types.Operator):
    bl_idname = "object.aligning_horizontally_mini"
    bl_label = "Aligning Horizontally Mini"
    bl_description = "Aligns selected objects in a virtual cubic grid"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator property to specify the split character (default is period)
    split_char: bpy.props.StringProperty(name="Split Character", default=".") # type: ignore

    x_count: bpy.props.IntProperty(
        name="X-axis Count",
        description="Number of objects to place on the X-axis",
        default=3,
        min=1
    ) # type: ignore
    
    y_count: bpy.props.IntProperty(
        name="Y-axis Count",
        description="Number of objects to place on the Y-axis",
        default=3,
        min=1
    ) # type: ignore
    
    spacing_x: bpy.props.FloatProperty(
        name="X-axis Spacing",
        description="Space between objects on the X-axis",
        default=2.0,
        min=0.1
    ) # type: ignore
    
    spacing_y: bpy.props.FloatProperty(
        name="Y-axis Spacing",
        description="Space between objects on the Y-axis",
        default=2.0,
        min=0.1
    ) # type: ignore
    
    spacing_z: bpy.props.FloatProperty(
        name="Z-axis Spacing",
        description="Space between objects on the Z-axis",
        default=2.0,
        min=0.1
    ) # type: ignore

    sort_active_first: bpy.props.BoolProperty(
        name="Active Object First",
        description="Sort the active object to the front",
        default=False
    ) # type: ignore

    pass_active: bpy.props.BoolProperty(
        name="Pass Active Objects",
        description="If True, active objects will be removed from groups",
        default=False
    ) # type: ignore

    group_by_name: bpy.props.BoolProperty(
        name="Group by Name",
        description="Group and align objects based on their names",
        default=False
    ) # type: ignore

    group_placement_direction: bpy.props.EnumProperty(
        name="Group Placement Direction",
        description="Specify the direction to place each group",
        items=[
            ('X+', "X+", "Place in positive X direction"),
            ('X-', "X-", "Place in negative X direction"),
            ('Y+', "Y+", "Place in positive Y direction"),
            ('Y-', "Y-", "Place in negative Y direction"),
            ('Z+', "Z+", "Place in positive Z direction"),
            ('Z-', "Z-", "Place in negative Z direction"),
        ],
        default='X+'
    ) # type: ignore
    
    group_info: bpy.props.StringProperty(
        name="Group Information",
        description="Group order and object count",
        default=""
    ) # type: ignore

    def execute(self, context):
        selected_objects = list(context.selected_objects)
        selected_objects = sorted(selected_objects, key=lambda obj: obj.name)

        active_object = context.active_object

        if not selected_objects or not active_object:
            self.report({'WARNING'}, "No objects selected or no active object")
            return {'CANCELLED'}

        if self.sort_active_first:
            # Move active object to the front of the list
            selected_objects.remove(active_object)
            selected_objects.insert(0, active_object)

        # Group objects by name if option is selected
        if self.group_by_name:
            grouped_objects = self.group_objects_by_name(selected_objects)
        else:
            grouped_objects = {'All Objects': selected_objects}
        
        # Initialize group information
        group_info_list = []
        
        # Initial position
        current_position = active_object.location.copy()

        # Remove active object from the list if pass_active is True
        if self.pass_active:
            if active_object:
                for group_name, objects in grouped_objects.items():
                    if active_object in objects:
                        objects.remove(active_object)
        
        # Align for each group
        for group_name, objects in grouped_objects.items():
            # Align to the current group position
            positions = self.calculate_grid_positions(len(objects), current_position)
            for obj, pos in zip(objects, positions):
                obj.location = pos
            
            # Calculate initial position for the next group
            max_x, max_y, max_z = self.calculate_max_dimensions(len(objects))
            group_info_list.append(f"Group: {group_name}, Objects: {len(objects)}, Z count: {max_z}")
            
            if self.group_placement_direction == 'X+':
                current_position.x += max_x * self.spacing_x
            elif self.group_placement_direction == 'X-':
                current_position.x -= max_x * self.spacing_x
            elif self.group_placement_direction == 'Y+':
                current_position.y += max_y * self.spacing_y
            elif self.group_placement_direction == 'Y-':
                current_position.y -= max_y * self.spacing_y
            elif self.group_placement_direction == 'Z+':
                current_position.z += max_z * self.spacing_z
            elif self.group_placement_direction == 'Z-':
                current_position.z -= max_z * self.spacing_z

        # Store group information in the property
        self.group_info = "\n".join(group_info_list)

        self.report({'INFO'}, "Objects aligned in grid")
        return {'FINISHED'}

    def calculate_grid_positions(self, total_objects, origin):
        """Calculate virtual cubic point cloud based on the given number of objects"""
        x_count = self.x_count
        y_count = self.y_count
        
        # Calculate Z-axis count
        z_count = math.ceil(total_objects / (x_count * y_count))
        
        positions = []

        for z in range(z_count):
            for y in range(y_count):
                for x in range(x_count):
      
                    if len(positions) < total_objects:
                        if self.group_placement_direction == 'X-':
                            positions.append((
                                origin.x + -x * self.spacing_x,
                                origin.y + y * self.spacing_y,
                                origin.z + z * self.spacing_z
                            ))
                        elif self.group_placement_direction == 'Y-':
                            positions.append((
                                origin.x + x * self.spacing_x,
                                origin.y + -y * self.spacing_y,
                                origin.z + z * self.spacing_z
                            ))
                        elif self.group_placement_direction == 'Z-':
                            positions.append((
                                origin.x + x * self.spacing_x,
                                origin.y + y * self.spacing_y,
                                origin.z + -z * self.spacing_z
                            ))
                        else:
                            positions.append((
                                origin.x + x * self.spacing_x,
                                origin.y + y * self.spacing_y,
                                origin.z + z * self.spacing_z
                            ))
        return positions

    def calculate_max_dimensions(self, total_objects):
        """Calculate maximum X, Y, Z values from the number of objects"""
        x_count = self.x_count
        y_count = self.y_count
        
        z_count = math.ceil(total_objects / (x_count * y_count))
        
        max_x = min(total_objects, x_count)
        max_y = min(math.ceil(total_objects / x_count), y_count)
        max_z = z_count
        
        return max_x, max_y, max_z

    def group_objects_by_name(self, objects):
        """Group objects by name"""
        groups = defaultdict(list)
        
        for obj in objects:
            # Use the first part of the name (up to numbers or specific string) as the group key
            group_key = obj.name.split(self.split_char)[0]
            groups[group_key].append(obj)
        
        return groups
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        
        # Draw operator properties
        col.prop(self, "x_count")
        col.prop(self, "y_count")
        col.prop(self, "spacing_x")
        col.prop(self, "spacing_y")
        col.prop(self, "spacing_z")
        col.prop(self, "pass_active")
        col.prop(self, "sort_active_first")
        col.prop(self, "group_by_name")
        col.prop(self, "group_placement_direction")
        col.prop(self, "split_char")
        
        # Draw group information
        if self.group_info:
            col.label(text="Group Information:")
            lines = self.group_info.splitlines()

            # Display only the first 10 lines
            for i, line in enumerate(lines):
                if i < 10:
                    col.label(text=line)
                else:
                    col.label(text="...omitted")  # Display explanation text if more than 10 lines
                    break


# Class registration
classes = [
    OBJECT_OT_ArrangeObjectsInGrid,
]


# Register operator in Blender
def menu_func(self, context):
    self.layout.separator()
    self.layout.operator(OBJECT_OT_ArrangeObjectsInGrid.bl_idname)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_transform_object.append(menu_func)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.VIEW3D_MT_transform_object.remove(menu_func)

if __name__ == "__main__":
    register()