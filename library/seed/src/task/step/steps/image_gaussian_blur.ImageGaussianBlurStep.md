# Gaussian image blur

Separable Gaussian smoothing for 2-D image matrices.

## Purpose

Implements `image_gaussian_blur` for image-like numeric tables. The operator
builds a one-dimensional Gaussian kernel from `sigma` and `truncate`, applies it
along both axes with symmetric edge padding, and returns the filtered matrix
preserving the input labels and shape.

## Parameters

`sigma` is the kernel standard deviation in pixels and `truncate` the kernel
half-width in standard deviations. `row_dim`/`field_dim` name the input axes and
`output` is injected by the engine.

## Output

A Form with the same dimensions and labels as the input containing the smoothed
values. Constant images remain constant.

## Limitations

Only two-dimensional numeric tables are supported (CSV/TSV export is 2-D only).
Edges use symmetric padding (the edge sample is repeated), which matches
`scipy.ndimage.gaussian_filter` with `mode="reflect"` for the tested range but is
not a full boundary-condition model.
