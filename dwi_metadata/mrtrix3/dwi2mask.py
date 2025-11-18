#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import ACQUISITIONS

logger = logging.getLogger(__name__)

def run(indir, outdir, outpath):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    try:
        os.remove(outpath)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running MRtrix3 dwi2mask')
    mrmath_cmd = ['mrmath']
    for acq in tqdm(ACQUISITIONS, desc='Generating homologated brain mask'):
        out_path = op.join(outdir, f'{acq}.mif')
        subprocess.run(['dwi2mask', op.join(indir, f'{acq}/'), out_path,
                        '-config', 'RealignTransform', 'true',
                        '-quiet'],
                       check=True)
        mrmath_cmd.append(out_path)
    mrmath_cmd.extend(['max', outpath, '-datatype', 'bit', '-quiet'])
    subprocess.run(mrmath_cmd, check=True)
    logger.info(f'dwi2mask results aggregated as {outpath}')
    for acq in ACQUISITIONS:
        os.remove(op.join(outdir, f'{acq}.mif'))



def convert(indir, in_extension, maskpath, outdir, out_extension):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    # Want to transform the aggregate mask image back to the originating image spaces
    # This is not fixed per variant; it depends on the image to which the mask is to be matched,
    #   and this could depend on the conversion software / whether or not MRtrix3 performed transform realignment
    logger.info(f'Converting aggregate mask to match {indir}')
    for acq in tqdm(ACQUISITIONS, desc=f'Back-propagating homologated brain mask to match {indir}', leave=False):
        inpath = op.join(indir, f'{acq}.{in_extension}')
        outpath = op.join(outdir, f'{acq}.{out_extension}')
        if not op.exists(inpath):
            raise FileNotFoundError(f'Cannot convert mask for "{inpath}"')
        in_strides = subprocess.run(['mrinfo', inpath,
                                     '-strides',
                                     '-config', 'RealignTransform', 'true',
                                     '-quiet'],
                                    capture_output=True,
                                    text=True).stdout
        in_strides = [int(item) for item in in_strides.strip().split(' ')]
        out_strides = in_strides[0:3]
        subprocess.run(['mrconvert', maskpath, outpath,
                        '-strides', ','.join(map(str, out_strides)),
                        '-quiet'],
                       check=True)

