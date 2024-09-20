#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from dwi_metadata import VARIANTS
from dwi_metadata import tests

logger = logging.getLogger(__name__)



def test_dcm2niix(dicomdir, dcm2niixdir):
    run(dicomdir, op.abspath(dcm2niixdir))
    tests.metadata('dcm2niix', dcm2niixdir, ('nii', 'json', 'bvec', 'bval'))
    


def run(indir, outdir):
    indir = op.abspath(indir)
    cwd = os.getcwd()
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    os.chdir(indir)
    logger.info(f'Running dcm2niix')
    for v in tqdm(VARIANTS, desc='Running dcm2niix'):
        subprocess.run(['dcm2niix',
                        '-o', outdir,
                        '-f', '%f',
                        f'{v}'],
                       capture_output=True,
                       check=True)
    os.chdir(cwd)

