from setuptools import setup

version = "0.2.dev0"

long_description = "\n\n".join([open("README.rst").read(), open("CHANGES.rst").read()])

install_requires = [
    "configparser==3.7.4",
    "GDAL==2.4.1",
    "gsconfig-py3==1.0.7",
    "tqdm==4.40.2",
    "json5==0.8.5",
    "psycopg2==2.8.4",
]

tests_require = [
    "pytest",
    "mock",
    "pytest-cov",
    "pytest-flakes",
    "pytest-black",
]

setup(
    name="nens-gs-uploader",
    version=version,
    description="This tools corrects vectors and uploads to the geoserver for wms and wfs purposes.",
    long_description=long_description,
    # Get strings from http://www.python.org/pypi?%3Aaction=list_classifiers
    classifiers=["Programming Language :: Python", "Framework :: Django"],
    keywords=[],
    author="Chris Kerklaan",
    author_email="chris.kerklaan@nelen-schuurmans.nl",
    url="https://github.com/nens/nens-gs-uploader",
    license="MIT",
    packages=["nens_gs_uploader"],
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={"test": tests_require},
    entry_points={
        "console_scripts": [
            "run-nens-gs-uploader = nens_gs_uploader.nens_gs_uploader:main"
        ]
    },
)
