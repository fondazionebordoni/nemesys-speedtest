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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from collections import OrderedDict

from SysProf.NemesysException import LocalProfilerException, RisorsaException, FactoryException
from SysProf import LocalProfilerFactory
from xml.etree import ElementTree as ET
from platform import system
from logger import logging

import sysmonitorexception
import checkhost
import netifaces
import xmltodict
import netstat
import socket
import time
import re


CHECK_ALL = "ALL"
CHECK_MEDIUM = "MEDIUM"

RES_OS = 'OS'
RES_CPU = 'CPU'
RES_RAM = 'RAM'
RES_ETH = 'Ethernet'
RES_WIFI = 'Wireless'
#RES_HSPA = 'Mobile'
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

tag_results = 'SystemProfilerResults'
#tag_threshold = 'SystemProfilerThreshold'
tag_avMem = 'RAM.totalPhysicalMemory'
tag_memLoad = 'RAM.RAMUsage'
tag_wireless = 'wireless.ActiveWLAN'
tag_ip = 'ipAddr' #to check
tag_os = 'sistemaOperativo.OperatingSystem'
tag_cpu = 'CPU.cpuLoad'
#tag_mac = 'rete.NetworkDevice/MACAddress'
#tag_activeNic = 'rete.NetworkDevice/isActive'
#tag_cores = 'CPU.cores'
#tag_proc = 'CPU.processor'
#tag_hosts = 'hostNumber'


#' SOGLIE '#
th_host = 1                     # Massima quantità di host in rete
th_avMem = 134217728    # Minima memoria disponibile
th_memLoad = 95             # Massimo carico percentuale sulla memoria
th_cpu = 85                     # Massimo carico percentuale sulla CPU
#'--------'#


logger = logging.getLogger()


def interfaces():
    monitor = SysMonitor()
    devices = monitor._get_NetIF(True)
    for device in devices.findall('rete/NetworkDevice'):
        dev = xmltodict.parse(ET.tostring(device))
        dev = dev['NetworkDevice']
        logger.info("============================================")
        for key, val in dev.items(): 
            logger.info("| %s : %s" % (key, val))
    logger.info("============================================")


class SysMonitor():
    def __init__(self):
        
        self._strict_check = True
        
        self._system = OrderedDict \
        ([ \
        (RES_OS, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_CPU, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_RAM, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_ETH, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_WIFI, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
#        (RES_HSPA, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_DEV, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_MAC, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_IP, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_MASK, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_HOSTS, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])),\
        (RES_TRAFFIC, OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ])) \
        ])
        
        self._checks = OrderedDict \
        ([ \
        (RES_OS,self._get_os),\
        (RES_CPU,self._check_cpu),\
        (RES_RAM,self._check_mem),\
        (RES_ETH,self._check_ethernet),\
        (RES_WIFI,self._check_wireless),\
#        (RES_HSPA,self._check_hspa),\
        (RES_DEV,self._getDev),\
        (RES_MAC,self._get_mac),\
        (RES_IP,self._get_ip),\
        (RES_MASK,self._get_mask),\
        (RES_HOSTS,self._check_hosts),\
        (RES_TRAFFIC,self._check_traffic) \
        ])
        
        
        self._net_if = {'netifaces':None, 'profiler':None, 'time':None}
    
    

    def _clear(self):
        for res in self._system:
            self._system[res].update(OrderedDict([ (STATUS,False) , (VALUE,None) , (INFO,None) , (TIME,None) ]))
        #self._logger_dict(self._system)
    
    
    def _logger_dict(self, dictionary):
        logger.info("============================================")
        for key, val in dictionary.items(): 
            logger.info("----[ %s ]----" % key)
            for k, v in val.items():
                logger.info("\t%s = %s" % (k,v))
    
    
    def _store(self, res, status, value, info):
        self._system[res][STATUS] = status
        self._system[res][VALUE] = value
        self._system[res][INFO] = info
        self._system[res][TIME] = None #time.time()
        #self._logger_dict(self._system)
    
    
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
            if self._strict_check:
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
            if self._strict_check:
                raise sysmonitorexception.FAILREADPARAM
    
        return value
    
    
    def _get_os(self, res = RES_OS):
        
        value = 'unknown'
        try:
            
            value = self._get_string_tag(tag_os.split('.', 1)[1], 1, tag_os.split('.', 1)[0])
            info = ("Sistema Operativo %s" % value)
            status = True 
            
        except Exception as e:
            
            info = e
            status = False
            #raise e
            
        finally:
            
            self._store(res, status, value, info)
    
    
    def _check_cpu(self, res = RES_CPU):
        
        try:
            
            num_check = 0
            tot_value = 0
            
            value = None
            
            for _ in range(4):
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
            
            self._store(res, status, value, info)
    
    
    def _check_mem(self, res = RES_RAM):
        
        try:
            
            for _ in range(3):
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
                    avMem = 'unknown'
                    value = avMem
        
            for _ in range(3):
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
                    memLoad = 'unknown'
                    value = memLoad
        
            info = 'Utilizzato il %s%% di %d GB della memoria' % (memLoad, avMem / (1000*1000*1000))
            status = True
        
        except Exception as e:
            
            info = e
            status = False
            #raise e
            
        finally:
            
            self._store(res, status, value, info)
    
    
    def _check_ethernet(self, res = RES_ETH):
    
        try:
    
            value = -1
            num_active_eth = 0
            info = 'Dispositivi ethernet non presenti.'
            devices = self._get_NetIF(True)
            
            for device in devices.findall('rete/NetworkDevice'):
                #logger.debug(ET.tostring(device))
                dev_type = device.find('Type').text
                if (dev_type == 'Ethernet 802.3'):
                    
                    if (system().lower().startswith('win')):
                        guid = device.find('GUID').text
                        my_netstat = netstat.get_netstat(guid)
                        if (my_netstat.is_device_active()):
                                num_active_eth += 1
                        else:
                                logger.debug("Found inactive Ethernet device")

                    elif (system().lower().startswith('lin')):
                        status = device.find('Status').text
                        active = device.find('isActive').text
                        if (status == 'Disabled' and value != 1):    
                            logger.debug("Found inactive Ethernet device")
                        elif (status == 'Enabled' and active == 'True'):
                            num_active_eth += 1
                            
                    elif (system().lower().startswith('dar')):    
                        status = device.find('Status').text
                        active = device.find('isActive').text
                        if (status == 'Enabled' and active == 'True'):
                            num_active_eth += 1
                        else:    
                            logger.debug("Found inactive Ethernet device")

            if (num_active_eth > 0):
                info = 'Dispositivi ethernet attivi.'
                value = 1
                status = True
            else:
                info = 'Dispositivi ethernet non attivi.'
                value = 0
                raise sysmonitorexception.WARNETH
                                
        
        except Exception as e:
            
            info = e
            status = False
            
        finally:
            self._store(res, status, value, info)
    
    
    def _check_wireless(self, res = RES_WIFI):
    
        try:
            
            value = -1
            info = 'Dispositivi wireless non presenti.'
            devices = self._get_NetIF(True)
            
            for device in devices.findall('rete/NetworkDevice'):
                #logger.debug(ET.tostring(device))
                dev_type = device.find('Type').text
                if (dev_type == 'Wireless'):
                    
                    if (system().lower().startswith('win')):
#                         guid = device.find('GUID').text
#                        dev_info = self._getDevInfo(guid)
#                        if (dev_info != None):
#                             dev_type = dev_info['type']
#                             if (dev_type == type) or (dev_type == 'Unknown'):
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
                        
                    elif (system().lower().startswith('dar')):    
                        status = device.find('Status').text
                        active = device.find('isActive').text
                        if (status == 'Enabled' and active == 'True'):
                            value = 1
                            info = 'Dispositivi wireless attivi.'
                            raise sysmonitorexception.WARNWLAN
                        elif (value != 1):
                            value = 0
                            info = 'Dispositivi wireless non attivi.'
                                
            status = True
            
        except Exception as e:
            
            info = e
            status = False
            #raise e
            
        finally:
            
            self._store(res, status, value, info)
    
    
    def _check_hosts(self, up = 2048, down = 2048, ispid = 'tlc003', arping = 1, res = RES_HOSTS):
        try:
            
            value = None
            call_ping = False
            
            self._get_ip()
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
                        call_ping = True
                        status = False
                        return
                        
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
            
            self._store(res, status, value, info)
            
            if call_ping:
                self._check_hosts(up, down, ispid, 0)
    
    
    def _check_traffic(self, sec = 2, res = RES_TRAFFIC):
        
        try:

            value = 'unknown'

            self._get_ip()
            ip = self._system[RES_IP][VALUE]
            self._getDev(ip)
            dev = self._system[RES_DEV][VALUE]

            my_netstat = netstat.get_netstat(dev)

            logger.debug("getting stats from dev " + dev)

            start_rx_bytes = my_netstat.get_rx_bytes()
            start_tx_bytes = my_netstat.get_tx_bytes()
            logger.debug("start rx %d, start tx %d" % (start_rx_bytes,start_tx_bytes))
            start_time = time.time()
            time.sleep(sec)
            end_rx_bytes = my_netstat.get_rx_bytes()
            end_tx_bytes = my_netstat.get_tx_bytes()
            measure_time_millis = (time.time() - start_time) * 1000
            logger.debug("end rx %d, end tx %d" % (end_rx_bytes, end_tx_bytes))
            logger.debug("total time millis %d" % measure_time_millis)

            UP_kbps = (end_tx_bytes - start_tx_bytes) * 8 / measure_time_millis
            DOWN_kbps = (end_rx_bytes - start_rx_bytes) * 8 / measure_time_millis
            if ( (UP_kbps < 0) or (DOWN_kbps < 0)):
                    raise Exception("Ottenuto valore di traffico negativo, potrebbe dipendere dall'azzeramento dei contatori.")

            value = (DOWN_kbps, UP_kbps)
            info = "%.1f kbps in download e %.1f kbps in upload di traffico globale attuale sull'interfaccia di rete in uso." % (DOWN_kbps, UP_kbps)

            if (int(UP_kbps) < 20 and int(DOWN_kbps) < 200):
                value = 'LOW'
            elif (int(UP_kbps) < 180 and int(DOWN_kbps) < 1800):
                value = 'MEDIUM'
            else:
                value = 'HIGH'

            if (value != 'LOW'):
                raise Exception(info)

            status = True

        except Exception as e:

            info = e
            status = False
            #raise e

        finally:

            self._store(res, status, value, info)
    
    
    def _get_NetIF(self, from_profiler = True):
        
        age = 2
        old = self._net_if['time']
        now = time.time()
        
        if (old == None):
            old = now - 22
            
        if ((now-old)>age):
            
            self._net_if['time'] = now
            
            #if from_profiler:
            profiler = LocalProfilerFactory.getProfiler()
            self._net_if['profiler'] = profiler.profile(set(['rete']))
                
            #else:
            self._net_if['netifaces'] = {}
            for ifName in netifaces.interfaces():
                #logger.debug((ifName,netifaces.ifaddresses(ifName)))
                mac = [i.setdefault('addr', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_LINK, [{'addr':''}])]
                ip = [i.setdefault('addr', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'addr':''}])]
                mask = [i.setdefault('netmask', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'netmask':''}])]
                if mask[0] == '0.0.0.0':
                    mask = [i.setdefault('broadcast', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'broadcast':''}])]
                self._net_if['netifaces'][ifName] = {'mac':mac, 'ip':ip, 'mask':mask}
            #logger.debug('Network Interfaces:\n %s' % self._net_if['netifaces'])
            
        if from_profiler:
            return self._net_if['profiler']
        else:
            return self._net_if['netifaces']
    
    
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
            
            self._store(res, status, value, info)
    
    
#     def _getDevInfo(self, dev = None):
#         
#         if dev == None:
#             dev = self._get_ActiveIp()
#             
#         dev_info = pktman.getdev(dev)
#         if (dev_info['err_flag'] != 0):
#             dev_info = None
#         else:
#             if (dev_info['type'] == 0):
#                 dev_info['type'] = 'Unknown'
#             elif (dev_info['type'] == 14):
#                 dev_info['type'] = 'Ethernet 802.3'
#             elif (dev_info['type'] == 25):
#                 dev_info['type'] = 'Wireless'
#             elif (dev_info['type'] == 17):
#                 dev_info['type'] = 'WWAN'
#             elif (dev_info['type'] == 3) and (dev_info['ip'] != '127.0.0.1'):
#                 dev_info['type'] = 'External Modem'
#         
#             if (dev_info.get('descr', 'none') == 'none'):
#                 data = self._get_NetIF(True)
#                 for device in data.findall('rete/NetworkDevice'):
#                     if (device.find('Device').text == dev):
#                         dev_info['type'] = device.find('Type').text
#                         dev_info['descr'] = "%s (%s)" % (device.find('Name').text, device.find('Type').text)
#         
#         return dev_info
#     
    
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
                    break
            
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
            
            self._store(res, status, value, info)
    
    
    def _get_ip(self, res = RES_IP):
        
        try:
            
            value = None
            netIF = self._get_NetIF(False)
            activeIp = self._get_ActiveIp()
        
            for interface in netIF:
                if (netIF[interface]['ip'][0] == activeIp):
                    #logger.debug('| Active Ip: %s | Find Ip: %s |' % (activeIp,netIF[interface]['ip'][0]))
                    value = activeIp
                    info = "Indirizzo IPv4 dell'interfaccia di rete: %s" % value
        
            if (value == None):
                raise sysmonitorexception.UNKIP
            
            status = True
            
        except Exception as e:
            
            info = e
            status = False
            #raise e
            
        finally:
            
            self._store(res, status, value, info)
    
    
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
            
            self._store(res, status, value, info)
    
    
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
        bin_val = range(0, 4)
        for x in range(0, 4):
            bin_val[x] = range(0, 8)
    
        for i in range(0, 4):
            j = 7
            while j >= 0:
    
                bin_val[i][j] = (dec[i] & 1) + 0
                dec[i] /= 2
                j = j - 1
        return bin_val
    
    
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


def _checkipsyntax(ip):

    try:
        socket.inet_aton(ip)
        parts = ip.split('.')
        if len(parts) != 4:
            return False
    except Exception:
        return False

    return True

def getIp(host = 'finaluser.agcom244.fub.it', port = 443):
        '''
        restituisce indirizzo IP del computer
        '''
        s = socket.socket(socket.AF_INET)
        s.connect((host, port))
        value = s.getsockname()[0]
        
        if not _checkipsyntax(value):
            raise sysmonitorexception.UNKIP
        return value

def getDev(host = 'finaluser.agcom244.fub.it', port = 443, ip = None):
    '''
    restituisce scheda attiva (guid della scheda su Windows 
    '''
    if not ip:
        local_ip_address = getIp(host, port)
    else:
        local_ip_address = ip
            

    ''' Now get the associated device '''
    found = False
    for ifName in netifaces.interfaces():
            all_addresses = netifaces.ifaddresses(ifName)
            if netifaces.AF_INET in all_addresses:
                    addresses = all_addresses[netifaces.AF_INET]
                    for address in addresses:
                            if address['addr'] == local_ip_address:
                                    found = True
                                    break
            if found:
                    break
    if not found:
        raise sysmonitorexception.UNKDEV
    return ifName


if __name__ == "__main__":
        monitor = SysMonitor()
    #monitor.interfaces()
    
#    monitor.checkall()
 
        print monitor.checkres(RES_ETH) 
        result = monitor.checkres(RES_IP)
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
            
        result = monitor.checkres(RES_DEV, "172.16.181.129")
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
            
        result = monitor.checkres(RES_MAC, "172.16.181.129")
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
            
        result = monitor.checkres(RES_MASK, "172.16.181.129")
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
            
        result = monitor.checkres(RES_ETH)
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
            
        result = monitor.checkres(RES_WIFI)
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
            
#         result = monitor.checkres(RES_HSPA)
#         for key, val in result.items(): 
#             logger.info("| %s\t: %s" % (key, val))
#         logger.info("--------")
#             
        #for i in range(8):
        result = monitor.checkres(RES_RAM)
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
        #time.sleep(0.2)
            
        result = monitor.checkres(RES_HOSTS)
        for key, val in result.items(): 
            logger.info("| %s\t: %s" % (key, val))
        logger.info("--------")
    
    