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

import math

import bpy
import bmesh

from mathutils import Vector, Matrix


axes = {
    "X": Vector((1, 0, 0)),
    "Y": Vector((0, 1, 0)),
    "Z": Vector((0, 0, 1)),
}


class AligningAxesError(Exception):
    pass


def align_to_local_axis(ob: bpy.types.Object, axis: str = "X") -> None:
    """Align the faces of the object with a local axis.

    After rotating the mesh, rotate the object in the opposite way to ensure the
    mesh stays where it is.
    """

    assert ob.type == "MESH", f"only works with MESH, this is {ob.type!r}"

    face_normal = _average_face_normal(ob)
    target_normal = _find_closes_axis(face_normal)
    rotation_axis = axes[axis]

    if rotation_axis.dot(target_normal) > 0.9:
        raise AligningAxesError(
            f"Target normal {target_normal} cannot be equal to the rotation axis {axis}"
        )

    angle = _rotation_to_vec(face_normal, target_normal, rotation_axis)
    print(f"Rotate {math.degrees(angle):.2f} deg over axis {rotation_axis}")

    matrix = Matrix.Rotation(angle, 4, axis)
    _apply_rotation(ob, matrix)


def _average_face_normal(ob: bpy.types.Object) -> Vector:
    pass

    if ob.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    normal_sum = Vector((0, 0, 0))

    bm: bmesh.types.BMesh = bmesh.new()
    me: bpy.types.Mesh = ob.data
    try:
        bm.from_mesh(me)
        bm.normal_update()

        for face in bm.faces:
            face_area = face.calc_area()
            normal_sum += face_area * face.normal
    finally:
        bm.free()

    if normal_sum.length < 0.0001:
        return Vector((0, 0, 0))

    return normal_sum.normalized()


def _find_closes_axis(face_normal: Vector) -> Vector:
    """Return the X, Y, or Z coordinate axis."""

    def absdot(v: Vector) -> float:
        dot: float = face_normal.dot(v)
        return abs(dot)

    return max(axes.values(), key=absdot)


def _rotation_to_vec(
    face_normal: Vector,
    target_normal: Vector,
    rotation_axis: Vector,
) -> float:
    """Create rotation to align face_normal with target_normal.

    Rturns a single-axis rotation angle over 'rotation_axis'.
    """
    assert (
        abs(target_normal.dot(rotation_axis)) < 0.9
    ), f"Rotation {rotation_axis} and target {target_normal} axes should not align"

    angle = math.atan2(
        face_normal.cross(target_normal).dot(rotation_axis),
        face_normal.dot(target_normal),
    )

    return angle


def _apply_rotation(ob: bpy.types.Object, rotation: Matrix) -> None:
    ob.matrix_basis = ob.matrix_basis @ rotation

    with bpy.context.temp_override(object=ob):
        bpy.ops.object.transform_apply(
            location=False,
            rotation=True,
            scale=False,
            properties=False,
            isolate_users=True,
        )

    ob.matrix_basis = ob.matrix_basis @ rotation.inverted()
