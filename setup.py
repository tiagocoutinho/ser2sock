# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages


TESTING = any(x in sys.argv for x in ["test", "pytest"])

setup_requirements = []
if TESTING:
    if sys.version_info < (3, 7):
        print("testing ser2tcp needs python >= 3.7")
        exit(1)
    setup_requirements += ["pytest-runner"]
test_requirements = ["pytest", "pytest-cov", "pytest-asyncio"]

with open("README.md") as f:
    description = f.read()

setup(
    name="ser2tcp",
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
    ],
    description="serial to tcp bridge",
    license="GPLv3+",
    long_description=description,
    long_description_content_type="text/markdown",
    keywords="serial line, tcp, bridge, socket, server",
    packages=find_packages(),
    requires=['pyserial'],
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    entry_points={
        'console_scripts': [
            'ser2tcp = ser2tcp:main',
        ],
    },
    url="https://github.com/tiagooutinho/ser2tcp/",
    project_urls={
        "Documentation": "https://tiagocoutinho.github.io/ser2tcp/",
        "Source": "https://github.com/tiagocoutinho/ser2tcp/",
    },
    version="0.1.0",
    python_requires=">=2.6",
    zip_safe=True
)
