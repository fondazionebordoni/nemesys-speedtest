# sysmonitor.py
# -*- coding: utf8 -*-

# Copyright (c) 2010 Fondazione Ugo Bordoni.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from collections import OrderedDict
from threading import Thread


from SysProf.NemesysException import LocalProfilerException, RisorsaException, FactoryException
from SysProf import LocalProfilerFactory
from xml.etree import ElementTree as ET
from errorcoder import Errorcoder
from contabyte import Contabyte
from platform import system
from pcapper import Pcapper
from logger import logging

import sysmonitorexception
import checkhost
import netifaces
import xmltodict
import pktman
import socket
import paths
import time
import re


if (system().lower().startswith('win')):
  from SysProf.windows import profiler
elif (system().lower().startswith('lin')):
  from SysProf.linux import profiler
else:
  from SysProf.darwin import profiler


STRICT_CHECK = True

CHECK_ALL = "ALL"
CHECK_MEDIUM = "MEDIUM"

RES_OS = 'OS'
RES_CPU = 'CPU'
RES_RAM = 'RAM'
RES_ETH = 'Ethernet'
RES_WIFI = 'Wireless'
RES_HSPA = 'Mobile'
RES_DEV = 'Device'
RES_MAC = 'MAC'
RES_IP = 'IP'
RES_MASK = 'MASK'
RES_HOSTS = 'Hosts'
RES_TRAFFIC = 'Traffic'

STATUS = 'status'
VALUE = 'value'
INFO = 'info'
TIME = 'time'

NETIF_TIME = None
NETIF_1 = None
NETIF_2 = None

tag_results = 'SystemProfilerResults'
tag_threshold = 'SystemProfilerThreshold'
tag_avMem = 'RAM.totalPhysicalMemory'
tag_memLoad = 'RAM.RAMUsage'
tag_wireless = 'wireless.ActiveWLAN'
tag_ip = 'ipAddr' #to check
tag_sys = 'sistemaOperativo.OperatingSystem'
tag_cpu = 'CPU.cpuLoad'
tag_mac = 'rete.NetworkDevice/MACAddress'
tag_activeNic = 'rete.NetworkDevice/isActive'
tag_cores = 'CPU.cores'
tag_proc = 'CPU.processor'
tag_hosts = 'hostNumber'
#tag_wireless = 'rete.NetworkDevice/Type'


#' SOGLIE '#
th_host = 1           # Massima quantità di host in rete
th_avMem = 134217728  # Minima memoria disponibile
th_memLoad = 95       # Massimo carico percentuale sulla memoria
th_cpu = 85           # Massimo carico percentuale sulla CPU
#'--------'#


logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)

  
class sysMonitor(Thread):
  def __init__(self):
    
    self._blank = OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])
    
    self._system = OrderedDict \
    ([ \
    (RES_OS,self._blank),\
    (RES_CPU,self._blank),\
    (RES_RAM,self._blank),\
    (RES_ETH,self._blank),\
    (RES_WIFI,self._blank),\
    (RES_HSPA,self._blank),\
    (RES_DEV,self._blank),\
    (RES_MAC,self._blank),\
    (RES_IP,self._blank),\
    (RES_MASK,self._blank),\
    (RES_HOSTS,self._blank),\
    (RES_TRAFFIC,self._blank) \
    ])
    
    self._checks = OrderedDict \
    ([ \
    (RES_OS,self._get_os),\
    (RES_CPU,self._check_cpu),\
    (RES_RAM,self._check_mem),\
    (RES_ETH,self._check_ethernet),\
    (RES_WIFI,self._check_wireless),\
    (RES_HSPA,self._check_hspa),\
    (RES_DEV,self._getDev),\
    (RES_MAC,self._get_mac),\
    (RES_IP,self.getIp),\
    (RES_MASK,self._get_mask),\
    (RES_HOSTS,self._check_hosts),\
    (RES_TRAFFIC,self._check_traffic) \
    ])
  
  
  def interfaces(self):
    devices = self._get_NetIF()
    for device in devices.findall('rete/NetworkDevice'):
      dev = xmltodict.parse(ET.tostring(device))
      dev = dev['NetworkDevice']
      logger.info("============================================")
      for key, val in dev.items(): 
        logger.info("| %s : %s" % (key, val))
    logger.info("============================================")
  
  
  def _get_values(self, tagrisorsa, xmlresult, tag = tag_results):
    #' Estrae informazioni dal SystemProfiler '#
    values = {}
    try:
      for subelement in xmlresult.find(tagrisorsa):
        values.update({subelement.tag:subelement.text})
    except Exception as e:
      logger.warning('Errore durante il recupero dello stato del computer. %s' % e)
      raise Exception('Errore durante il recupero dello stato del computer.')
  
    return values
  
  
  def _get_status(self, res):
    #logger.debug('Recupero stato della risorsa %s' % res)
    data = ET.ElementTree()
  
    try:
        profiler = LocalProfilerFactory.getProfiler()
        data = profiler.profile(set([res]))
    except FactoryException as e:
      logger.error ('Problema nel tentativo di istanziare la classe: %s' % e)
      raise sysmonitorexception.FAILPROF
    except RisorsaException as e:
      logger.error ('Problema nel tentativo di istanziare la risorsa: %s' % e)
      raise sysmonitorexception.FAILPROF
    except LocalProfilerException as e:
      logger.error ('Problema nel tentativo di istanziare il profiler: %s' % e)
      raise sysmonitorexception.FAILPROF
    except Exception as e:
      logger.error('Non sono riuscito a trovare lo stato del computer con SystemProfiler: %s.' % e)
      raise sysmonitorexception.FAILPROF
    
    return self._get_values(res, data)
  
  
  def _get_string_tag(self, tag, value, res):
    
    values = self._get_status(res)
    
    try:
      value = str(values[tag])
    except Exception as e:
      logger.error('Errore in lettura del paramentro "%s" di SystemProfiler: %s' % (tag, e))
      if STRICT_CHECK:
        raise sysmonitorexception.FAILREADPARAM
        
    if value == 'None':
      return None
    
    return value
  
  
  def _get_float_tag(self, tag, value, res):
  
    values = self._get_status(res)
  
    if (value == None):
      logger.error('Errore nel valore del paramentro "%s" di SystemProfiler.' % tag)
      raise sysmonitorexception.FAILREADPARAM
  
    try:
      value = float(values[tag])
    except ValueError:
      value = None
    except Exception as e:
      logger.error('Errore in lettura del paramentro "%s" di SystemProfiler: %s' % (tag, e))
      if STRICT_CHECK:
        raise sysmonitorexception.FAILREADPARAM
  
    return value
  
  
  def _get_os(self, res = RES_OS):
    
    try:
      
      value = self._get_string_tag(tag_sys.split('.', 1)[1], 1, tag_sys.split('.', 1)[0])
      info = ("Sistema Operativo %s" % value)
      status = True 
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_cpu(self, res = RES_CPU):
    
    try:
      
      num_check = 0
      tot_value = 0
      
      value = None
      
      for check in range(4):
        value = self._get_float_tag(tag_cpu.split('.', 1)[1], th_cpu - 1, tag_cpu.split('.', 1)[0])
        if value != None:  
          tot_value += value 
          num_check += 1
          if value < th_cpu:
            break
      
      value = tot_value / float(num_check)
      if value < 0 or value > 100:
        raise sysmonitorexception.BADCPU
      if value > th_cpu:
        raise sysmonitorexception.WARNCPU
    
      info = 'Utilizzato il %s%% del processore' % value
      status = True
    
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_mem(self, res = RES_RAM):
    
    try:
      
      for check in range(3):
        value = None
        avMem = self._get_float_tag(tag_avMem.split('.')[1], th_avMem + 1, tag_avMem.split('.')[0])
        if avMem != None:
          value = avMem
          if avMem < 0:
            raise sysmonitorexception.BADMEM
          if avMem < th_avMem:
            raise sysmonitorexception.LOWMEM
          break
        else:
          avMem = 'unknow'
          value = avMem
    
      for check in range(3):
        value = None
        memLoad = self._get_float_tag(tag_memLoad.split('.')[1], th_memLoad - 1, tag_memLoad.split('.')[0])
        if memLoad != None:
          value = memLoad
          if memLoad < 0 or memLoad > 100:
            raise sysmonitorexception.INVALIDMEM
          if memLoad > th_memLoad:
            raise sysmonitorexception.OVERMEM
          break
        else:
          memLoad = 'unknow'
          value = memLoad
    
      info = 'Utilizzato il %s%% di %d GB della memoria' % (memLoad, avMem / (1000*1000*1000))
      status = True
    
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_ethernet(self, res = RES_ETH):
  
    try:
  
      value = -1
      info = 'Dispositivi ethernet non presenti.'
      devices = self._get_NetIF(True)
      
      for device in devices.findall('rete/NetworkDevice'):
        #logger.debug(ET.tostring(device))
        type = device.find('Type').text
        if (type == 'Ethernet 802.3'):
          
          if (system().lower().startswith('win')):
            guid = device.find('GUID').text
            dev_info = self.getDevInfo(guid)
            if (dev_info != None):
              dev_type = dev_info['type']
              if (dev_type == 0 or dev_type == 14):
                status = int(device.find('Status').text)
                if (status == 7 and value != 1):
                  value = 0
                  info = 'Dispositivi ethernet non attivi.'
                  raise sysmonitorexception.WARNETH
                elif (status == 2):
                  value = 1
                  info = 'Dispositivi ethernet attivi.'
                  
          elif (system().lower().startswith('lin')):
            status = device.find('Status').text
            isAct = device.find('isActive').text
            if (status == 'Disabled' and value != 1):  
              value = 0
              info = 'Dispositivi ethernet non attivi.'
              raise sysmonitorexception.WARNETH
            elif (status == 'Enabled' and isAct == 'True'):
              value = 1
              info = 'Dispositivi ethernet attivi.'
                
      if (value == -1):
        raise sysmonitorexception.WARNETH
                
      status = True
    
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_wireless(self, res = RES_WIFI):
  
    try:
      
      value = -1
      info = 'Dispositivi wireless non presenti.'
      devices = self._get_NetIF(True)
      
      for device in devices.findall('rete/NetworkDevice'):
        #logger.debug(ET.tostring(device))
        type = device.find('Type').text
        if (type == 'Wireless'):
          
          if (system().lower().startswith('win')):
            guid = device.find('GUID').text
            dev_info = self.getDevInfo(guid)
            if (dev_info != None):
              dev_type = dev_info['type']
              if (dev_type == 0 or dev_type == 25):
                status = int(device.find('Status').text)
                if (status == 7 and value != 1):
                  value = 0
                  info = 'Dispositivi wireless non attivi.'
                elif (status == 2):
                  value = 1
                  info = 'Dispositivi wireless attivi.'
                  raise sysmonitorexception.WARNWLAN
                
          elif (system().lower().startswith('lin')):  
            status = device.find('Status').text
            if (status == 'Disabled' and value != 1):  
              value = 0
              info = 'Dispositivi wireless non attivi.'
            elif (status == 'Enabled'):
              value = 1
              info = 'Dispositivi wireless attivi.'
              raise sysmonitorexception.WARNWLAN
                
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_hspa(self, res = RES_HSPA):
  
    try:
      
      value = -1
      info = 'Dispositivi HSPA non presenti.'
      
      if (system().lower().startswith('lin')):
        info = 'Dispositivi HSPA non presenti o non attivi.'
      
      devices = self._get_NetIF(True)
      
      for device in devices.findall('rete/NetworkDevice'):
        #logger.debug(ET.tostring(device))
        type = device.find('Type').text
        
        if (type == 'External Modem'):
          dev_id = device.find('ID').text
          if (re.search('USB',dev_id)):
            value = 0
            info = 'Dispositivi HSPA non attivi.'
            dev_info = self.getDevInfo()
            if (dev_info != None):
              dev_type = dev_info['type']
              dev_mask = dev_info['mask']
              if (dev_type == 3 or dev_type == 17 or dev_mask == '255.255.255.255'):
                value = 1
                info = 'Dispositivi HSPA attivi.'
                raise sysmonitorexception.WARNHSPA
        
        elif (type == 'WWAN'):
          if (system().lower().startswith('win')):
            guid = device.find('GUID').text
            dev_info = self.getDevInfo(guid)
            if (dev_info != None):
              dev_type = dev_info['type']
              if (dev_type == 0 or dev_type == 17):
                status = int(device.find('Status').text)
                if (status == 7 and value != 1):
                  value = 0
                  info = 'Dispositivi HSPA non attivi.'
                elif (status == 2):
                  value = 1
                  raise sysmonitorexception.WARNHSPA
                
          elif (system().lower().startswith('lin')):
            value = 1
            info = 'Dispositivi HSPA attivi.'
            raise sysmonitorexception.WARNHSPA
    
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_hosts(self, up = 2048, down = 2048, ispid = 'tlc003', arping = 1, res = RES_HOSTS):
    try:
      
      value = None
        
      self.getIp()
      ip = self._system[RES_IP][VALUE]
      self._getDev(ip)
      dev = self._system[RES_DEV][VALUE]
      self._get_mac(ip)
      mac = self._system[RES_MAC][VALUE]
      self._get_mask(ip)
      mask = self._system[RES_MASK][VALUE]
    
      logger.info("Check Hosts su interfaccia %s con MAC %s e NET %s/%d" % (dev, mac, ip, mask))
    
      # Controllo se ho un indirizzo pubblico, in quel caso ritorno 1
      if bool(re.search('^10\.|^172\.(1[6-9]|2[0-9]|3[01])\.|^192\.168\.', ip)):
        
        hosts = checkhost.countHosts(ip, mask, up, down, ispid, th_host, arping, mac, dev)
        
        other = hosts - th_host
        if (other < 0):
          other = 0
         
        value = other
        info = 'Trovati %d host in rete che eccedono la soglia.' % other
        logger.info(info)
        
        if (0 < hosts <= th_host):
          info = 'Non ci sono host in rete che eccedono la soglia.'
        elif hosts > th_host:
          #logger.error('Presenza di altri %s host in rete.' % hosts)
          raise sysmonitorexception.TOOHOST
        elif (hosts <= 0):
          if arping != 1:
            raise sysmonitorexception.BADHOST
          else:
            logger.warning('Passaggio a PING per controllo host in rete')
            return self._check_hosts(up, down, ispid, 0)
              
      else:
        hosts = 1
        value = (hosts - th_host)
        info = 'La scheda di rete in uso ha un IP pubblico. Non controllo il numero degli altri host in rete.'
        
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_traffic(self, sec = 2, res = RES_TRAFFIC):
    
    try:
      
      value = 'unknown'
      
      self.getIp()
      ip = self._system[RES_IP][VALUE]
      self._getDev(ip)
      dev = self._system[RES_DEV][VALUE]
      
      buff = 8 * 1024 * 1024
      pcapper = Pcapper(dev, buff, 150)
      start_time = time.time()
      pcapper.start()
      pcapper.sniff(Contabyte(ip, '0.0.0.0'))
      #logger.info("Checking Traffic for %d seconds...." % sec)
      pcapper.stop_sniff(2.2)
      stats = pcapper.get_stats()
      total_time = (time.time() - start_time) * 1000
      logger.info('Checked Traffic for %s ms' % total_time)
      pcapper.stop()
      pcapper.join()
      
      UP_kbps = stats.byte_up_all * 8 / total_time
      DOWN_kbps = stats.byte_down_all * 8 / total_time
      
      value = (DOWN_kbps, UP_kbps)
      info = "%.1f kbps in download e %.1f kbps in upload di traffico globale attuale sull'interfaccia di rete in uso." % (DOWN_kbps, UP_kbps)
      
#      if (int(UP_kbps) < 20 and int(DOWN_kbps) < 200):
#        value = 'LOW'
#      elif (int(UP_kbps) < 180 and int(DOWN_kbps) < 1800):
#        value = 'MEDIUM'
#      else:
#        value = 'HIGH'
#      
#      if (value != 'LOW'):
#        raise Exception(check_info)
      
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _get_NetIF(self, from_profiler = True):
  
    global NETIF_TIME, NETIF_1, NETIF_2
  
    age = 4 #seconds
    now = time.time()
    
    if ( NETIF_TIME == None ):
      NETIF_TIME = now
    
    if ( (now-NETIF_TIME)>age or (NETIF_1 == None) or (NETIF_2 == None) ):
      NETIF_TIME = now
      
      if from_profiler:
        profiler = LocalProfilerFactory.getProfiler()
        NETIF_1 = profiler.profile(set(['rete']))
      else:  
        NETIF_2 = {}
        for ifName in netifaces.interfaces():
          #logger.debug((ifName,netifaces.ifaddresses(ifName)))
          mac = [i.setdefault('addr', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_LINK, [{'addr':''}])]
          ip = [i.setdefault('addr', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'addr':''}])]
          mask = [i.setdefault('netmask', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'netmask':''}])]
          if mask[0] == '0.0.0.0':
            mask = [i.setdefault('broadcast', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'broadcast':''}])]
          NETIF_2[ifName] = {'mac':mac, 'ip':ip, 'mask':mask}
        #logger.debug('Network Interfaces:\n %s' %NETIF_2)
  
    if from_profiler:
      return NETIF_1
    else:
      return NETIF_2
  
  
  def getDevInfo(self, dev = None):
    
    dev_info = None
    
    if dev == None:
      dev = self._get_ActiveIp()
  
    dev_info = pktman.getdev(dev)
    if (dev_info['err_flag'] != 0):
      dev_info = None
      
    return dev_info
  
  
  def _get_mac(self, ip = None , res = RES_MAC):
    
    try:
      
      value = None
      
      if ip == None:
        ip = self._get_ActiveIp()
      
      netIF = self._get_NetIF(False)
      
      for interface in netIF:
        if (netIF[interface]['ip'][0] == ip):
          #logger.debug('| Ip: %s | Mac: %s |' % (ip,netIF[interface]['mac'][0]))
          value = netIF[interface]['mac'][0]
          if (value != None):
            value = value.upper()
          info = "Mac address dell'interfaccia di rete: %s" % value
      
      if (value == None):
        info = "Impossibile recuperare il valore del mac address dell'IP %s" % ip
        logger.error(info)
        raise sysmonitorexception.BADMAC
      
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def getIp(self, res = RES_IP):
    
    try:
      
      value = None
      netIF = self._get_NetIF(False)
      activeIp = self._get_ActiveIp()
    
      for interface in netIF:
        if (netIF[interface]['ip'][0] == activeIp):
          #logger.debug('| Active Ip: %s | Find Ip: %s |' % (activeIp,netIF[interface]['ip'][0]))
          value = activeIp
          info = "IPv4 dell'interfaccia di rete: %s" % value
    
      if (value == None):
        raise sysmonitorexception.UNKIP
      
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _get_mask(self, ip = None, res = RES_MASK):
    
    try:
      
      if ip == None:
        ip = self._get_ActiveIp()
    
      value = 0
      dotMask = None
    
      netIF = self._get_NetIF(False)
    
      for interface in netIF:
        if (netIF[interface]['ip'][0] == ip):
          #logger.debug('| Ip: %s | Mask: %s |' % (ip,netIF[interface]['mask'][0]))
          dotMask = netIF[interface]['mask'][0]
          #value = dotMask
          value = self._mask_conversion(dotMask)
    
      if (value <= 0):
        value = 32
        logger.error('Maschera forzata a 32. Impossibile recuperare il valore della maschera dell\'IP %s' % ip)
        #raise sysmonitorexception.BADMASK
      
      info = "Il valore della maschera di rete relativa all'IP %s e' %s [cidr %s]" % (ip, dotMask, value)
      status = True
      
    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def _check_ip_syntax(self, ip):
  
    try:
      socket.inet_aton(ip)
      parts = ip.split('.')
      if len(parts) != 4:
        return False
    except Exception:
      return False
  
    return True


  def _convertDecToBin(self, dec):
    i = 0
    bin = range(0, 4)
    for x in range(0, 4):
      bin[x] = range(0, 8)
  
    for i in range(0, 4):
      j = 7
      while j >= 0:
  
        bin[i][j] = (dec[i] & 1) + 0
        dec[i] /= 2
        j = j - 1
    return bin
  
  
  def _mask_conversion(self, dotMask):
    nip = str(dotMask).split(".")
    if(len(nip) == 4):
      i = 0
      bini = range(0, len(nip))
      while i < len(nip):
        bini[i] = int(nip[i])
        i += 1
      bins = self._convertDecToBin(bini)
      lastChar = 1
      maskcidr = 0
      i = 0
      while i < 4:
        j = 0
        while j < 8:
          if (bins[i][j] == 1):
            if (lastChar == 0):
              return 0
            maskcidr = maskcidr + 1
          lastChar = bins[i][j]
          j = j + 1
        i = i + 1
    else:
      return 0
    return maskcidr


  def _get_ActiveIp(self, host = 'speedtest.agcom244.fub.it', port = 443):
    
    #logger.debug('Determinazione dell\'IP attivo verso Internet')
    try:
      s = socket.socket(socket.AF_INET)
      s.connect((host, port))
      value = s.getsockname()[0]
    except socket.gaierror:
      raise sysmonitorexception.WARNLINK
    
    if not self._check_ip_syntax(value):
      raise sysmonitorexception.UNKIP
    
    return value



  
  

  
  
  def _getDev(self, ip = None, res = RES_DEV):
  
    try:
      
      value = None
      
      if ip == None:
        ip = self._get_ActiveIp()
    
      netIF = self._get_NetIF(False)
    
      for interface in netIF:
        if (netIF[interface]['ip'][0] == ip):
          #logger.debug('| Ip: %s | Find on Dev: %s |' % (ip,interface))
          value = interface
          info = "Interfaccia di rete: %s" % value
    
      if (value == None):
        info = 'Impossibile recuperare il nome del Device associato all\'IP %s' % ip
        logger.error(info)
        raise sysmonitorexception.UNKDEV
      
      status = True

    except Exception as e:
      
      info = e
      status = False
      #raise e
      
    finally:
      
      self._system[res][STATUS] = status
      self._system[res][VALUE] = value
      self._system[res][INFO] = info
      self._system[res][TIME] = time.time()
  
  
  def checkres(self, res, *args):
    
    self._checks[res](*args)
    
    return self._system[res]
  
  
  def checkall(self):
    
    for check in self._checks:
      result = self.checkres(check)
      logger.debug("--------[ %s ]--------" % check)
      for key, val in result.items(): 
        logger.info("| %s\t: %s" % (key, val))
      logger.debug("--------[ %s ]--------" % check)
      
    
#    system_profile = {}
#  
#    if (len(check_set) > 0):
#      checks = (check_set & set(available_check.keys()))
#  
#      unavailable_check = check_set - set(available_check.keys())
#      if (unavailable_check):
#        for res in list(unavailable_check):
#          system_profile[res] = {}
#          system_profile[res]['status'] = None
#          system_profile[res]['value'] = None
#          system_profile[res]['info'] = 'Risorsa non disponibile'
#  
#    else:
#      checks = set(available_check.keys())
#  
#    #logger.debug('Check Order: %s' % sorted(available_check, key = lambda check: available_check[check]['prio']))
#    for check in sorted(available_check, key = lambda check: available_check[check]['prio']):
#      if check in checks:
#  
#        try:
#          info = None
#          status = None
#          info = available_check[check]['meth']()
#          if (info != None):
#            status = True
#        except Exception as e:
#          # errorcode = errors.geterrorcode(e)
#          # logger.error('Errore [%d]: %s' % (errorcode, e))
#          info = e
#          status = False
#  
#        system_profile[check] = {}
#        system_profile[check]['status'] = status
#        system_profile[check]['value'] = None
#        system_profile[check]['info'] = str(info)
#        #logger.info('%s: %s' % (check, system_profile[check]))
#        #logger.debug(CHECK_VALUES)
#  
#    return system_profile  
  
  
  
  
if __name__ == "__main__":
  monitor = sysMonitor()
  #monitor.interfaces()
  
  monitor.checkall()
  
#  result = monitor.checkres(RES_IP)
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  result = monitor.checkres(RES_DEV, "172.16.181.129")
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  result = monitor.checkres(RES_MAC, "172.16.181.129")
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  result = monitor.checkres(RES_MASK, "172.16.181.129")
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  result = monitor.checkres(RES_ETH)
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  result = monitor.checkres(RES_WIFI)
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  result = monitor.checkres(RES_HSPA)
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  
#  #for i in range(8):
#  result = monitor.checkres(RES_RAM)
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
#  #time.sleep(0.2)
#  
#  result = monitor.checkres(RES_HOSTS)
#  for key, val in result.items(): 
#    logger.info("| %s\t: %s" % (key, val))
#  logger.info("--------")
  
  