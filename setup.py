import os
from setuptools import setup, find_packages
from pathlib import Path
import ddent

root_dir = Path.cwd()
req_file = root_dir / "requirements.txt"

requirements = req_file.open().read().split("\n")

setup(
    name='PyDDENT',
    version=ddent.__version__,
    setup_requires=["setuptools_scm"],
    description=f'PyDDENT {ddent.__version__}',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    scripts=['scripts/ingest_dbgap_table']
)
