# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages

requires = [
    'pyserial',
]

TESTING = any(x in sys.argv for x in ["test", "pytest"])

setup_requirements = []
if TESTING:
    if sys.version_info < (3, 7):
        print("testing ser2sock needs python >= 3.7")
        exit(1)
    setup_requirements += ["pytest-runner"]
test_requirements = ["pytest", "pytest-cov"]

with open("README.md") as f:
    description = f.read()

setup(
    name="ser2sock",
    author="Jose Tiago Macara Coutinho",
    author_email="coutinhotiago@gmail.com",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    description="serial to socket bridge",
    license="GPLv3+",
    long_description=description,
    long_description_content_type="text/markdown",
    keywords="serial line, tcp, udp, bridge, socket, server",
    packages=find_packages(),
    install_requires=requires,
    extras_require={
        ':python_version < "3"': ['selectors2'],
        'web': ['bottle']  # < 0.13 if python 2.6
    },
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    include_package_data=True,
    package_data={
        'ser2sock': ['*.tpl'],
    },
    entry_points={
        'console_scripts': [
            'ser2sock = ser2sock.server:main',
        ],
    },
    url="https://github.com/tiagocoutinho/ser2sock/",
    project_urls={
        "Documentation": "https://tiagocoutinho.github.io/ser2sock/",
        "Source": "https://github.com/tiagocoutinho/ser2sock/",
    },
    version="4.1.2",
    python_requires=">=2.6",
    zip_safe=True
)
