from setuptools import setup, find_packages
import re

vfile="mnemo/version.py"
verstrline = open(vfile, "rt").read()
VSRE = r"^__version__\s*=\s*(['\"])(.*)\1"
g = re.search(VSRE, verstrline, re.M)
if g:
    __version__ = g.group(2)
else:
    raise RuntimeError(f"Unable to find version in file '{vfile}")

setup(
  name='mnemo',
  version=__version__,
  description='mnemo: The Mnemosyne Language interpreter',
  long_description='An implementation of a specialized parallel programming simulator in pure Python',
  url='https://github.com/stevenrbrandt/mnemo.git',
  author='Steven R. Brandt',
  author_email='steven@stevenrbrandt.com',
  license='LGPL',
  packages=['mnemo'],
  entry_points = {
    'console_scripts' : ['mnemo=mnemo:main'],
  },
  package_data = {
    'piraha': ['py.typed','mnemo.peg','lib'],
  },
  include_package_data=True,
  install_requires=['piraha']
)
