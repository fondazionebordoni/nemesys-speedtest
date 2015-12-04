'''
Created on 20/ott/2010

@author: Albenzio Cirillo

Profiler per Piattaforme LINUX

N.B.: funziona con psutil 0.3.0 o superiore

'''
from ..LocalProfilerFactory import LocalProfiler
from ..RisorsaFactory import Risorsa
from ..NemesysException import RisorsaException
import xml.etree.ElementTree as ET
import psutil, os
import platform
import netifaces
import socket

class CPU(Risorsa):

    def __init__(self):
        Risorsa.__init__(self)
        self._chisono = "sono una CPU"
        self._params = ['cpuLoad']
        #print psutil.__version__

    def cpuLoad(self):
        val = psutil.cpu_percent(0.5)
        return self.xmlFormat('cpuLoad', val)

class RAM(Risorsa):
    def __init__(self):
        Risorsa.__init__(self)
        self._params = ['total_memory', 'percentage_ram_usage']

    def total_memory(self):
        #Necessaria psutil 0.4.1
        val = psutil.phymem_usage().total
        return self.xmlFormat('totalPhysicalMemory', val)

    def percentage_ram_usage(self):
        #Necessaria psutil 0.4.1
        val = psutil.phymem_usage().percent
        return self.xmlFormat('RAMUsage', val)

class sistemaOperativo(Risorsa):

    def __init__(self):
        Risorsa.__init__(self)
        self._params = ['version']

    def version (self):
        valret = platform.platform()
        return self.xmlFormat('OperatingSystem', valret)

class disco(Risorsa):

    def __init__(self):
        Risorsa.__init__(self)
        self._params = ['byte_transfer']

    def byte_transfer(self):
        return 0

class rete(Risorsa):

    def __init__(self):
        Risorsa.__init__(self)
        self.ipaddr = ""
        self._params = ['profileDevice']

    def getipaddr(self):
        if self.ipaddr == "":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("www.fub.it", 80))
                self.ipaddr = s.getsockname()[0]
            except socket.gaierror:
                pass
                #raise RisorsaException("Connessione Assente")
        else:
            pass
        return self.ipaddr

    def get_if_ipaddress(self, ifname):
        neti_names = netifaces.interfaces()
        ipval = '127.0.0.1'
        for nn in neti_names:
            if ifname == nn:
                try:
                    ipval = netifaces.ifaddresses(ifname)[netifaces.AF_INET][0]['addr']
                except:
                    ipval = '127.0.0.1'
        return ipval

    def profileDevice(self):
        
        devpath = '/sys/class/net/'
        wireless = ['wireless', 'wifi', 'wi-fi', 'senzafili', 'wlan']
        descriptors = ['address', 'type', 'operstate', 'uevent']
        
        self.ipaddr = self.getipaddr()
        devlist = os.listdir(devpath)
        maindevxml = ET.Element('rete')
        if len(devlist) > 0:
            for dev in devlist:
                devIsAct = 'False' # by def
                ipdev = self.get_if_ipaddress(dev)
                if (ipdev == self.ipaddr):
                    devIsAct = 'True'
                    
                val = {}
                for des in descriptors:
                    fname = devpath + str(dev) + '/' + str(des)
                    f = open(fname)
                    val[des] = f.read().strip('\n')
                    #print des, '=', val[des]

                devxml = ET.Element('NetworkDevice')

                if val['operstate'] == "up":
                    devStatus = 'Enabled'
                else:
                    devStatus = 'Disabled'
                    
                if (val['type'] == '1'):
                    val['type'] = 'Ethernet 802.3'
                elif (val['type'] == '512'):
                    val['type'] = 'WWAN'
                
                for word in wireless:
                    if word in val['uevent']:
                        val['type'] = 'Wireless'
                
                devxml.append(self.xmlFormat('Name', dev))
                devxml.append(self.xmlFormat('Device', dev))
                devxml.append(self.xmlFormat('Status', devStatus))
                devxml.append(self.xmlFormat('isActive', devIsAct))
                devxml.append(self.xmlFormat('Type', val['type']))
                devxml.append(self.xmlFormat('IPaddress', ipdev))
                devxml.append(self.xmlFormat('MACaddress', val['address']))
                
                maindevxml.append(devxml)
                del devxml

        return maindevxml


class Profiler(LocalProfiler):

    def __init__(self):
        available_resources = set(['CPU', 'RAM', 'sistemaOperativo', 'rete'])
        LocalProfiler.__init__(self, available_resources)

    def profile(self, resource = set()):
        return super(Profiler, self).profile(__name__, resource)
