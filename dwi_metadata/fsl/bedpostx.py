#!/usr/bin/python3

import glob
import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import ACQUISITIONS

logger = logging.getLogger(__name__)

# Reduce computational burden of bedpostx
# Can't be run with zero burn-in, as the resulting orientations won't be anatomically faithful
# Default is burn-in b=1000, jumps j=1250, sample every s=25
OPTIONS = ['-b', '500', '-j', '10', '-s', '5']



def run(indir, maskdir, bedpostxdir):
    try:
        shutil.rmtree(bedpostxdir)
    except OSError:
        pass
    os.makedirs(bedpostxdir)
    indir = op.abspath(indir)
    maskdir = op.abspath(maskdir)
    cwd = os.getcwd()
    logger.info(f'Running FSL bedpostx from input {indir}')
    os.chdir(bedpostxdir)
    for acq in tqdm(ACQUISITIONS, desc=f'Running FSL bedpostx on input {indir}'):
        bedpostx_tmpdir = f'{acq}/'
        os.makedirs(bedpostx_tmpdir)
        os.symlink(op.join(indir, f'{acq}.nii'), op.join(bedpostx_tmpdir, 'data.nii'))
        os.symlink(op.join(indir, f'{acq}.bvec'), op.join(bedpostx_tmpdir, 'bvecs'))
        os.symlink(op.join(indir, f'{acq}.bval'), op.join(bedpostx_tmpdir, 'bvals'))
        os.symlink(op.join(maskdir, f'{acq}.nii'), op.join(bedpostx_tmpdir, 'nodif_brain_mask.nii'))
        subprocess.run(['bedpostx', bedpostx_tmpdir] + OPTIONS,
                       capture_output=True,
                       check=True)
        for item in glob.glob(op.join(bedpostxdir, '*merged*')):
            os.remove(item)
    os.chdir(cwd)



def convert(bedpostxdir, conversiondir, use_dyads):
    try:
        shutil.rmtree(conversiondir)
    except OSError:
        pass
    os.makedirs(conversiondir)
    logger.info(f'Converting {bedpostxdir} to MRtrix3 format')
    for acq in tqdm(ACQUISITIONS, desc=f'Converting FSL {bedpostxdir} to MRtrix3 format'):
        bedpostx_subdir = os.path.join(bedpostxdir, f'{acq}.bedpostX')
        tmppath = op.join(conversiondir, 'tmp.mif')
        if use_dyads:
            for index in range(1, 4):
                subprocess.run(['mrcalc',
                                op.join(bedpostx_subdir, f'dyads{index}.nii.gz'),
                                op.join(bedpostx_subdir, f'mean_f{index}samples.nii.gz'),
                                '-mult',
                                op.join(conversiondir, f'tmp{index}.mif'),
                                '-config', 'RealignTransform', 'false',
                                '-quiet'],
                               check=True)
            subprocess.run(['mrcat',
                            op.join(conversiondir, 'tmp1.mif'),
                            op.join(conversiondir, 'tmp2.mif'),
                            op.join(conversiondir, 'tmp3.mif'),
                            tmppath,
                            '-axis', '3',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            for index in range(1, 4):
                os.remove(op.join(conversiondir, f'tmp{index}.mif'))
            subprocess.run(['peaksconvert',
                            tmppath,
                            op.join(conversiondir, f'{acq}.mif'),
                            '-in_format', '3vector',
                            '-in_reference', 'bvec',
                            '-out_format', '3vector',
                            '-out_reference', 'xyz',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            os.remove(tmppath)
        else:
            subprocess.run(['mrcat',
                            op.join(bedpostx_subdir, 'mean_f1samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_ph1samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_th1samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_f2samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_ph2samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_th2samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_f3samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_ph3samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_th3samples.nii.gz'),
                            tmppath,
                            '-axis', '3',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            subprocess.run(['peaksconvert',
                            tmppath,
                            op.join(conversiondir, f'{acq}.mif'),
                            '-in_format', 'spherical',
                            '-in_reference', 'bvec',
                            '-out_format', '3vector',
                            '-out_reference', 'xyz',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            os.remove(tmppath)

