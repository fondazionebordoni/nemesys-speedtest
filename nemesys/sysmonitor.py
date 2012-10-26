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

from SysProf import LocalProfilerFactory
from SysProf.NemesysException import LocalProfilerException, RisorsaException, FactoryException
from logger import logging
from errorcoder import Errorcoder
from xml.etree import ElementTree as ET
from contabyte import Contabyte
from platform import system
from pcapper import Pcapper

import checkhost
import pktman
import netifaces
import paths
import socket
import sysmonitorexception
import re
import time

import xmltodict

if (system().lower().startswith('win')):
  from SysProf.windows import profiler
elif (system().lower().startswith('lin')):
  from SysProf.linux import profiler
elif (system().lower().startswith('dar')):
  from SysProf.darwin import profiler


STRICT_CHECK = True

CHECK_ALL = "ALL"
CHECK_MEDIUM = "MEDIUM"

RES_CPU = 'CPU'
RES_RAM = 'RAM'
RES_WIFI = 'Wireless'
RES_HSPA = 'Mobile'
RES_ETH = 'Ethernet'
RES_HOSTS = 'Hosts'
RES_MAC = 'MAC'
RES_IP = 'IP'
RES_MASK = 'MASK'
RES_OS = 'OS'
RES_TRAFFIC = 'Traffic'
RES_DEV = 'Device'

CHECK_VALUES = {}

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

def interfaces():
  data = _get_NetIF(1)
  for device in data.findall('rete/NetworkDevice'):
    dev = xmltodict.parse(ET.tostring(device))
    dev = dev['NetworkDevice']
    logger.info("============================================")
    for key, val in dev.items(): 
      logger.info("| %s : %s" % (key, val))
  logger.info("============================================")

def _get_values(tagrisorsa, xmlresult, tag = tag_results):
  #' Estrae informazioni dal SystemProfiler '#
  values = {}
  try:
    for subelement in xmlresult.find(tagrisorsa):
      values.update({subelement.tag:subelement.text})
  except Exception as e:
    logger.warning('Errore durante il recupero dello stato del computer. %s' % e)
    raise Exception('Errore durante il recupero dello stato del computer.')

  return values


def _get_status(res):

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

  return _get_values(res, data)


def _get_string_tag(tag, value, res):

  values = _get_status(res)

  try:
    value = str(values[tag])
  except Exception as e:
    logger.error('Errore in lettura del paramentro "%s" di SystemProfiler: %s' % (tag, e))
    if STRICT_CHECK:
      raise sysmonitorexception.FAILREADPARAM

  if value == 'None':
    return None

  return value


def _get_float_tag(tag, value, res):

  values = _get_status(res)

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


def _check_cpu(res = RES_CPU):

  global CHECK_VALUES
  
  num_check = 0
  tot_value = 0
  
  CHECK_VALUES[res] = None
  
  for check in range(4):
    value = _get_float_tag(tag_cpu.split('.', 1)[1], th_cpu - 1, tag_cpu.split('.', 1)[0])
    if value != None:  
      tot_value += value 
      num_check += 1
      if value < th_cpu:
        break
  
  value = tot_value / float(num_check)  
  CHECK_VALUES[res] = value
  if value < 0 or value > 100:
    raise sysmonitorexception.BADCPU
  if value > th_cpu:
    raise sysmonitorexception.WARNCPU

  check_info = 'Utilizzato il %s%% del processore' % value

  return check_info


def _check_mem(res = RES_RAM):

  global CHECK_VALUES

  for check in range(3):
    CHECK_VALUES[res] = None
    avMem = _get_float_tag(tag_avMem.split('.')[1], th_avMem + 1, tag_avMem.split('.')[0])
    if avMem != None:
      CHECK_VALUES[res] = avMem
      if avMem < 0:
        raise sysmonitorexception.BADMEM
      if avMem < th_avMem:
        raise sysmonitorexception.LOWMEM
      break
    else:
      avmem = 'unknow'
      CHECK_VALUES[res] = avMem


  for check in range(3):
    CHECK_VALUES[res] = None
    memLoad = _get_float_tag(tag_memLoad.split('.')[1], th_memLoad - 1, tag_memLoad.split('.')[0])
    if memLoad != None:
      CHECK_VALUES[res] = memLoad
      if memLoad < 0 or memLoad > 100:
        raise sysmonitorexception.INVALIDMEM
      if memLoad > th_memLoad:
        raise sysmonitorexception.OVERMEM
      break
    else:
      memLoad = 'unknow'
      CHECK_VALUES[res] = memLoad


  check_info = 'Utilizzato il %s%% di %d GB della memoria' % (memLoad, avMem / (1000*1000*1000))

  return check_info

def _check_ethernet(res = RES_ETH):

  global CHECK_VALUES

  CHECK_VALUES[res] = -1

  check_info = 'Dispositivi ethernet non presenti.'
  data = _get_NetIF(1)
  
  for device in data.findall('rete/NetworkDevice'):
    #logger.debug(ET.tostring(device))
    type = device.find('Type').text
    if (type == 'Ethernet 802.3'):
      
      if (system().lower().startswith('win')):
        guid = device.find('GUID').text
        dev_info = getDevInfo(guid)
        if (dev_info != None):
          dev_type = dev_info['type']
          if (dev_type == 0 or dev_type == 14):
            status = int(device.find('Status').text)
            if (status == 7 and CHECK_VALUES[res] != 1):
              CHECK_VALUES[res] = 0
              check_info = 'Dispositivi ethernet non attivi.'
              raise sysmonitorexception.WARNETH
            elif (status == 2):
              CHECK_VALUES[res] = 1
              check_info = 'Dispositivi ethernet attivi.'
              
      elif (system().lower().startswith('lin')):
        status = device.find('Status').text
        active = device.find('isActive').text
        if (status == 'Disabled' and CHECK_VALUES[res] != 1):  
          CHECK_VALUES[res] = 0
          check_info = 'Dispositivi ethernet non attivi.'
          raise sysmonitorexception.WARNETH
        elif (status == 'Enabled' and active == 'True'):
          CHECK_VALUES[res] = 1
          check_info = 'Dispositivi ethernet attivi.'

      elif (system().lower().startswith('dar')):  
        status = device.find('Status').text
        active = device.find('isActive').text
        if (CHECK_VALUES[res] != 1):  
          CHECK_VALUES[res] = 0
          check_info = 'Dispositivi ethernet non attivi.'
          raise sysmonitorexception.WARNETH
        elif (status == 'Enabled' and active == 'True'):
          CHECK_VALUES[res] = 1
          check_info = 'Dispositivi ethernet attivi.'
            
  if (CHECK_VALUES[res] == -1):
    raise sysmonitorexception.WARNETH
            
  return check_info
  
def _check_wireless(res = RES_WIFI):

  global CHECK_VALUES

  CHECK_VALUES[res] = -1

  check_info = 'Dispositivi wireless non presenti.'
  data = _get_NetIF(1)
  
  for device in data.findall('rete/NetworkDevice'):
    #logger.debug(ET.tostring(device))
    type = device.find('Type').text
    if (type == 'Wireless'):
      
      if (system().lower().startswith('win')):
        guid = device.find('GUID').text
        dev_info = getDevInfo(guid)
        if (dev_info != None):
          dev_type = dev_info['type']
          if (dev_type == 0 or dev_type == 25):
            status = int(device.find('Status').text)
            if (status == 7 and CHECK_VALUES[res] != 1):
              CHECK_VALUES[res] = 0
              check_info = 'Dispositivi wireless non attivi.'
            elif (status == 2):
              CHECK_VALUES[res] = 1
              check_info = 'Dispositivi wireless attivi.'
              raise sysmonitorexception.WARNWLAN
            
      elif (system().lower().startswith('lin')):  
        status = device.find('Status').text
        if (status == 'Disabled' and CHECK_VALUES[res] != 1):  
          CHECK_VALUES[res] = 0
          check_info = 'Dispositivi wireless non attivi.'
        elif (status == 'Enabled'):
          CHECK_VALUES[res] = 1
          check_info = 'Dispositivi wireless attivi.'
          raise sysmonitorexception.WARNWLAN

      elif (system().lower().startswith('dar')):  
        status = device.find('Status').text
        active = device.find('isActive').text
        if (CHECK_VALUES[res] != 1):  
          CHECK_VALUES[res] = 0
          check_info = 'Dispositivi wireless non attivi.'
        elif (status == 'Enabled' and active == 'True'):
          CHECK_VALUES[res] = 1
          check_info = 'Dispositivi wireless attivi.'
          raise sysmonitorexception.WARNWLAN
                    
  return check_info

def _check_hspa(res = RES_HSPA):

  global CHECK_VALUES

  CHECK_VALUES[res] = -1
  check_info = 'Dispositivi HSPA non presenti.'
  
  if (system().lower().startswith('lin')):
    check_info = 'Dispositivi HSPA non presenti o non attivi.'
  
  data = _get_NetIF(1)
  
  for device in data.findall('rete/NetworkDevice'):
    #logger.debug(ET.tostring(device))
    type = device.find('Type').text
    
    if (type == 'External Modem'):
      dev_id = device.find('ID').text
      if (re.search('USB',dev_id)):
        CHECK_VALUES[res] = 0
        check_info = 'Dispositivi HSPA non attivi.'
        dev_info = getDevInfo()
        if (dev_info != None):
          dev_type = dev_info['type']
          dev_mask = dev_info['mask']
          if (dev_type == 3 or dev_type == 17 or dev_mask == '255.255.255.255'):
            CHECK_VALUES[res] = 1
            check_info = 'Dispositivi HSPA attivi.'
            raise sysmonitorexception.WARNHSPA
    
    elif (type == 'WWAN'):
      if (system().lower().startswith('win')):
        guid = device.find('GUID').text
        dev_info = getDevInfo(guid)
        if (dev_info != None):
          dev_type = dev_info['type']
          if (dev_type == 0 or dev_type == 17):
            status = int(device.find('Status').text)
            if (status == 7 and CHECK_VALUES[res] != 1):
              CHECK_VALUES[res] = 0
              check_info = 'Dispositivi HSPA non attivi.'
            elif (status == 2):
              CHECK_VALUES[res] = 1
              raise sysmonitorexception.WARNHSPA
            
      elif (system().lower().startswith('lin')):
        CHECK_VALUES[res] = 1
        check_info = 'Dispositivi HSPA attivi.'
        raise sysmonitorexception.WARNHSPA
      
      elif (system().lower().startswith('dar')):  
        status = device.find('Status').text
        active = device.find('isActive').text
        if (CHECK_VALUES[res] != 1):  
          CHECK_VALUES[res] = 0
          check_info = 'Dispositivi HSPA non attivi.'
        elif (status == 'Enabled' and active == 'True'):
          CHECK_VALUES[res] = 1
          check_info = 'Dispositivi HSPA attivi.'
          raise sysmonitorexception.WARNHSPA

  return check_info
  
def _check_hosts(up = 2048, down = 2048, ispid = 'tlc003', arping = 1, res = RES_HOSTS):

  global CHECK_VALUES

  CHECK_VALUES[res] = None
  
  #netIF = _get_NetIF()
  # for key in netIF:
    # logger.debug('%s : %s' % (key,netIF[key]))
    
  ip = getIp()
  dev = getDev(ip)
  mac = _get_mac(ip)
  mask = _get_mask(ip)

  logger.info("Check Hosts su interfaccia %s con MAC %s e NET %s/%d" % (dev, mac, ip, mask))

  # Controllo se ho un indirizzo pubblico, in quel caso ritorno 1
  if bool(re.search('^10\.|^172\.(1[6-9]|2[0-9]|3[01])\.|^192\.168\.', ip)):

    value = checkhost.countHosts(ip, mask, up, down, ispid, th_host, arping, mac, dev)
    
    other = value - th_host
    if (other < 0):
      other = 0
    
    logger.info('Trovati %d host in rete che eccedono la soglia.' % other)

    CHECK_VALUES[res] = other

    if value < 0:
      raise sysmonitorexception.BADHOST
    elif (value == 0):
      if arping == 1:
        logger.warning('Passaggio a PING per controllo host in rete')
        return _check_hosts(up, down, ispid, 0)
      else:
        raise sysmonitorexception.BADHOST
    elif value > th_host:
      #logger.error('Presenza di altri %s host in rete.' % value)
      raise sysmonitorexception.TOOHOST

    check_info = ('Trovati %d host in rete che eccedono la soglia.' % other)

  else:
    value = 1
    CHECK_VALUES[res] = (value - th_host)
    logger.info('La scheda di rete in uso ha un IP pubblico. Non controllo il numero degli altri host in rete.')
    check_info = 'La scheda di rete in uso ha un IP pubblico. Non controllo il numero degli altri host in rete.'

  return check_info


def _check_traffic(sec = 2, res = RES_TRAFFIC):

  global CHECK_VALUES

  CHECK_VALUES[res] = None

  traffic = None
  ip = getIp()
  dev = getDev(ip)
  buff = 8 * 1024 * 1024

  try:
    pcapper = Pcapper(dev, buff, 150)
    start_time = time.time()
    pcapper.start()
    pcapper.sniff(Contabyte(ip, '0.0.0.0'))
    #logger.info("Checking Traffic for %d seconds...." % sec)
    time.sleep(sec)
    pcapper.stop_sniff()
    stats = pcapper.get_stats()
    total_time = int((time.time() - start_time) * 1000)
    logger.info('Checked Traffic for %s ms' % total_time)
    pcapper.stop()
    pcapper.join()
    
    UP_kbps = stats.byte_up_all * 8 / total_time
    DOWN_kbps = stats.byte_down_all * 8 / total_time
    
    if (int(UP_kbps) < 20 and int(DOWN_kbps) < 200):
      traffic = 'LOW'
    elif (int(UP_kbps) < 180 and int(DOWN_kbps) < 1800):
      traffic = 'MEDIUM'
    else:
      traffic = 'HIGH'
    
    CHECK_VALUES[res] = traffic
    
    check_info = "%.1f kbps in download e %.1f kbps in upload di traffico globale attuale sull'interfaccia di rete in uso." % (DOWN_kbps, UP_kbps)
     
  except Exception as e:
    CHECK_VALUES[res] = 'unknown'
    raise e
 
  if (CHECK_VALUES[res] != 'LOW'):
    raise Exception(check_info)
  
  return check_info


def _check_ip_syntax(ip):

  try:
    socket.inet_aton(ip)
    parts = ip.split('.')
    if len(parts) != 4:
      return False
  except Exception:
    return False

  return True


def _convertDecToBin(dec):
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


def _mask_conversion(dotMask):
  nip = str(dotMask).split(".")
  if(len(nip) == 4):
    i = 0
    bini = range(0, len(nip))
    while i < len(nip):
      bini[i] = int(nip[i])
      i += 1
    bins = _convertDecToBin(bini)
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


def _get_NetIF(type = 0):

  global NETIF_TIME, NETIF_1, NETIF_2

  age = 4 #seconds
  now = time.time()
  
  if ( NETIF_TIME == None ):
    NETIF_TIME = now
  
  if ( (now-NETIF_TIME)>age or (NETIF_1 == None) or (NETIF_2 == None) ):
    NETIF_TIME = now
    
    if (type != 0):
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

  if (type != 0):
    return NETIF_1
  else:
    return NETIF_2


def _get_ActiveIp(host = 'speedtest.agcom244.fub.it', port = 443):

  #logger.debug('Determinazione dell\'IP attivo verso Internet')
  try:
    s = socket.socket(socket.AF_INET)
    s.connect((host, port))
    value = s.getsockname()[0]
  except socket.gaierror:
    raise sysmonitorexception.WARNLINK
    
  if not _check_ip_syntax(value):
    raise sysmonitorexception.UNKIP

  return value


def _get_mac(ip = None , res = RES_MAC):

  global CHECK_VALUES

  CHECK_VALUES[res] = None

  if ip == None:
    ip = _get_ActiveIp()

  mac = None
  netIF = _get_NetIF()

  for interface in netIF:
    if (netIF[interface]['ip'][0] == ip):
      #logger.debug('| Ip: %s | Mac: %s |' % (ip,netIF[interface]['mac'][0]))
      mac = netIF[interface]['mac'][0]

  if (mac == None):
    logger.error('Impossibile recuperare il valore del mac address dell\'IP %s' % ip)
    raise sysmonitorexception.BADMAC

  CHECK_VALUES[res] = mac

  return mac


def getIp(res = RES_IP):

  global CHECK_VALUES

  CHECK_VALUES[res] = None

  ip = None
  netIF = _get_NetIF()
  activeIp = _get_ActiveIp()

  for interface in netIF:
    if (netIF[interface]['ip'][0] == activeIp):
      #logger.debug('| Active Ip: %s | Find Ip: %s |' % (activeIp,netIF[interface]['ip'][0]))
      ip = activeIp

  if (ip == None):
    raise sysmonitorexception.UNKIP

  CHECK_VALUES[res] = ip

  return ip


def _get_mask(ip = None, res = RES_MASK):

  global CHECK_VALUES

  CHECK_VALUES[res] = None

  if ip == None:
    ip = _get_ActiveIp()

  cidrMask = 0
  dotMask = None

  netIF = _get_NetIF()

  for interface in netIF:
    if (netIF[interface]['ip'][0] == ip):
      #logger.debug('| Ip: %s | Mask: %s |' % (ip,netIF[interface]['mask'][0]))
      dotMask = netIF[interface]['mask'][0]
      CHECK_VALUES[res] = dotMask
      cidrMask = _mask_conversion(dotMask)

  if (cidrMask <= 0):
    cidrMask = 32
    logger.error('Maschera forzata a 32. Impossibile recuperare il valore della maschera dell\'IP %s' % ip)
    #raise sysmonitorexception.BADMASK

  return cidrMask


def getDev(ip = None, res = RES_DEV):

  global CHECK_VALUES

  CHECK_VALUES[res] = None

  dev = None

  if ip == None:
    ip = _get_ActiveIp()

  netIF = _get_NetIF()

  for interface in netIF:
    if (netIF[interface]['ip'][0] == ip):
      #logger.debug('| Ip: %s | Find on Dev: %s |' % (ip,interface))
      dev = interface

  if (dev == None):
    logger.error('Impossibile recuperare il nome del Device associato all\'IP %s' % ip)
    raise sysmonitorexception.UNKDEV

  CHECK_VALUES[res] = dev

  return dev


def getDevInfo(dev = None):
  
  dev_info = None
  
  if dev == None:
    dev = _get_ActiveIp()

  dev_info = pktman.getdev(dev)
  if (dev_info['err_flag'] != 0):
    dev_info = None

  return dev_info


def _get_os(res = RES_OS):

  global CHECK_VALUES
  
  CHECK_VALUES[res] = None
  
  query = {tag_sys:''}
  os = _get_string_tag(tag_sys.split('.', 1)[1], 1, tag_sys.split('.', 1)[0])
  
  CHECK_VALUES[res] = os
  
  check_info = ("Sistema Operativo %s" % os)
  
  return check_info


def _get_Sys():

  d = {tag_sys:'', tag_cores:'', tag_proc:''}
  r = []

  for keys in d:
    r.append(_get_string_tag(keys.split('.', 1)[1], 1, keys.split('.', 1)[0]))

  return r


def checkset(check_set = set()):

  global CHECK_VALUES
  CHECK_VALUES = {}

  available_check = \
  { \
   RES_OS:{'prio':1, 'meth':_get_os}, \
   RES_CPU:{'prio':2, 'meth':_check_cpu}, \
   RES_RAM:{'prio':3, 'meth':_check_mem}, \
   RES_ETH:{'prio':4, 'meth':_check_ethernet}, \
   RES_WIFI:{'prio':5, 'meth':_check_wireless}, \
   RES_HSPA:{'prio':6, 'meth':_check_hspa}, \
   RES_HOSTS:{'prio':7, 'meth':_check_hosts}, \
   RES_TRAFFIC:{'prio':8, 'meth':_check_traffic}, \
   RES_MAC:{'prio':9, 'meth':_get_mac}, \
   RES_IP:{'prio':10, 'meth':getIp}, \
   RES_MASK:{'prio':11, 'meth':_get_mask}, \
   RES_DEV:{'prio':12, 'meth':getDev}, \
   #'sys':{'prio':13,'meth':_get_Sys} \
   }

  system_profile = {}

  if (len(check_set) > 0):
    checks = (check_set & set(available_check.keys()))

    unavailable_check = check_set - set(available_check.keys())
    if (unavailable_check):
      for res in list(unavailable_check):
        system_profile[res] = {}
        system_profile[res]['status'] = None
        system_profile[res]['value'] = None
        system_profile[res]['info'] = 'Risorsa non disponibile'

  else:
    checks = set(available_check.keys())

  #logger.debug('Check Order: %s' % sorted(available_check, key = lambda check: available_check[check]['prio']))
  for check in sorted(available_check, key = lambda check: available_check[check]['prio']):
    if check in checks:

      try:
        info = None
        status = None
        info = available_check[check]['meth']()
        if (info != None):
          status = True
      except Exception as e:
        # errorcode = errors.geterrorcode(e)
        # logger.error('Errore [%d]: %s' % (errorcode, e))
        info = e
        status = False

      system_profile[check] = {}
      system_profile[check]['status'] = status
      system_profile[check]['value'] = CHECK_VALUES[check]
      system_profile[check]['info'] = str(info)
      #logger.info('%s: %s' % (check, system_profile[check]))
      #logger.debug(CHECK_VALUES)

  return system_profile


def fastcheck():

  _check_cpu()
  _check_mem()

  return True


def mediumcheck():

  fastcheck()
  _check_wireless()

  return True


def checkall(up, down, ispid, arping = 1):

  mediumcheck()
  _check_hosts(up, down, ispid, arping)

  return True




if __name__ == '__main__':

  try:
    print '\nCheck All'
    print 'Test sysmonitor checkall: %s' % checkall(1000, 2000, 'fst001')
  except Exception as e:
    errorcode = errors.geterrorcode(e)
    print 'Errore [%d]: %s' % (errorcode, e)

  print '\nCheck Set All'
  print 'Test sysmonitor checkset: %s' % checkset()

  print '\nCheck Set Partial'
  print 'Test sysmonitor checkset: %s' % checkset(set(['CPU', 'RAM', 'Wifi', 'MAC', 'IP', 'pippo', 8]))

