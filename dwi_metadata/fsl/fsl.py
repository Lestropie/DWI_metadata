#!/usr/bin/python3

from os import path as op

from dwi_metadata import tests
from . import bedpostx
from . import dtifit



def test_dtifit(scratchdir):
    def execute(inputname, inputdir, maskdir, scratchdir):
        dtifitdir = op.join(scratchdir, f'dtifit_from_{op.basename(inputdir)}')
        dtifit.run(inputdir, maskdir, dtifitdir)
        conversiondir = op.join(scratchdir, f'dtifit_{op.basename(inputdir)}_to_scannerspace')
        dtifit.convert(dtifitdir, conversiondir)
        tests.peaks(f'FSL dtifit from {inputname}', conversiondir, maskdir, 'nii')
    execute('dcm2niix',
            op.join(scratchdir, 'dcm2niix'),
            op.join(scratchdir, 'mask_dcm2niix'),
            scratchdir)
    execute('MRtrix3 mrconvert without reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niijsonbvecbvalFalse'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niijsonbvecbvalFalse'),
            scratchdir)                        
    execute('MRtrix3 mrconvert with reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niijsonbvecbvalTrue'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niijsonbvecbvalTrue'),
            scratchdir)        



# Note that fsleyes labels "L-R-A-P-S-I" do *not* correspond to anatomical orientations;
#   they seemingly correspond rather to i, i-, j, j-, k, k-
def test_bedpostx(scratchdir):

    def execute(inputname, inputdir, maskdir, scratchdir):
        bedpostxdir = op.join(scratchdir, f'bedpostx_from_{op.basename(inputdir)}')
        bedpostx.run(inputdir, maskdir, bedpostxdir)
        conversiondir = op.join(scratchdir, f'bedpostx_from_{op.basename(inputdir)}_sph2peaks')
        bedpostx.convert(bedpostxdir, conversiondir, False)
        tests.peaks(f'bedpostx from {inputname}; spherical coordinates', conversiondir, maskdir, 'nii')
        conversiondir = op.join(scratchdir, f'bedpostx_from_{testname}_dyads2peaks')
        bedpostx.convert(bedpostxdir, conversiondir, True)
        tests.peaks(f'bedpostx from {inputname}; 3-vectors', conversiondir, maskdir, 'nii')
    execute('dcm2niix',
            op.join(scratchdir, 'dcm2niix'),
            op.join(scratchdir, 'mask_dcm2niix'),
            scratchdir)
    execute('MRtrix3 mrconvert without reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niijsonbvecbvalFalse'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niijsonbvecbvalFalse'),
            scratchdir)
    execute('MRtrix3 mrconvert with reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niijsonbvecbvalTrue'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niijsonbvecbvalTrue'),
            scratchdir)

