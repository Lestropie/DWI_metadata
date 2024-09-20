#!/usr/bin/python3

from os import path as op
import shutil
import itertools
from tqdm import tqdm

from dwi_metadata import EXTENSIONS
from dwi_metadata import VARIANTS
from dwi_metadata import tests

from . import dwi2mask
from . import dwi2tensor
from . import mrconvert



# Make sure we get complex non-standard strides that are both LHS and RHS coordinate systems
STRIDES = {'unmodified': None,
           'RAS': '+1,+2,+3,+4',
           'LAS': '-1,+2,+3,+4',
           'complexone': '-3,+1,-2,+4',
           'complextwo': '-3,+1,+2,+4',}



def test_mrconvert_from_dicom(dicomdir, scratchdir):
    for extensions, reorient in tqdm(itertools.product(EXTENSIONS, (False, True)), 
                                     desc='Evaluating MRtrix3 mrconvert from DICOM',
                                     total=len(EXTENSIONS)*2):
        outdir = op.join(scratchdir, f'mrconvert_dcm2{"".join(extensions)}{reorient}')
        mrconvert.run_dicom(dicomdir,
                            outdir,
                            extensions,
                            reorient)
        tests.metadata(f'mrconvert: DICOM to {",".join(extensions)} '
                       f'{"with" if reorient else "without"} reorientation',
                       outdir,
                       extensions)



def test_mrconvert_from_dcm2niix(dcm2niixdir, scratchdir):
    for extensions, reorient, (strides_name, strides_option) in \
        tqdm(itertools.product(EXTENSIONS, (False, True), STRIDES.items()),
             desc='Evaluating MRtrix3 mrconvert from dcm2niix',
             total=len(EXTENSIONS)*2*len(STRIDES)):
             
        outdir = op.join(scratchdir, f'dcm2niix2{"".join(extensions)}{reorient}{strides_name}')
        mrconvert.run_intermediate(dcm2niixdir,
                                   outdir,
                                   ['nii', 'json', 'bvec', 'bval'],
                                   extensions,
                                   reorient,
                                   strides_option)
        tests.metadata(f'mrconvert: dcm2niix to {",".join(extensions)} '
                       f'{"with" if reorient else "without"} reorientation '
                       f'& {strides_name} strides',
                       outdir,
                       extensions)
        shutil.rmtree(outdir)




def test_mrconvert_from_mrconvert(scratchdir):
    for extensions_intermediate, reorient_intermediate, extensions_out, reorient_out, (strides_name, strides_option) \
        in tqdm(itertools.product(EXTENSIONS, (False, True), EXTENSIONS, (False, True), STRIDES.items()),
                desc='Evaluating MRtrix3 mrconvert from multiple formats with stride manipulation',
                total=len(EXTENSIONS)*2*len(EXTENSIONS)*2*len(STRIDES)):
                
        intermediatedir = op.join(scratchdir, f'mrconvert_dcm2{"".join(extensions_intermediate)}{reorient_intermediate}')
        outdir = op.join(scratchdir, f'mrconvert_{"".join(extensions_intermediate)}{reorient_intermediate}'
                                     f'2{"".join(extensions_out)}{reorient_out}{strides_name}')
        mrconvert.run_intermediate(intermediatedir,
                                   outdir,
                                   extensions_intermediate,
                                   extensions_out,
                                   reorient_out,
                                   strides_option)
        tests.metadata(f'mrconvert: {",".join(extensions_intermediate)} '
                       f'{"with" if reorient_intermediate else "without"} reorientation '
                       f'to {",".join(extensions_out)} '
                       f'{"with" if reorient_out else "without"} reorientation '
                       f'& {strides_name} strides',
                       outdir,
                       extensions_out)
        shutil.rmtree(outdir)



def convert_mask(dcm2niixdir, maskpath, scratchdir):
    dwi2mask.convert(dcm2niixdir,
                     'nii',
                     maskpath,
                     op.join(scratchdir, 'mask_dcm2niix'),
                     'nii')
    for extensions, reorient in tqdm(itertools.product(EXTENSIONS, (False, True)),
                                     desc='Back-propagating brain mask to MRtrix3 mrconvert outputs'):
        version_string = f'dcm2{"".join(extensions)}{reorient}'
        mrtrixdir = op.join(scratchdir, f'mrconvert_{version_string}')
        dwi2mask.convert(mrtrixdir,
                         extensions[0],
                         maskpath,
                         op.join(scratchdir, f'mask_mrconvert_{version_string}'),
                         extensions[0])



def test_dwi2tensor(scratchdir):
    dwi2tensor.run(op.join(scratchdir, 'dcm2niix'),
                   ['nii', 'json', 'bvec', 'bval'],
                   op.join(scratchdir, 'mask_dcm2niix'),
                   op.join(scratchdir, 'dwi2tensor_from_dcm2niix'))
    tests.peaks(f'MRtrix3 dwi2tensor from dcm2niix',
                op.join(scratchdir, 'dwi2tensor_from_dcm2niix'),
                op.join(scratchdir, 'mask_dcm2niix'),
                'nii')
    for extensions, reorient in tqdm(itertools.product(EXTENSIONS, (False, True)),
                                     desc='Running MRtrix3 dwi2tensor on MRtrix3 mrconvert outputs',
                                     total=len(EXTENSIONS)*2):
        version_string = f'dcm2{"".join(extensions)}{reorient}'
        outdir = op.join(scratchdir, f'dwi2tensor_from_mrconvert_{version_string}')
        maskdir = op.join(scratchdir, f'mask_mrconvert_{version_string}')
        dwi2tensor.run(op.join(scratchdir, f'mrconvert_{version_string}'),
                       extensions,
                       maskdir,
                       outdir)
        tests.peaks(f'MRtrix3 dwi2tensor from mrconvert {version_string}', outdir, maskdir, extensions[0])

