ARG MAKE_JOBS="1"
ARG DEBIAN_FRONTEND="noninteractive"

FROM python:3.11-slim AS base
# Not using buster as cmake is too old
FROM buildpack-deps:bookworm AS base-builder

# Install required dependencies for all versions of MRtrix3 to be used
FROM base-builder AS mrtrix3-builder
RUN apt-get -qq update \
    && apt-get install -yq --no-install-recommends \
        libeigen3-dev \
        libfftw3-dev \
        libpng-dev \
        libtiff-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

FROM mrtrix3-builder AS mrtrix3-eval-builder
# Version of MRtrix3 to be evaluated
ARG MRTRIX3_GIT_COMMITISH="master"
# Command-line arguments for `./configure`
ARG MRTRIX3_CONFIGURE_FLAGS="-nogui"
# Command-line arguments for `./build`
ARG MRTRIX3_BUILD_FLAGS="-persistent -nopaginate"
ARG MAKE_JOBS
WORKDIR /opt/mrtrix3
RUN git clone -b $MRTRIX3_GIT_COMMITISH --depth 1 https://github.com/MRtrix3/mrtrix3.git . \
    && python3 ./configure $MRTRIX3_CONFIGURE_FLAGS \
    && NUMBER_OF_PROCESSORS=$MAKE_JOBS python3 ./build $MRTRIX3_BUILD_FLAGS \
    && rm -rf tmp

# Additional version of MRtrix3 that includes additional features for fibre orientation evaluation
FROM mrtrix3-builder AS mrtrix3-peakscmds-builder
ARG MRTRIX3_GIT_COMMITISH="new_peaks_cmds"
ARG MRTRIX3_CONFIGURE_FLAGS="-DMRTRIX_BUILD_GUI=OFF"
# Can't specify "peakscheck" as a target since no such target is constructed for cmake
ARG MRTRIX3_BUILD_TARGETS="peaksconvert LinkPythonAPIFiles LinkPythonCommandFiles"
ARG MAKE_JOBS
WORKDIR /opt/peakscmds
RUN apt-get -qq update \
    && apt-get install -yq --no-install-recommends \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*
# TODO Still getting the "MRtrix3 base version does not match git tag" issue
# Possible solution: Don't do a shallow clone
# Not finding NIfTI headers?
# - Can't do targeted build as third-party files are then not pulled
RUN git clone -b $MRTRIX3_GIT_COMMITISH https://github.com/MRtrix3/mrtrix3.git . \
    && cmake -Bbuild -GNinja $MRTRIX3_CONFIGURE_FLAGS \
    && cmake --build build -j $MAKE_JOBS \
    && find build/bin/ -type f ! -name 'peaks*' -delete \
    && find build/bin/ -type f -name "peaks2*" -delete \
    && echo "Rebuilt new_peaks_cmds"

# Install dcm2niix
FROM base-builder AS dcm2niix-builder
WORKDIR /opt/dcm2niix
ARG DCM2NIIX_TAG="v1.0.20240202"
RUN apt-get -qq update \
    && apt-get install -yq --no-install-recommends \
        cmake \
    && rm -rf /var/lib/apt/lists/*
RUN git clone -b $DCM2NIIX_TAG --depth 1 https://github.com/rordenlab/dcm2niix.git . \
    && mkdir build \
    && cd build \
    && cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON .. \
    && make

# Install FSL
FROM base-builder AS fsl-installer
WORKDIR /opt/fsl
RUN apt-get -qq update \
    && apt-get install -yq --no-install-recommends \
        bc \
        dc \
        file \
        libfontconfig1 \
        libfreetype6 \
        libgl1-mesa-dev \
        libgl1-mesa-dri \
        libglu1-mesa-dev \
        libgomp1 \
        libice6 \
        libopenblas0 \
        libxcursor1 \
        libxft2 \
        libxinerama1 \
        libxrandr2 \
        libxrender1 \
        libxt6 \
        python3 \
        sudo \
        wget \
    && rm -rf /var/lib/apt/lists/*
RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py \
    && python3 fslinstaller.py -V 6.0.7.7 -d /opt/fsl -m -o

# Download data
FROM base-builder AS data-downloader
WORKDIR /data
RUN wget https://osf.io/s4az7/download -O DWI.tar.gz \
    && tar -xvf DWI.tar.gz \
    && rm -f DWI.tar.gz

# Build final image.
FROM base AS final

# Install runtime system dependencies.
RUN apt-get -qq update \
    && apt-get install -yq --no-install-recommends \
        binutils \
        dc \
        less \
        libfftw3-single3 \
        libfftw3-double3 \
        libfftw3-bin \
        libgomp1 \
        liblapack3 \
        libpng16-16 \
        libtiff6 \
        libquadmath0 \
        python3-distutils \
        python3-numpy \
        python3-tqdm \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mrtrix3-eval-builder /opt/mrtrix3 /opt/mrtrix3
COPY --from=mrtrix3-peakscmds-builder /opt/peakscmds /opt/peakscmds
COPY --from=dcm2niix-builder /opt/dcm2niix /opt/dcm2niix
COPY --from=fsl-installer /opt/fsl /opt/fsl
COPY --from=data-downloader /data /data
COPY execute.py /execute.py

ENV FSLDIR="/opt/fsl" \
    FSLOUTPUTTYPE="NIFTI_GZ" \
    FSLMULTIFILEQUIT="TRUE" \
    FSLTCLSH="/opt/fsl/bin/fsltclsh" \
    FSLWISH="/opt/fsl/bin/fslwish" \
    PATH="/opt/mrtrix3/bin:/opt/peakscmds/build/bin:/opt/dcm2niix/build/bin:/opt/fsl/share/fsl/bin:$PATH"

CMD ["/execute.py", "/data"]
