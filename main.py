#!/usr/bin/python3

import logging
import numpy as np
import os
import os.path as op
import sys

#from dwi_metadata import EXTENSIONS
from dwi_metadata import FILE_FORMATS
from dwi_metadata import ACQUISITIONS
from dwi_metadata.dcm2niix import dcm2niix
from dwi_metadata.fsl import fsl
from dwi_metadata.mrtrix3 import mrtrix3
from dwi_metadata import tests
from dwi_metadata import utils

logger = logging.getLogger()



def main():

    if len(sys.argv) != 4:
        sys.stderr.write('Usage: main.py <DICOM_directory> <scratch_directory> <log_file>\n')
        sys.exit(1)

    dicomdir = sys.argv[1]
    scratchdir = sys.argv[2]
    logfile = sys.argv[3]

    if not op.isdir(dicomdir):
        sys.stderr.write('Expect first argument to be input directory')
        sys.exit(1)

    logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)-8s '
                               '[%(filename)s:%(lineno)d] %(message)s',
                        level=logging.INFO,
                        filename=logfile,
                        filemode="w")
    console = logging.StreamHandler()
    console.setLevel(logging.WARN)
    logger.addHandler(console)

    logger.debug('List of acquisitions:')
    for acq in ACQUISITIONS:
        logger.debug(f'  {acq}')

    utils.wipe_output_directory(scratchdir)
    try:
        os.makedirs(scratchdir)
    except FileExistsError:
        pass

    # Evaluate dcm2niix
    dcm2niixdir = op.join(scratchdir, 'dcm2niix')
    dcm2niix.test_dcm2niix(dicomdir, dcm2niixdir)

    # Evaluate MRtrix conversion from DICOM to various formats
    mrtrix3.test_mrconvert_from_dicom(dicomdir, scratchdir)

    # Evaluate conversion to different forms of phase encoding data
    mrtrix3.test_petables(dicomdir, scratchdir)

    # To better separate potential issues between MRtrix3 read and MRtrix3 write,
    #   evaluate conversions from dcm2niix to different formats with different strides
    mrtrix3.test_mrconvert_from_dcm2niix(dcm2niixdir, scratchdir)

    # Now take files that have been converted by MRtrix3 from DICOM to some format,
    #   and import them and write them as another format
    mrtrix3.test_mrconvert_from_mrconvert(scratchdir)

    # Generate a single brain mask that will be used for processing of all datasets
    maskpath = op.join(scratchdir, 'mask.nii')
    mrtrix3.dwi2mask.run(dicomdir,
                         op.join(scratchdir, 'dwi2mask'),
                         maskpath)

    # Convert this aggregate brain mask to fit data
    #   with different orientations & obtained through different conversions
    mrtrix3.convert_mask(dcm2niixdir, maskpath, scratchdir)

    # Run tensor fit using MRtrix3
    mrtrix3.test_dwi2tensor(scratchdir)

    # Check DWI pre-processing commands: topup, applytopup, eddy
    # Note: No automated validation, these images need to be verified manually
    fsl.test_preproc(dicomdir, scratchdir)

    # FSL dtifit
    fsl.test_dtifit(scratchdir)

    # FSL bedpostx
    fsl.test_bedpostx(scratchdir)





if __name__ == '__main__':
    main()

