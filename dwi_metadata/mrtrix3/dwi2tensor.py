#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import VARIANTS

logger = logging.getLogger(__name__)

def run(indir, extensions, maskdir, dwi2tensordir):
    try:
        shutil.rmtree(dwi2tensordir)
    except OSError:
        pass
    os.makedirs(dwi2tensordir)
    logger.info(f'Running MRtrix3 dwi2tensor from input {indir}')
    for v in tqdm(VARIANTS, desc=f'Running MRtrix3 dwi2tensor on {indir}', leave=False):
        tensor_image_path = op.join(dwi2tensordir, f'{v}_tensor.{extensions[0]}')
        mask_path = op.join(maskdir, f'{v}.{extensions[0]}')
        grad_option = []
        if all(ext in extensions for ext in ('bvec', 'bval')):
            grad_option = ['-fslgrad', op.join(indir, f'{v}.bvec'), op.join(indir, f'{v}.bval')]
        elif 'grad' in extensions:
            grad_option = ['-grad', op.join(indir, f'{v}.grad')]
        subprocess.run(['dwi2tensor', op.join(indir, f'{v}.{extensions[0]}'), tensor_image_path,
                        '-mask', mask_path,
                        '-quiet']
                       + grad_option,
                       check=True)
        subprocess.run(['tensor2metric', tensor_image_path,
                        '-vector', op.join(dwi2tensordir, f'{v}.{extensions[0]}'),
                        '-mask', mask_path,
                        '-modulate', 'fa',
                        '-quiet'],
                       check=True)
        os.remove(tensor_image_path)

