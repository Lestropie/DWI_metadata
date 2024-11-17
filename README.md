# DWI_metadata

A software tool for verifying appropriate software handling of DWI metadata

*Under development*

## Running the tests

A Docker image is now provided that embeds all requisite functionalities and data.
This can be done via eg.:
```ShellSession
docker build . -t dwi_metadata:latest
mkdir scratch
docker run -it --rm -v $(pwd)/scratch:/scratch dwi_metadata:latest /data /scratch /scratch/log.log
```

The execution scripts expect all relevant commands to be present in `PATH`.
This includes the `peakscheck` and `peaksconvert` commands proposed for *MRtrix3*,
which currently necessitates installation of the following branch:
https://github.com/MRtrix3/mrtrix3/pull/2918.
The container environment ensures that this is all set up as required.

## Software dependencies

-   `dcm2niix`
-   FSL
-   MRtrix3:
    -   A version for evaluation that is derived from `3.0.4`, intended to be included in `3.0.5`
    -   A development version that includes two crucial new commands for evaluation of fibre orientations:
        https://github.com/MRtrix3/mrtrix3/pull/2918

## Input data

### Gradient table

The gradient table utilised in acquisition of data for this project can be found at:

https://osf.io/p96tj/

The crucial feature of this gradient table is that,
for the first three non-*b*=0 volumes,
diffusion sensitisation was applied along each of the three native axes of the Device Coordinates System (DCS):
[1.0, 0.0, 0.0], then [0.0, 1.0, 0.0], then [0.0, 0.0, 1.0].
The known directions of diffusion sensitisation of these three volumes can therefore be utilised as *fiducials*,
ensuring that no interpretation of these data from the respsective DICOM series nor subsequent image processing steps
result in erroneous transformation of these vectors.
The gradient table intotality is however still relatively homogeneously distributed,
and can therefore be used for downstream diffusoin model fitting without bias.

Note that the directions of these vectors is predicated on the coordinate system of the scanner hardware gradients;
this is *not* equivalent to the Right-Anterior-Superior (RAS) convention used in many neuroimaging softwares / formats. 

### DICOM data

The DICOM data included in the Docker image can be found at:

https://osf.io/p96tj/

Here there are *24* DWI DICOM series.
These represent *every single possible combination* of slice encoding direction, slice order, and phase encoding direction,
for non-oblique fields of view.
In addition, all are isotropic acquisitions,
and use a cubic Field of View (FoV);
this facilitates concatenation of data across all series,
provided that the data are reoriented appropriately.
The contents of DICOM field `SeriesDescription`,
as well as the names of the directories in which they are stored,
also encode the slice encoding direction, slice order, and phase encoding direction;
any software handling of the metadata encoding this information can therefore be cross-checked
against what is known to have been acquired.

## Processing

The following is a summary of the validation currently performed by this tool.
It is hoped that this list will expand in the future.
Every test involves verification of all 24 DICOM series.

### Validation capabilities

1.  Validate gradient table as `bvec` / `bval`, based on image header transformation.
    Compare fiducials transformed to "real" / "scanner" space against known diffusion directions.
2.  Validate gradient table as MRtrix internal "`dw_scheme`".
    Image header transformation is irrelevant in this case,
    given that gradient directions are defined with respect to "real" / "scanner" space.
    Compare fiducials against known diffusion directions.
3.  Validate slice encoding metadata, based on image header transformation.
    This may involve *both* `SliceEncodingDirection` *and* `SliceTiming`,
    given that a temporal reversal of the slice timing vector and an inversion of the slice encoding direction
    are equivalent operations.
    Additionally, the relevant metadata may be stored internally within an image header,
    or it could be stored in a sidecar metadata file.
    Direction based on image axis identifier / signedness compared to `SeriesDescription`.
4.  Validate phase encoding direction, based on image header transformation.
    Additionally, the relevant metadata may be stored internally within an image header,
    or it could be stored in a sidecar metadata file.
    Direction based on image axis identifier / signedness compared to `SeriesDescription`.
5.  Validate interpretation of estimated fibre orientations.
    If these orientations can be appropriately transformed into "real" / "scanner" space
    for interpretation by MRtrix3,
    then the mean reconstructed streamline length should be longer than those cases
    where such transformation is incorrect.

### Software validations

-   `dcm2niix`:
    -   Conversion from DICOM only
    -   Validations 1, 3, 4.
        Note that in its current version, BIDS field "`SliceEncodingDirection`" is *not* explicitly written by `dcm2niix`;
        this tool must therefore *assume* a value of "`k`" in its absence.

-   *MRtrix3*:
    -   Conversion from DICOM:
        -   Different image and metadata formats:
            -   NIfTI, JSON, `bvec` & `bval`
            -   MRtrix MIF format, but with metadata stored in an external JSON
            -   MRtrix MIH / DAT format, with metadata accessible in text form from the image header
        -   With and without internal header transform realignment
    -   Conversion from non-DICOM:
        -   Import data:
            -   With and without internal header transform realignment
            -   Software sources:
                -   `dcm2niix`
                -   *MRtrix3*:
                    -   All previously mentioned image / file formats
                    -   Data generated with and without internal transform realignment
        -   Export data:
            -   All previously mentioned image / file formats
            -   Multiple destination image strides
    -   Validations 1, 2, 3, 4 (depending on image / file format)

-   FSL:

    -   Software sources:
        -   `dcm2niix`
        -   *MRtrix3* `mrconvert`
            -   With and without internal transform realignment
    -   `dtifit`:
        -   Validation 5 applied to V1 estimate.
    -   `bedpostx`:
        -   Validation 5 applied to "dyads".
            (with conversion to "real" / "scanner" space via *MRtrix3*)
        -   Validation 5 applied to spherical coordinates.
            (with conversion to "real" / "scanner" space via *MRtrix3*)

-----

RS ([@Lestropie](https://github.com/Lestropie)) is a fellow of the National Imaging Facility,
a National Collaborative Research Infrastructure Strategy (NCRIS) capability,
at the Florey Institute of Neuroscience and Mental Health.
