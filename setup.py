#!/usr/bin/env python3

"""
packaging / installing
"""

# c0103: should use uppercase names
# c0326: no space allowed around keyword argument assignment
# pylint: disable=c0103,c0326

import setuptools

from liveboot.version import __version__

LONG_DESCRIPTION = \
    "See https://github.com/sopnode/liveboot/blob/main/README.md"

# requirements
#
# *NOTE* for ubuntu: also run this beforehand
# apt-get -y install libffi-dev
# which is required before pip can install asyncssh
INSTALL_REQUIRES = [
    'redfish',
    # read the config
    'PyYAML',
    # extract stuff in a data tree
    'jmespath',
    # template rendering
    'jinja2',
    # used in the cloud-init shell script
    'jinja2-cli[yaml]',
    # check the existence of a URL
    'requests',
]

setuptools.setup(
    name="liveboot",
    author="Thierry Parmentelat",
    author_email="thierry.parmentelat@inria.fr",
    description="Testbed Management Framework for Sophia Node",
    long_description=LONG_DESCRIPTION,
    license="CC BY-SA 4.0",
    keywords=['Sophia Node', 'networking testbed'],

    packages=['liveboot'],
    version=__version__,
    python_requires=">=3.10",

    entry_points={ 'console_scripts': ['liveboot = liveboot.cli:main'] },
    scripts=[
        'cloud-init/seed-cloud-init.sh',
        'fedora/build-rpm-liveboot.sh',
        'ubuntu/patch-ubuntu-image.sh',
    ],
    package_data={
        'liveboot': [
            'templates/cloud-init-template.yaml.j2',
        ],
    },

    install_requires=INSTALL_REQUIRES,

    project_urls={
        'source': "https://github.com/sopnode/liveboot/",
    },

    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "Programming Language :: Python :: 3.10",
    ],
)
