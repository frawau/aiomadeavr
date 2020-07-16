#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import setuptools

version = "0.1"

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiomadeavr",
    packages=["aiomadeavr"],
    # packages=setuptools.find_packages(),
    version=version,
    author="François Wautier",
    author_email="francois@wautier.eu",
    description="Library/utility to control Marantz/Denon devices over telnet.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="http://github.com/frawau/aiomadeavr",
    keywords=["Marantz", "Denon", "Control", "Network"],
    license="MIT",
    install_requires=["aiohttp"],
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: MIT License",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
    zip_safe=False,
)
