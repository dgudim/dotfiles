# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2013-2024 Campbell Barton
# SPDX-FileCopyrightText: 2016-2025 Mikhail Rachinskiy

import math

from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy.types import PropertyGroup

from . import report


class SceneProperties(PropertyGroup):

    # Analyze
    # -------------------------------------

    threshold_zero: FloatProperty(
        name="Limit",
        subtype="DISTANCE",
        default=0.0001,
        min=0.0,
        max=0.2,
        precision=5,
        step=0.01
    )
    angle_nonplanar: FloatProperty(
        name="Limit",
        subtype="ANGLE",
        default=math.radians(5.0),
        min=0.0,
        max=math.radians(180.0),
        step=100,
    )
    thickness_min: FloatProperty(
        name="Minimum Thickness",
        subtype="DISTANCE",
        default=0.001,  # 1mm
        min=0.0,
        max=10.0,
        precision=3,
        step=0.1
    )
    angle_sharp: FloatProperty(
        name="Angle",
        subtype="ANGLE",
        default=math.radians(160.0),
        min=0.0,
        max=math.radians(180.0),
        step=100,
    )
    angle_overhang: FloatProperty(
        name="Angle",
        subtype="ANGLE",
        default=math.radians(45.0),
        min=0.0,
        max=math.radians(90.0),
        step=100,
    )

    # Export
    # -------------------------------------

    export_path: StringProperty(
        name="Export Directory",
        default="//",
        maxlen=1024,
        subtype="DIR_PATH",
    )
    export_format: EnumProperty(
        name="Format",
        description="File format",
        items=(
            ("OBJ", "OBJ", ""),
            ("PLY", "PLY", ""),
            ("STL", "STL", ""),
        ),
        default="STL",
    )
    use_ascii_format: BoolProperty(
        name="ASCII",
        description="Export file in ASCII format",
    )
    use_scene_scale: BoolProperty(
        name="Scene Scale",
        description="Apply scene scale on export",
    )
    use_copy_textures: BoolProperty(
        name="Copy Textures",
        description="Copy textures on export to the output path",
    )
    use_uv: BoolProperty(name="UVs")
    use_normals: BoolProperty(
        name="Normals",
        description="Export specific vertex normals if available, export calculated normals otherwise"
    )
    use_colors: BoolProperty(
        name="Colors",
        description="Export vertex color attributes"
    )

    @staticmethod
    def get_report():
        return report.info()
