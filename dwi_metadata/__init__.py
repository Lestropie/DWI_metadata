#!/usr/bin/python3

from dataclasses import dataclass
from enum import Enum
import itertools
import numpy as np

# All possible configurations
# Need to handle diffusion gradient table vs. slice / phase encoding differently here:
# - Diffusion gradients are applied using the Device Coordinate System (DCS),
#   which for a patient in head first supine (HFS) results in:
#   - +X: Left     -> [-1, 0, 0] in RAS
#   - +Y: Anterior -> [ 0, 1, 0] in RAS
#   - +Z: Inferior -> [ 0, 0,-1] in RAS
# - Image encoding is based on the Patient Coordinate System (PCS),
#   which is independent of patient bedding:
#   - Sag+: Left      -> [-1, 0, 0] in RAS
#   - Cor+: Posterior -> [ 0,-1, 0] in RAS
#   - Tra+: Superior  -> [ 0, 0, 1] in RAS
PLANES = {
    'Tra': [ 0, 0, 1],
    'Cor': [ 0,-1, 0],
    'Sag': [-1, 0, 0]
}
SLICEORDERS = {
    'Asc': +1,
    'Des': -1,
}
PEDIRS = {
    'RL': [-1, 0, 0],
    'LR': [ 1, 0, 0],
    'AP': [ 0,-1, 0],
    'PA': [ 0, 1, 0],
    'HF': [ 0, 0,-1],
    'FH': [ 0, 0, 1]
}
GRADTABLE_FIDUCIALS = np.array([[-1, 0, 0],
                                [ 0, 1, 0],
                                [ 0, 0,-1]])

DIRECTION_CODES_ANATOMICAL = PEDIRS
DIRECTION_CODES_BIDS = {'i-': [-1, 0, 0],
                        'i':  [ 1, 0, 0],
                        'j-': [ 0,-1, 0],
                        'j':  [ 0, 1, 0],
                        'k-': [ 0, 0,-1],
                        'k':  [ 0, 0, 1]}


GradType = Enum('GradType', 'header fsl b none')
KeyvalueType = Enum('KeyvalueType', 'header json none')
PEType = Enum('PEType', 'header json table topup eddy none')

@dataclass
class FileFormat:
    description: str
    symbolic_name: str
    image_extension: str
    grad_type: GradType
    keyvalue_type: KeyvalueType
    pe_type: PEType

FILE_FORMATS = [
    FileFormat('NIfTI w. bvecs/bvals and JSON', 'niibvecbvaljson', 'nii', GradType.fsl, KeyvalueType.json, PEType.json),
    FileFormat('NIfTI w. FSL eddy phase-encoding files', 'niieddy', 'nii', GradType.none, KeyvalueType.none, PEType.eddy),
    FileFormat('NIfTI w. full topup phase-encoding table', 'niitopup', 'nii', GradType.none, KeyvalueType.none, PEType.topup),
    FileFormat('MIH format w. all read from header', 'mih', 'mih', GradType.header, KeyvalueType.header, PEType.header),
    FileFormat('MIF format w. external metadata', 'mifjsongrad', 'mif', GradType.b, KeyvalueType.json, PEType.json),
    FileFormat('MIF format w. external phase encoding table', 'mifpetable', 'mif', GradType.none, KeyvalueType.none, PEType.table),
]

# Generate set of all acquired series
class Acquisition:
    def __init__(self, plane, sliceorder, pedir):
        self.plane = plane
        self.sliceorder = sliceorder
        self.pedir = pedir
    def __format__(self, fmt):
        return f'DWI_{self.plane}_{self.sliceorder}_{self.pedir}'
ACQUISITIONS = []
for plane, pedir, sliceorder in itertools.product(PLANES, PEDIRS, SLICEORDERS):
    if not any(bool(a) and bool(b) for a, b in zip(PLANES[plane], PEDIRS[pedir])):
        ACQUISITIONS.append(Acquisition(plane, sliceorder, pedir))

