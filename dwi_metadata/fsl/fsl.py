#!/usr/bin/python3

import logging
import os
from os import path as op
import subprocess
from tqdm import tqdm

from dwi_metadata import ACQUISITIONS
from dwi_metadata import tests
from . import applytopup
from . import bedpostx
from . import dtifit
from . import eddy
from . import topup

logger = logging.getLogger(__name__)


# FSL topup will not run if an image claims to have phase encoding along the third axis;
#   therefore can't do every possible permutation
# TODO Can play with permutation of the first two axes
FSLPREPROC_STRIDES = {'RAS': [1, 2, 3, 4],
                      'LAS': [-1, 2, 3, 4],
                      'LPS': [-1, -2, 3, 4],
                      'RPS': [1, -2, 3, 4],
                      'RAI': [1, 2, -3, 4],
                      'LAI': [-1, 2, -3, 4],
                      'LPI': [-1, -2, -3, 4],
                      'RPI': [1, -2, -3, 4]}


def test_dtifit(scratchdir):
    def execute(inputname, inputdir, maskdir, scratchdir):
        dtifitdir = op.join(scratchdir, f'dtifit_from_{op.basename(inputdir)}')
        dtifit.run(inputdir, maskdir, dtifitdir)
        conversiondir = op.join(scratchdir, f'dtifit_{op.basename(inputdir)}_to_scannerspace')
        dtifit.convert(dtifitdir, conversiondir)
        tests.peaks(f'FSL dtifit from {inputname}',
                    conversiondir,
                    maskdir,
                    'mif',
                    'nii')
    execute('dcm2niix',
            op.join(scratchdir, 'dcm2niix'),
            op.join(scratchdir, 'mask_dcm2niix'),
            scratchdir)
    execute('MRtrix3 mrconvert without reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niibvecbvaljsonFalse'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niibvecbvaljsonFalse'),
            scratchdir)
    execute('MRtrix3 mrconvert with reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niibvecbvaljsonTrue'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niibvecbvaljsonTrue'),
            scratchdir)



# Note that fsleyes labels "L-R-A-P-S-I" do *not* correspond to anatomical orientations;
#   they seemingly correspond rather to i, i-, j, j-, k, k-
def test_bedpostx(scratchdir):

    def execute(inputname, inputdir, maskdir, scratchdir):
        bedpostxdir = op.join(scratchdir, f'bedpostx_from_{op.basename(inputdir)}')
        bedpostx.run(inputdir, maskdir, bedpostxdir)
        conversiondir = op.join(scratchdir, f'bedpostx_from_{op.basename(inputdir)}_sph2peaks')
        bedpostx.convert(bedpostxdir, conversiondir, False)
        tests.peaks(f'bedpostx from {inputname}; spherical coordinates',
                    conversiondir,
                    maskdir,
                    'mif',
                    'nii')
        conversiondir = op.join(scratchdir, f'bedpostx_from_{op.basename(inputdir)}_dyads2peaks')
        bedpostx.convert(bedpostxdir, conversiondir, True)
        tests.peaks(f'bedpostx from {inputname}; 3-vectors',
                    conversiondir,
                    maskdir,
                    'mif',
                    'nii')
    execute('dcm2niix',
            op.join(scratchdir, 'dcm2niix'),
            op.join(scratchdir, 'mask_dcm2niix'),
            scratchdir)
    execute('MRtrix3 mrconvert without reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niibvecbvaljsonFalse'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niibvecbvaljsonFalse'),
            scratchdir)
    execute('MRtrix3 mrconvert with reorientation',
            op.join(scratchdir, 'mrconvert_dcm2niibvecbvaljsonTrue'),
            op.join(scratchdir, 'mask_mrconvert_dcm2niibvecbvaljsonTrue'),
            scratchdir)



def test_preproc(dicomdir, scratchdir):

    os.makedirs(op.join(scratchdir, 'topup'))
    for stride_name, stride_list in tqdm(FSLPREPROC_STRIDES.items(), desc='Testing FSL topup'):
        topupdir = op.join(scratchdir, 'topup', stride_name)
        os.makedirs(topupdir)
        topup.run(dicomdir, topupdir, stride_list)
    logger.info(f'Check topup images: mrview {scratchdir}/topup/*/corr.nii.gz')

    os.makedirs(op.join(scratchdir, 'applytopup'))
    for stride_name, stride_list in tqdm(FSLPREPROC_STRIDES.items(), desc='Testing FSL applytopup'):
        topupdir = op.join(scratchdir, 'topup', stride_name)
        applytopupdir = op.join(scratchdir, 'applytopup', stride_name)
        os.makedirs(applytopupdir)
        applytopup.run(dicomdir, topupdir, applytopupdir, stride_list)
    logger.info(f'Check applytopup images: mrview {scratchdir}/applytopup/*/applytopup.mif')

    # TODO Require further work before eddy tests can run in reasonable time
    #os.makedirs(op.join(scratchdir, 'eddy'))
    #for stride_name, stride_list in tqdm(FSLPREPROC_STRIDES.items(), desc='Testing FSL eddy'):
    #    topupdir = op.join(scratchdir, 'topup', stride_name)
    #    eddydir = op.join(scratchdir, 'eddy', stride_name)
    #    os.makedirs(eddydir)
    #    eddy.run(dicomdir, topupdir, eddydir, op.join(scratchdir, 'mask.nii'), stride_list)
    #logger.info(f'Check eddy images: {scratchdir}/eddy/*')

