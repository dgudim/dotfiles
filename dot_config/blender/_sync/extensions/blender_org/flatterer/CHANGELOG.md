# Flatterer Changelog

## Version 1.6 - released 2025-03-09

- Add two "Boolean Cut" operators:
    1. Cut all selected objects out of the active object.
    2. Cut the active object out of all selected objects.
  The modifiers are moved to the first spot, so that they sit before any Solidify modifier.
- Shape Table: include surface area (in m²) of each exported shape.
- Fix bug where the 'Align to Local Axis' would cause an error.
- Work around issue handling zero-length edges.
- Support "engrave" edges also when inside the mesh (before it was only working for wire edges).

## Version 1.5.1 - released 2023-05-19

- Fix issue where "Separate Mesh into Faces" would create too many separate objects.

## Version 1.5 - released 2023-04-15

- Add "Align with Local Axis" operator to rotate meshes so they align with the local coordinate axes.
- Add "Extrude Finger" operator, available in mesh edit mode. It takes the selected edges, and extrudes them outward for finger connections. This is limited to working in a single direction at a time, so make sure to only select edges on one side of your model.
- Add "Separate Mesh into Faces", which separates the mesh into an object for every group of faces that have the same direction.
- Open the directory containing the SVG file after exporting, in a file manager/explorer. Can be disabled in the add-on preferences.

## Version 1.4 - released 2023-01-07

- Clarified the GUI.
- Add support for marking edges to engrave (instead of to cut).

## Version 1.3 - released 2022-12-31

- Add material length option, and write a multi-page SVG file where each page is a slab of cuttable material.
- Add margin option, to distinguish "margin to material edge" from "spacing between cutting shapes". Previous versions used the "Shape Padding" option for both, which is now only used for the latter.
- Remove "Reduce Waste" option. It got in the way of the newly introduced exporting to multiple pages, and it wasn't as practically useful as I thought it would be.

## Version 1.2 - released 2022-04-06

- Optionally place a shape table in the SVG, listing each exported shape and its width / height.
- Thicker shape outlines.
- Export to SVG layers, compatible with Inkscape.
- Also export wire edges (previously this was limited to face boundary edges).

## Version 1.1 - released 2022-02-09

- Expose some options of the packing algorithm: sorting & rotation. These make it possible to tweak the packing algorithm for your use case; some options work better for almost-square parts, others better for long-and-thin parts, etc.
- Fix bug in the panel, which caused buttons to disappear when there is no active object.
- Change label of operator to "Setup Scene for mm" so that it's clearer what the button does.

## Version 1.0 - released 2022-01-09

Initial release.
