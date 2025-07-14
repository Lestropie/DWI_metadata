#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import ACQUISITIONS
from .. import GradType

logger = logging.getLogger(__name__)

def run(indir, formats, maskdir, dwi2tensordir):
    try:
        shutil.rmtree(dwi2tensordir)
    except OSError:
        pass
    os.makedirs(dwi2tensordir)
    logger.info(f'Running MRtrix3 dwi2tensor from input {indir}')
    for acq in tqdm(ACQUISITIONS, desc=f'Running MRtrix3 dwi2tensor on {indir}', leave=False):
        tensor_image_path = op.join(dwi2tensordir, f'{acq}_tensor.{formats.image_extension}')
        mask_path = op.join(maskdir, f'{acq}.{formats.image_extension}')
        grad_option = []
        if formats.grad_type == GradType.fsl:
            grad_option = ['-fslgrad', op.join(indir, f'{acq}.bvec'), op.join(indir, f'{acq}.bval')]
        elif formats.grad_type == GradType.b:
            grad_option = ['-grad', op.join(indir, f'{acq}.grad')]
        subprocess.run(['dwi2tensor', op.join(indir, f'{acq}.{formats.image_extension}'), tensor_image_path,
                        '-mask', mask_path,
                        '-quiet']
                       + grad_option,
                       check=True)
        subprocess.run(['tensor2metric', tensor_image_path,
                        '-vector', op.join(dwi2tensordir, f'{acq}.{formats.image_extension}'),
                        '-mask', mask_path,
                        '-modulate', 'fa',
                        '-quiet'],
                       check=True)
        os.remove(tensor_image_path)

