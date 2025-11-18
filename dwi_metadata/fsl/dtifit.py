#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import ACQUISITIONS

logger = logging.getLogger(__name__)

def run(indir, maskdir, dtifitdir):
    try:
        shutil.rmtree(dtifitdir)
    except OSError:
        pass
    os.makedirs(dtifitdir)
    logger.info(f'Running FSL dtifit from input {indir}')
    for acq in tqdm(ACQUISITIONS, desc=f'Running FSL dtifit on {indir}'):
        subprocess.run(['dtifit',
                        '-k', op.join(indir, f'{acq}.nii'),
                        '-o', op.join(dtifitdir, f'{acq}'),
                        '-m', op.join(maskdir, f'{acq}.nii'),
                        '-r', op.join(indir, f'{acq}.bvec'),
                        '-b', op.join(indir, f'{acq}.bval'),
                        '--wls',
                        '--save_tensor'],
                       capture_output=True,
                       check=True)
        subprocess.run(['mrcalc',
                        '-config', 'RealignTransform', 'false',
                        '-quiet',
                        op.join(dtifitdir, f'{acq}_V1.nii.gz'),
                        op.join(dtifitdir, f'{acq}_FA.nii.gz'),
                        '-mult',
                        op.join(dtifitdir, f'{acq}.nii')],
                       check=True)
        for suffix in ('V1', 'V2', 'V3', 'FA', 'L1', 'L2', 'L3', 'MD', 'MO', 'S0'):
            os.remove(op.join(dtifitdir, f'{acq}_{suffix}.nii.gz'))



def convert(dtifitdir, conversiondir):
    try:
        shutil.rmtree(conversiondir)
    except OSError:
        pass
    os.makedirs(conversiondir)
    logger.info(f'Converting {dtifitdir} to MRtrix3 format')
    for acq in tqdm(ACQUISITIONS, desc=f'Converting FSL {dtifitdir} to MRtrix3 format'):
        subprocess.run(['peaksconvert',
                        op.join(dtifitdir, f'{acq}.nii'),
                        op.join(conversiondir, f'{acq}.mif'),
                        '-in_format', '3vector',
                        '-in_reference', 'bvec',
                        '-out_format', '3vector',
                        '-out_reference', 'xyz',
                        '-quiet'],
                       check=True)

