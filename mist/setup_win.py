from distutils.core import setup
import py2exe
import sys, os
from SysProf.windows import profiler
from xml.etree import ElementTree as ET
import modulefinder
from glob import glob

__version__ = '1.1.0'

sys.path.append("C:\\Microsoft.VC90.CRT")

data_files = [("Microsoft.VC90.CRT", glob(r'C:\Microsoft.VC90.CRT\*.*'))]

profiler = profiler.Profiler()
data = profiler.profile({'CPU'})
print ET.tostring(data)


class Target:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the versioninfo resources
        self.version = __version__
        self.company_name = "Fondazione Ugo Bordoni"
        self.copyright = "(c)2012 Fondazione Ugo Bordoni"
        self.name = "MisuraInternet Speed Test"

setup(
  data_files=data_files,
	options = {
		'py2exe': {
			'packages': 'encodings',
      'optimize': 2,
		}
	},
	name = 'mist',
	version = __version__,
	windows = [
		{"script": "mist.py", 'uac_info': "requireAdministrator", "icon_resources": [(1, "..\\mist.ico")]},
	],
	#packages = ['mist'],
)
