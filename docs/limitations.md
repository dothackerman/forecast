# Methodological limitations

This service is designed for pragmatic parcel-level forecasting, but it is **not** a full downscaling platform.

## What is explicitly out of scope

- No **dynamical downscaling**:
  - no nested mesoscale model domains,
  - no local PDE-based reruns over Swiss sub-regions.

- No **statistical downscaling**:
  - no station-trained bias correction models,
  - no ML/quantile mapping workflow.

## Practical consequences

- Spatial representativeness is limited by source NWP resolution.
- Parcel values are generated from centroid interpolation, not full geometry-resolved simulation.
- Temperature adjustment uses a fixed environmental lapse rate rather than regime-dependent calibration.
- Solar correction uses a simplified geometric factor and does not model cloud-radiation-topography interactions in detail.
- Precipitation and humidity are mostly inherited from parent fields (not recomputed with local dynamics).

## Interpretation guidance

Use outputs as:
- rapid, consistent, terrain-adjusted parcel indicators.

Do not use outputs as:
- substitutes for high-resolution local numerical weather model runs,
- validated station-based local climatology products.
