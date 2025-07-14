#!/usr/bin/python3

from dataclasses import dataclass
import json
import logging
import os
from os import path as op
import subprocess
import sys
import numpy as np
from tqdm import tqdm

from collections import namedtuple

from . import ACQUISITIONS
from . import GRADTABLE_FIDUCIALS
from . import PEDIRS
from . import PLANES
from . import SLICEORDERS
from . import GradType
from . import KeyvalueType
from . import PEType
from . import utils

logger = logging.getLogger(__name__)

@dataclass
class MetadataTests:
    gradtable: bool
    phase_encoding: bool
    slice_encoding: bool


def metadata(testname, inputdir, formats, tests):

    Mismatch = namedtuple('Mismatch', ['variant',
                                       'metadata_code',
                                       'metadata_reversal',
                                       'metadata_direction',
                                       'description_code',
                                       'description_reversal',
                                       'description_direction',
                                       'transform'])

    sliceencodingdirection_errors = []
    phaseencodingdirection_errors = []
    gradtable_errors = []
    logger.debug(f'Verifying metadata for {testname}:')
    for acq in tqdm(ACQUISITIONS, desc=f'Verifying metadata for {testname}', leave=False):
        logger.debug(f'  Variant {acq}:')
        transform = utils.get_transform(op.join(inputdir, f'{acq}.{formats.image_extension}'))
        transform_linear = np.array([row[0:3] for row in transform[0:3]])
        slicetimingreversal_metadata = None
        bvecs = None
        dw_scheme = None
        metadata = None
        if (tests.phase_encoding and formats.pe_type == PEType.json) \
                or (tests.slice_encoding and formats.keyvalue_type == KeyvalueType.json):
            try:
                with open(op.join(inputdir, f'{acq}.json'), 'r') as f:
                    metadata = json.loads(f.read())
            except FileNotFoundError as e:
                raise FileNotFoundError(f'Missing JSON file for {testname} ({tests})') from e
            try:
                slicetimingreversal_metadata = metadata['SliceTiming'][0] > metadata['SliceTiming'][-1]
            except KeyError:
                pass
        elif (tests.phase_encoding and formats.pe_type == PEType.header) \
                or (tests.slice_encoding and formats.keyvalue_type == KeyvalueType.header):
            assert formats.image_extension == 'mih'
            metadata = {}
            with open(op.join(inputdir, f'{acq}.mih'), 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == 'mrtrix image':
                        continue
                    line_split = line.split(': ')
                    if len(line_split) != 2:
                        line_split = [line_split[0], ': '.join(line_split[1:])]
                    if line_split[0] in metadata:
                        if isinstance(metadata[line_split[0]], list):
                            metadata[line_split[0]].append(line_split[1])
                        else:
                            metadata[line_split[0]] = [metadata[line_split[0]], line_split[1]]
                    else:
                        metadata[line_split[0]] = line_split[1]
            if 'SliceTiming' in metadata:
                slicetiming_metadata = [float(f) for f in metadata['SliceTiming'].split(',')]
                slicetimingreversal_metadata = slicetiming_metadata[0] > slicetiming_metadata[-1]
            transform = [ [int(round(float(f))) for f in line.split(',')] for line in metadata['transform'] ]
        if tests.gradtable:
            if formats.grad_type == GradType.header:
                dw_scheme = [ list(map(float, line.split(','))) for line in metadata['dw_scheme'] ]
            elif formats.grad_type == GradType.b:
                assert 'dw_scheme' not in metadata
                dw_scheme = []
                with open(op.join(inputdir, f'{acq}.grad'), 'r') as f:
                    for line in f.readlines():
                        if line.startswith('#'):
                            continue
                        dw_scheme.append(line)
                dw_scheme = [ list(map(float, line.split())) for line in dw_scheme ]
                assert all(len(line) == 4 for line in dw_scheme)
            elif formats.grad_type == GradType.fsl:
                with open(op.join(inputdir, f'{acq}.bvec'), 'r') as f:
                    bvecs = [ list(map(float, line.split(' '))) for line in f.readlines()]
                assert len(bvecs) == 3
                assert len(bvecs[1]) == len(bvecs[0]) and len(bvecs[2]) == len(bvecs[0])
        phaseencodingdirection_metadata = None
        if formats.pe_type in (PEType.header, PEType.json):
            phaseencodingdirection_metadata = utils.code2direction(metadata['PhaseEncodingDirection'], transform)
        elif formats.pe_type == PEType.table:
            petable = np.loadtxt(op.join(inputdir, f'{acq}.petable'))
            assert all(np.array_equal(petable[rowidx,:], petable[0,:]) for rowidx in range(1, petable.shape[0]))
            pedir_image = petable[0][0:3]
            assert sum(map(bool, pedir_image)) == 1
            assert np.linalg.norm(pedir_image) == 1.0
            phaseencodingdirection_metadata = np.dot(transform_linear, pedir_image).tolist()
        elif formats.pe_type == PEType.topup:
            topupdata = np.loadtxt(op.join(inputdir, f'{acq}.topup'))
            assert all(np.array_equal(topupdata[rowidx,:], topupdata[0,:]) for rowidx in range(1, topupdata.shape[0]))
            pedir_image = topupdata[0][0:3]
            if np.linalg.det(transform_linear) > 0.0:
                pedir_image[0] *= -1.0
            assert sum(map(bool, pedir_image)) == 1
            assert np.linalg.norm(pedir_image) == 1.0
            phaseencodingdirection_metadata = np.dot(transform_linear, pedir_image).tolist()
        elif formats.pe_type == PEType.eddy:
            eddycfg = np.loadtxt(op.join(inputdir, f'{acq}.eddycfg'))
            assert len(eddycfg.shape) == 1
            pedir_image = eddycfg[0:3]
            if np.linalg.det(transform_linear) > 0.0:
                pedir_image[0] *= -1.0
            with open(op.join(inputdir, f'{acq}.eddyidx'), 'r') as f:
                eddyidx = list(map(int, f.read().strip().split(' ')))
            assert all(value == 1 for value in eddyidx)
            phaseencodingdirection_metadata = np.dot(transform_linear, pedir_image).tolist()

        # Can no longer assert this; not all tests will involve gradient tables
        #assert bvecs or dw_scheme
        assert not (bvecs is not None and dw_scheme is not None)

        # Slice encoding direction not explicitly labelled in dcm2niix JSON;
        #   therefore if absent we'll have to assume "k"
        # TODO With latest changes this is likely to be unavailable in some circumstances
        if tests.slice_encoding:
            assert metadata is not None, f"No metadata for {testname}"
            assert slicetimingreversal_metadata is not None

            if 'SliceEncodingDirection' not in metadata:
                if 'dcm2niix' in inputdir:
                    metadata['SliceEncodingDirection'] = 'k'
                else:
                    raise KeyError('Expected "SliceEncodingDirection" missing from ' + op.join(inputdir, f'{acq}'))
            sliceencodingdirection_metadata = utils.code2direction(metadata['SliceEncodingDirection'], transform)
            if slicetimingreversal_metadata:
                sliceencodingdirection_metadata = [-i if i else 0 for i in sliceencodingdirection_metadata]

            sliceencodingdirection_seriesdescription = [i * SLICEORDERS[acq.sliceorder] for i in PLANES[acq.plane]]

            if sliceencodingdirection_metadata != sliceencodingdirection_seriesdescription:
                sliceencodingdirection_errors.append(Mismatch(f'{acq}',
                                                              metadata['SliceEncodingDirection'],
                                                              slicetimingreversal_metadata,
                                                              sliceencodingdirection_metadata,
                                                              acq.plane,
                                                              SLICEORDERS[acq.sliceorder],
                                                              sliceencodingdirection_seriesdescription,
                                                              transform))

        if tests.phase_encoding:
            phaseencodingdirection_seriesdescription = PEDIRS[acq.pedir]
            if phaseencodingdirection_metadata != phaseencodingdirection_seriesdescription:
                phaseencodingdirection_errors.append(Mismatch(f'{acq}',
                                                            metadata['PhaseEncodingDirection'] \
                                                            if formats.pe_type in (PEType.json, PEType.header) \
                                                            else 'N/A',
                                                            False,
                                                            phaseencodingdirection_metadata,
                                                            acq.pedir,
                                                            False,
                                                            phaseencodingdirection_seriesdescription,
                                                            transform))

        if tests.gradtable:
            if formats.grad_type in (GradType.b, GradType.header):
                assert dw_scheme
                fiducials = np.array([[int(round(f)) for f in dw_scheme[row][0:3]] for row in range(1, 4)])
                if not np.array_equal(fiducials, GRADTABLE_FIDUCIALS):
                    gradtable_errors.append([f'{acq}', fiducials])
            elif formats.grad_type == GradType.fsl:
                # Validate bvecs
                # Ideally do this based on description of the format,
                #   rather than relying on MRtrix3 commands,
                #   given that we may need to use this test to validate the latter
                #
                # Skip the first b=0 volume
                bvecs_fiducials = np.array([row[1:4] for row in bvecs])
                logger.debug(f'    Stored bvec fiducials: {bvecs_fiducials.round()}')
                transform_linear = np.array([row[0:3] for row in transform[0:3]])
                logger.debug('    Transform: ' + str(transform_linear.round()))
                #sys.stderr.write('transform_linear: ' + str(transform_linear) + '\n')
                # We transpose the vectors so that they can be premultiplied by the transform matrix
                fiducials_image = np.transpose(bvecs_fiducials)
                # Invert the first element of each 3-vector if necessary
                if np.linalg.det(transform_linear) > 0.0:
                    fiducials_image[:,0] *= -1.0
                logger.debug(f'    Transposed & flipped imagespace fiducials: {fiducials_image.round()}')
                # Transform fiducials from being defined with respect to image axes
                #   to being defined with respect to scanner axes
                #fiducials_real = np.matmul(transform_linear, fiducials_image).round()
                fiducials_real = np.zeros((3,3))
                for gradindex in range(0,3):
                    fiducials_real[gradindex] = np.dot(transform_linear, fiducials_image[gradindex,:])
                #sys.stderr.write('Transform from bvecs ' + str(bvecs_fiducials) + ' to imagespace' + str(fiducials_image) + ' to scannerspace ' + str(fiducials_real) + '\n')
                logger.debug('    Realspace fiducials: ' + str(fiducials_real.round()))
                if not np.array_equal(fiducials_real.round(), GRADTABLE_FIDUCIALS):
                    gradtable_errors.append([f'{acq}', fiducials_real])

    logger.info(f'Results for {testname}:')
    if sliceencodingdirection_errors:
        logger.warning(f'{len(sliceencodingdirection_errors)} errors in slice encoding direction for {testname}:')
        for mismatch in sliceencodingdirection_errors:
            logger.warning(f'  {mismatch.variant}: "{mismatch.metadata_code}" x {-1 if mismatch.metadata_reversal else 1}; transform: {mismatch.transform[0:3]} = {mismatch.metadata_direction} != "{mismatch.description_code}" x {mismatch.description_reversal} = {mismatch.description_direction}')
    else:
        logger.info('No slice encoding direction errors')
    if phaseencodingdirection_errors:
        logger.warning(f'{len(phaseencodingdirection_errors)} errors in phase encoding direction for {testname}:')
        for mismatch in phaseencodingdirection_errors:
            logger.warning(f'  {mismatch.variant}: "{mismatch.metadata_code}"; transform: {mismatch.transform[0:3]} = {mismatch.metadata_direction} != "{mismatch.description_code}" = {mismatch.description_direction}')
    else:
        logger.info('No phase encoding direction errors')
    if gradtable_errors:
        logger.warning(f'{len(gradtable_errors)} errors in gradient table for {testname}:')
        for mismatch in gradtable_errors:
            if np.array_equal(mismatch[1].round() * -1, GRADTABLE_FIDUCIALS):
                logger.warning(f'  {mismatch[0]}: ANTIPODAL')
            else:
                logger.warning(f'  {mismatch[0]}: [{" ".join(str(line) for line in mismatch[1])}]')
    else:
        logger.info('No gradient table errors')



def peaks(testname, inputdir, maskdir, image_extension, mask_extension):
    errors = []
    logger.info(f'Verifying peak orientations for {testname}')
    for v in tqdm(ACQUISITIONS, desc=f'Verifying peak orientations for {testname}', leave=False):
        logger.debug(f'  Variant {v}')
        maskpath = op.join(maskdir, 'temp.mif')
        proc = subprocess.run(['maskfilter', op.join(maskdir, f'{v}.{mask_extension}'), 'erode', maskpath,
                               '-npass', '2',
                               '-config', 'RealignTransform', 'False',
                               '-quiet'])
        proc = subprocess.run(['peakscheck', op.join(inputdir, f'{v}.{image_extension}'),
                               '-mask', maskpath,
                               '-quiet'],
                              capture_output=True)
        os.remove(maskpath)
        if proc.returncode != 0:
            errors.append(f'{v}')
    if errors:
        logger.warning(f'{len(errors)} potential errors in fibre orientations for {testname}: '
                       f'{errors}')

