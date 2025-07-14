#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from dwi_metadata import ACQUISITIONS
from dwi_metadata import FILE_FORMATS
from dwi_metadata import tests

logger = logging.getLogger(__name__)



def test_dcm2niix(dicomdir, dcm2niixdir):
    run(dicomdir, op.abspath(dcm2niixdir))
    tests.metadata('dcm2niix', dcm2niixdir, FILE_FORMATS[0], tests.MetadataTests(True, True, True))



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
    for acq in tqdm(ACQUISITIONS, desc='Running dcm2niix'):
        subprocess.run(['dcm2niix',
                        '-o', outdir,
                        '-f', '%f',
                        f'{acq}'],
                       capture_output=True,
                       check=True)
    os.chdir(cwd)

