from distutils.core import setup
import py2exe
import re, sys, os
from SysProf.windows import profiler
from xml.etree import ElementTree as ET
import modulefinder
from glob import glob

sys.path.append("C:\\Microsoft.VC90.CRT")

data_files = [("Microsoft.VC90.CRT", glob(r'C:\Microsoft.VC90.CRT\*.*'))]

profiler = profiler.Profiler()
data = profiler.profile({'CPU'})
print ET.tostring(data)

def get_version():
    try:
        f = open("_generated_version.py")
    except EnvironmentError:
        return None
    ver = None
    for line in f.readlines():
        mo = re.match("__version__ = '([^']+)'", line)
        if mo:
            ver = mo.group(1)
            break

    # Fix version in Inno Setup file too!
    filedata = None
    with open('../mist.iss', 'r') as file :
      filedata = file.read()
    
    # Replace the target string
    if '@version@' in filedata:
        filedata = filedata.replace('@version@', ver)
    
    # Write the file out again
    with open('../mist.iss', 'w') as file:
      file.write(filedata)

    return ver

class Target:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the versioninfo resources
        self.version = get_version()
        self.company_name = "Fondazione Ugo Bordoni"
        self.copyright = "(c)2010-2015 Fondazione Ugo Bordoni"
        self.name = "MisuraInternet Speed Test"

setup(
  data_files=data_files,
	options = {
		'py2exe': {
			'packages': 'encodings',
            'optimize': 2,
            'includes': ['SysProf.windows.profiler']
 		}
	},
	name = 'mist',
	version = get_version(),
	windows = [
		{"script": "mist.py", 'uac_info': "requireAdministrator", "icon_resources": [(1, "..\\mist.ico")]},
	],
	#packages = ['mist'],
)
