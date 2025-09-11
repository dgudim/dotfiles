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

from typing import Iterable, Optional, TYPE_CHECKING, Iterator, cast
from dataclasses import dataclass
from collections import defaultdict
from contextlib import contextmanager
from enum import Enum

import bpy
import bmesh
from mathutils import Vector, Matrix

# Blender doesn't differentiate between vector sizes, but I do.
if TYPE_CHECKING:
    # But Blender doesn't come with the `typing_extensions` module, so be
    # careful here.
    from typing_extensions import TypeAlias
else:
    TypeAlias = object

Vector3: TypeAlias = Vector
Vector2: TypeAlias = Vector
Poly2Edge: TypeAlias = tuple[Vector2, Vector2]
Poly2Edges: TypeAlias = list[Poly2Edge]
Poly3Edge: TypeAlias = tuple[Vector3, Vector3]
Poly3Edges: TypeAlias = list[Poly3Edge]


@dataclass
class Options:
    laser_width: float
    """The width of the laser beam, in Blender units (assumed mm)."""
    material_width: float
    """The width of the to-be-cut material, in Blender units (assumed mm)."""
    material_length: float
    """The length of the to-be-cut material, in Blender units (assumed mm)."""
    margin: float
    """The distance from the edge of the material to the closest shape, in Blender units (assumed mm)."""
    shape_padding: float
    """Amount of padding around each shape, in Blender units (assumed mm)."""
    pack_sort: str
    """Sorting method for the packing algorithm."""
    pack_may_rotate: bool
    """Whether the packing algorithm is allowed to rotate shapes."""
    shape_table: bool
    """Whether to put the table of shape sizes in the SVG."""

    def page_offset(self, page_index: int) -> float:
        "X-offset to put elements on the given page."
        # Use the margin to also space apart the pages.
        return page_index * (self.material_width + self.margin)


class MeshAnalysisError(RuntimeError):
    pass


class MeshType(Enum):
    CUT = "CUT"
    ENGRAVE = "ENGRAVE"

    @classmethod
    def for_edge(cls, edge: bmesh.types.BMEdge) -> "MeshType":
        if not edge.smooth:
            return cls.ENGRAVE
        return cls.CUT


@dataclass
class AnnotatedMesh:
    edges: list["AnnotatedEdge"]

    def append_edge(self, edge: "AnnotatedEdge") -> None:
        self.edges.append(edge)

    def flattened(self, drop_axis: int) -> "FlattenedMesh":
        flattened_edges = [e.flattened(drop_axis) for e in self.edges]
        return FlattenedMesh(edges=flattened_edges)


@dataclass
class AnnotatedEdge:
    verts: tuple[Vector3, Vector3]
    edgeType: MeshType

    def flattened(self, drop_axis: int) -> "FlattenedEdge":
        vectors2d = []
        for vect3d in self.verts:
            point2d = tuple(vect3d[i] for i in range(3) if i != drop_axis)
            vect2d = Vector2(point2d)
            vectors2d.append(vect2d)
        assert len(vectors2d) == 2
        flat_verts: tuple[Vector2, Vector2] = tuple(vectors2d)
        return FlattenedEdge(verts=flat_verts, edgeType=self.edgeType)


@dataclass
class FlattenedMesh:
    edges: list["FlattenedEdge"]

    @property
    def is_closed(self) -> bool:
        if not self.edges:
            return False
        return bool(self.edges[0].verts[0] == self.edges[-1].verts[-1])

    def iter_points(self) -> Iterable[Vector2]:
        last_point: Optional[Vector2] = None
        for e in self.edges:
            if e.verts[0] != last_point:
                yield e.verts[0]
            yield e.verts[1]
            last_point = e.verts[1]

    def extend(self, other_mesh: "FlattenedMesh") -> None:
        self.edges.extend(other_mesh.edges)

    def append_edge(self, edge: "FlattenedEdge") -> None:
        self.edges.append(edge)

    def split(self) -> dict[MeshType, list["FlattenedMesh"]]:
        """Split the mesh into meshes of continues edges of the same type."""

        per_type: dict[MeshType, list[FlattenedMesh]] = defaultdict(list)

        for edge in self.edges:
            meshes_for_type = per_type[edge.edgeType]

            # Find/create a mesh that this edge can be appended to.
            for mesh in sorted(meshes_for_type, key=lambda m: -len(m.edges)):
                if not mesh.edges:
                    break
                if edge.follows(mesh.edges[-1]):
                    break
            else:
                mesh = FlattenedMesh(edges=[])
                per_type[edge.edgeType].append(mesh)

            mesh.append_edge(edge)

        return per_type

    def aabb(self) -> "AABB":
        aabb = AABB()
        for edge in self.edges:
            for point in edge.verts:
                aabb.extend(point)
        return aabb

    def translate_self(self, offset: Vector2) -> None:
        for edge in self.edges:
            edge.translate_self(offset)

    def copy(self) -> "FlattenedMesh":
        return FlattenedMesh(edges=self.edges[:])

    def move_to_origin(self) -> None:
        """Translate this mesh so its smallest coordinate is at the origin."""
        aabb = self.aabb()
        self.translate_self(-aabb.min_point)


@dataclass
class FlattenedEdge:
    verts: tuple[Vector2, Vector2]
    edgeType: MeshType

    def follows(self, edge: "FlattenedEdge") -> bool:
        """Returns whether this edge's start is connected to the given edge's end."""
        return edge.edgeType == self.edgeType and edge.verts[1] == self.verts[0]

    def translate_self(self, offset: Vector2) -> None:
        v0 = self.verts[0] + offset
        v1 = self.verts[1] + offset
        self.verts = (v0, v1)


class MeshBoundary:
    """2D boundaries of a single mesh's outline and holes."""

    def __init__(self, name: str) -> None:
        self.name = name
        # Polygons of the outline and any holes. Order not guaranteed.
        self.polygons: dict[MeshType, list[FlattenedMesh]] = {}
        self._aabb: Optional["AABB"] = None

        self.rotation = 0  # Degrees (because SVG does degrees)
        self.translation = Vector2((0, 0))
        self.page_num = 0  # Set by the shape packer.

    def __bool__(self) -> bool:
        return bool(self.polygons and self.aabb)

    def polygons_by_type(self) -> Iterable[tuple[MeshType, FlattenedMesh]]:
        for meshtype, polies in self.polygons.items():
            for poly in polies:
                yield meshtype, poly

    @property
    def aabb(self) -> "AABB":
        if self._aabb is not None:
            return self._aabb

        aabb = AABB()
        for _, poly in self.polygons_by_type():
            aabb.join(poly.aabb())
        self._aabb = aabb
        return aabb

    def transform_into(self, position: Vector2, size: Vector2) -> None:
        """Rotate the shape to a new position and rotate to make the size match.

        Only does 90 degree rotations.
        """

        aabb = self.aabb
        self.translation = position - aabb.min_point
        if (size.x > size.y) == (aabb.width > aabb.height):
            self.rotation = 0
        else:
            self.rotation = 90
            self.translation.y += aabb.width


@dataclass
class AABB:
    """Axis-Aligned Bounding Box."""

    min_x: float = float("inf")
    min_y: float = float("inf")
    max_x: float = float("-inf")
    max_y: float = float("-inf")

    def __bool__(self) -> bool:
        return self.min_x < self.max_x and self.min_y < self.max_y

    @property
    def width(self) -> float:
        """Width of the AABB.

        >>> AABB(min_x=1, min_y=2, max_x=3, max_y=4).width
        2
        """
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Height of the AABB.

        >>> AABB(min_x=1, min_y=2, max_x=3, max_y=5.5).height
        3.5
        """
        return self.max_y - self.min_y

    @property
    def mid_x(self) -> float:
        """X coordinate of middle point of the AABB.

        >>> AABB(min_x=1, min_y=2, max_x=3, max_y=4).mid_x
        2.0
        """
        return (self.max_x + self.min_x) / 2

    @property
    def mid_y(self) -> float:
        """X coordinate of middle point of the AABB.

        >>> AABB(min_x=1, min_y=2, max_x=3, max_y=4).mid_y
        3.0
        """
        return (self.max_y + self.min_y) / 2

    @property
    def min_point(self) -> Vector2:
        return Vector2((self.min_x, self.min_y))

    @property
    def area(self) -> float:
        """Area spanned by the AABB."""
        return self.width * self.height

    def extend(self, point: Vector2) -> None:
        """Extend the AABB to include the given point."""
        self.min_x = min(self.min_x, point[0])
        self.min_y = min(self.min_y, point[1])
        self.max_x = max(self.max_x, point[0])
        self.max_y = max(self.max_y, point[1])

    def join(self, aabb: "AABB") -> None:
        """Extend the AABB to include the other AABB.

        >>> aabb1 = AABB(min_x=1, min_y=2, max_x=3, max_y=4)
        >>> aabb2 = AABB(min_x=5, min_y=5, max_x=7.7, max_y=9.3)
        >>> aabb1.join(aabb2)
        >>> aabb1
        AABB(min_x=1, min_y=2, max_x=7.7, max_y=9.3)
        """
        self.min_x = min(self.min_x, aabb.min_x)
        self.min_y = min(self.min_y, aabb.min_y)
        self.max_x = max(self.max_x, aabb.max_x)
        self.max_y = max(self.max_y, aabb.max_y)

    def boundary(self) -> Poly2Edges:
        minmin = Vector2((self.min_x, self.min_y))
        maxmin = Vector2((self.max_x, self.min_y))
        maxmax = Vector2((self.max_x, self.max_y))
        minmax = Vector2((self.min_x, self.max_y))
        return [
            (minmin, maxmin),
            (maxmin, maxmax),
            (maxmax, minmax),
            (minmax, minmin),
        ]

    def size(self) -> Vector2:
        return Vector((self.max_x - self.min_x, self.max_y - self.min_y))

    def translated(self, translation: Vector2) -> "AABB":
        """ "Translate the AABB by the given vector.

        >>> AABB(min_x=1, min_y=2, max_x=3, max_y=4).translated(Vector2((5, 6)))
        AABB(min_x=6.0, min_y=8.0, max_x=8.0, max_y=10.0)
        """
        return AABB(
            min_x=self.min_x + translation.x,
            min_y=self.min_y + translation.y,
            max_x=self.max_x + translation.x,
            max_y=self.max_y + translation.y,
        )

    def rotated(self) -> "AABB":
        """Mirror the AABB around its diagonal.

        >>> AABB(min_x=1, min_y=2, max_x=3, max_y=5.5).rotated()
        AABB(min_x=1, min_y=2, max_x=4.5, max_y=4)
        """
        return AABB(
            min_x=self.min_x,
            min_y=self.min_y,
            max_x=self.min_x + self.height,
            max_y=self.min_y + self.width,
        )


def flatten_mesh(object: bpy.types.Object, options: Options) -> MeshBoundary:
    """Flatten a mesh into a set of 2D polygons.

    Each polygon is a list of 2D coordinates.

    \return a MeshBoundary object.
    """
    assert object.type == "MESH"

    combined_flat_mesh = FlattenedMesh(edges=[])
    with _mesh_to_bmesh(object) as bm:
        drop_axis = _axis_to_drop(bm)
        for annotated_mesh in _find_boundary_polys(
            object.data, bm, options, object.name
        ):
            flat_mesh = annotated_mesh.flattened(drop_axis)
            combined_flat_mesh.extend(flat_mesh)

    combined_flat_mesh.move_to_origin()
    split = combined_flat_mesh.split()
    from pprint import pprint

    pprint(split)

    mesh_boundary = MeshBoundary(object.name)
    mesh_boundary.polygons = split
    return mesh_boundary


def _find_boundary_polys(
    mesh: bpy.types.Mesh,
    bm: bmesh.types.BMesh,
    options: Options,
    object_name: str,
) -> Iterable[AnnotatedMesh]:
    """Generator, yields boundary polygons.

    Each polygon is a list of 3D coordinates.
    """

    bm.edges.ensure_lookup_table()
    add_kerf(bm, options, object_name)
    yield from _boundary_polygons_from_bmesh(mesh, bm)


def add_kerf(bm: bmesh.types.BMesh, options: Options, object_name: str) -> None:
    """Add a kerf offset to all edges except ones marked as "seam" or "sharp"."""

    edge_kerfs = defaultdict(list)

    for v in bm.verts:
        if not v.is_boundary:
            continue

        for l in v.link_loops:
            e = l.edge
            if e.is_manifold or e.is_wire:
                continue
            if e.seam:  # Seams are used as "do not apply kerf compensation".
                continue

            # Assumption: face lies to the left of the loop.
            v_other = e.other_vert(v)
            if v_other.co == v.co:
                print(
                    f"{object_name}: zero-length edge found, might be caused by wonky boolean modifiers"
                )
                continue

            loop_vec = (v_other.co - v.co).normalized()
            tangent = loop_vec.cross(l.face.normal).normalized()
            if abs(tangent.length - 1.0) > 1e-6:
                raise MeshAnalysisError(
                    f"{object_name}: loop tangent is not unit length: {tangent}"
                )
            edge_kerfs[e.index].append(tangent)

    # Accumulate kerfs. This must be done afterwards to ensure all kerf
    # directions are computed before the adjustments are applied.
    vtx_kerf_directions: dict[int, Vector] = defaultdict(lambda: Vector((0, 0, 0)))
    for edge_index, kerfs in edge_kerfs.items():
        assert len(kerfs) == 1, "Expecting edges to be visited only once"
        kerf_direction = kerfs[0]

        e = bm.edges[edge_index]
        for v in e.verts:
            vtx_kerf_directions[v.index] += kerf_direction

    bm.verts.ensure_lookup_table()
    kerf_width = options.laser_width / 2
    for vtx_index, kerf_direction in vtx_kerf_directions.items():
        # Clamping prevents applying the kerf multiple times in the same direction.
        clamp_vector(kerf_direction)
        v = bm.verts[vtx_index]
        v.co += kerf_direction * kerf_width


def _boundary_polygons_from_bmesh(
    mesh: bpy.types.Mesh,
    bm: bmesh.types.BMesh,
) -> Iterable[AnnotatedMesh]:
    """Generate boundary polygon coordinates.

    For each polygon, a list of edges is yielded. Edges are represented as a
    `(start, end)` tuple of their coordinates. For connected edges, the `end` of
    edge N is the same as `start` of edge N+1.
    """
    bm.edges.index_update()

    export_edge_indices = {e.index for e in bm.edges if _is_export_edge(mesh, e)}
    start_edge_indices = _find_start_edge_indices(bm)

    non_export_starters = start_edge_indices - export_edge_indices
    if non_export_starters:
        print(f"Warning: non-export started edges: {sorted(non_export_starters)}")
        start_edge_indices -= non_export_starters

    def find_next_edge(vertex: bmesh.types.BMVert) -> Optional[bmesh.types.BMEdge]:
        for e in vertex.link_edges:
            if e.index in export_edge_indices:
                return e
        return None

    while export_edge_indices:
        annotated_mesh = AnnotatedMesh(edges=[])

        # Find the next edge to export.
        if start_edge_indices:
            edge_idx = start_edge_indices.pop()
            export_edge_indices.remove(edge_idx)
        else:
            edge_idx = export_edge_indices.pop()

        e = bm.edges[edge_idx]

        # If one of the vertices is only incident to this edge, start there.
        if len(e.verts[0].link_edges) == 1:
            v0, visit = e.verts
        else:
            visit, v0 = e.verts

        edge = AnnotatedEdge(verts=(v0.co, visit.co), edgeType=MeshType.for_edge(e))
        annotated_mesh.append_edge(edge)

        # Keep following this edge sequence until the end.
        while visit.index != v0.index:
            e = find_next_edge(visit)
            if e is None:
                break
            export_edge_indices.remove(e.index)
            start_edge_indices.discard(e.index)

            edge_type = MeshType.for_edge(e)

            # Vertices of the edges are not guaranteed in the same order.
            # Find the one that is not the current v1.
            next1, next2 = e.verts
            if next1.index == visit.index:
                visit = next2
                edge = AnnotatedEdge(verts=(next1.co, visit.co), edgeType=edge_type)
            else:
                visit = next1
                edge = AnnotatedEdge(verts=(next2.co, visit.co), edgeType=edge_type)
            annotated_mesh.append_edge(edge)

        yield annotated_mesh


def _find_start_edge_indices(bm: bmesh.types.BMesh) -> set[int]:
    """Return a set of edge indices to start exporting from.

    These indices are edges that end the chain of edges, i.e. either their start
    or end vertex only has one edge.
    """

    edge_indices: set[int] = set()
    for v in bm.verts:
        if len(v.link_edges) != 1:
            continue
        edge_indices.add(v.link_edges[0].index)
    return edge_indices


def _axis_to_drop(bm: bmesh.types.BMesh) -> int:
    # Compute bounding box. The AABB is only 2D, so keep track of min/max Z separately.
    min_z = float("inf")
    max_z = float("-inf")
    aabb = AABB()
    for v in bm.verts:
        aabb.extend(v.co.xy)
        min_z = min(min_z, v.co.z)
        max_z = max(max_z, v.co.z)

    bbox_min = Vector((aabb.min_x, aabb.min_y, min_z))
    bbox_max = Vector((aabb.max_x, aabb.max_y, max_z))
    bbox_dim = tuple(bbox_max - bbox_min)

    drop_axis = bbox_dim.index(min(bbox_dim))
    return drop_axis


def clamp_vector(v: Vector) -> None:
    v.x = max(-1.0, min(v.x, 1.0))
    v.y = max(-1.0, min(v.y, 1.0))
    v.z = max(-1.0, min(v.z, 1.0))


@contextmanager
def _mesh_to_bmesh(object: bpy.types.Object) -> Iterator[bmesh.types.BMesh]:
    """Context manager, yields a bmesh for the object and frees afterwards.

    The BMesh is transform to world space. Edges marked as "sharp" are tagged,
    as those are meant to be engraved. The "sharp" property can't seem to be
    obtained from BMesh, unfortunately.
    """
    assert object.type == "MESH"

    if object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    scale_vec = object.matrix_world.to_scale()
    scale_mat = Matrix.Diagonal(scale_vec)
    bm: bmesh.types.BMesh = bmesh.new()
    me: bpy.types.Mesh = object.data
    try:
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, dist=0.001)
        bmesh.ops.transform(bm, matrix=scale_mat, verts=bm.verts)
        yield bm
    finally:
        bm.free()


def select_export_edges(ob: bpy.types.Object) -> None:
    assert ob.type == "MESH"
    assert ob.mode == "EDIT"

    mesh = ob.data
    bm = bmesh.from_edit_mesh(mesh)
    for e in bm.edges:
        if _is_export_edge(mesh, e):
            e.select_set(True)
    bm.select_flush(True)

    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)


def _is_export_edge(mesh: bpy.types.Mesh, e: bmesh.types.BMEdge) -> bool:
    return bool(e.is_boundary or e.is_wire or mesh.edges[e.index].use_edge_sharp)


import doctest
import sys

mod = sys.modules[__name__]
doctest.testmod(mod)
