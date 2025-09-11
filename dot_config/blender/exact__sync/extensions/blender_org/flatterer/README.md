# Flatterer

SVG exporter aimed at being somewhat useful for sending things to a laser cutter.

All selected mesh objects are exported to a single SVG file and placed side-by-side on the canvas. Mesh objects **must** be planar meshes; only non-manifold edges are exported.

For more info see:

## https://stuvel.eu/software/flatterer/

Below is a shorter version of the above page.

## Scene Requirements

Set up the scene units as follows to ensure proper exporting to SVG:

| Setting     | value       |
| ----------- | ----------- |
| Unit System | Metric      |
| Unit Scale  | 0.001       |
| Length      | Millimetres |

This can be done via the "Setup Scene for mm" button in the 3D Viewport sidebar panel.

## Limitations

There are some limitations that I want to lift at some point, but which at the moment of writing are still in there:

- Scene scale settings are ignored, hence the section above.
- The mesh must be planar and aligned to local axes. It doesn't matter whether it aligns with the XY, YZ, or XZ plane, but it has to align with one of them.

## Disclaimer

This add-on is just a way to scratch my own itch. If it can be made useful for you too with some small adjustments, feel free to [file an issue](https://gitlab.com/dr.sybren/flatterer/-/issues).


## License Notes

This add-on is covered by the GPL v3 license, as per the LICENSE file.

This add-on bundles [rectpack](https://github.com/secnot/rectpack/), which is licensed under the Apache License v2.0.

