#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import VARIANTS

logger = logging.getLogger(__name__)



def run_dicom(indir, outdir, extensions, reorient):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running MRtrix3 mrconvert from DICOM: '
                f'File extensions {",".join(extensions)}, reorient {reorient}')
    for v in tqdm(VARIANTS,
                  desc=f'Running MRtrix3 mrconvert: '
                       f'DICOM -> {",".join(extensions)}, {"with" if reorient else "without"} reorientation',
                  leave=False):
        cmd = ['mrconvert',
               op.join(indir, f'{v}/'),
               op.join(outdir, f'{v}.{extensions[0]}'),
               '-config', 'RealignTransform', str(reorient),
               '-quiet']
        if 'json' in extensions:
            cmd.extend(['-json_export', op.join(outdir, f'{v}.json')])
        if 'bvec' in extensions and 'bval' in extensions:
            cmd.extend(['-export_grad_fsl', op.join(outdir, f'{v}.bvec'), op.join(outdir, f'{v}.bval')])
        if 'grad' in extensions:
            cmd.extend(['-export_grad_mrtrix', op.join(outdir, f'{v}.grad')])
        subprocess.run(cmd, check=True)




def run_intermediate(indir,
                     outdir,
                     extensions_in,
                     extensions_out,
                     reorient,
                     strides_option):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running {len(VARIANTS)} instances of mrconvert from intermediate input:')
    logger.info(f'  Input {indir}, input file extensions {",".join(extensions_in)};')
    logger.info(f'  Output file extensions {",".join(extensions_out)}, reorient {reorient}, strides {strides_option}')
    for v in tqdm(VARIANTS,
                  desc='Running MRtrix3 mrconvert: '
                       f'{indir} {",".join(extensions_in)} -> {",".join(extensions_out)}, '
                       f'{"with" if reorient else "without"} reorientation, '
                       f'strides {strides_option}',
                  leave=False):
        cmd = ['mrconvert',
               op.join(indir, f'{v}.{extensions_in[0]}'),
               op.join(outdir, f'{v}.{extensions_out[0]}'),
               '-config', 'RealignTransform', str(reorient),
               '-quiet']
        if 'json' in extensions_in:
            cmd.extend(['-json_import', op.join(indir, f'{v}.json')])
        if 'bvec' in extensions_in and 'bval' in extensions_in:
            cmd.extend(['-fslgrad', op.join(indir, f'{v}.bvec'), op.join(indir, f'{v}.bval')])
        if 'grad' in extensions_in:
            cmd.extend(['-grad', op.join(indir, f'{v}.grad')])
        if 'json' in extensions_out:
            cmd.extend(['-json_export', op.join(outdir, f'{v}.json')])
        if 'bvec' in extensions_out and 'bval' in extensions_out:
            cmd.extend(['-export_grad_fsl', op.join(outdir, f'{v}.bvec'), op.join(outdir, f'{v}.bval')])
        if 'grad' in extensions_out:
            cmd.extend(['-export_grad_mrtrix', op.join(outdir, f'{v}.grad')])
        if strides_option:
            cmd.extend(['-strides', strides_option])
        subprocess.run(cmd, check=True)

