# sysmonitor.py
# -*- coding: utf8 -*-

# Copyright (c) 2016 Fondazione Ugo Bordoni.
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
import netifaces
import platform
import time

import checkhost
import iptools
import netstat
import logging
import profiler
from sysmonitorexception import SysmonitorException
import sysmonitorexception
import system_resource

platform_name = platform.system().lower()

# Decidere se, quando non riesco a determinare i valori, sollevo eccezione
STRICT_CHECK = True

CHECK_ALL = "ALL"
CHECK_MEDIUM = "MEDIUM"

# Soglie di sistema
# ------------------------------------------------------------------------------
# Massima quantità di host in rete
th_host = 1
# Minima memoria disponibile
th_avMem = 134217728
# Massimo carico percentuale sulla memoria
th_memLoad = 95
# Massimo carico percentuale sulla CPU
th_cpu = 85

logger = logging.getLogger(__name__)


class SysMonitor():
    def __init__(self):
        self._strict_check = True
        self._profiler = profiler.get_profiler()
        self._netstat =  netstat.get_netstat(iptools.get_dev())
        self._checks = OrderedDict \
        ([ \
        (system_resource.RES_OS,self.check_os),\
        (system_resource.RES_CPU,self.checkcpu),\
        (system_resource.RES_RAM,self.checkmem),\
        (system_resource.RES_ETH,self.is_ethernet_active),\
        (system_resource.RES_WIFI,self.checkwireless),\
        (system_resource.RES_HOSTS,self.checkhosts),\
        (system_resource.RES_TRAFFIC,self.check_traffic) \
        ])

  
    def checkres(self, res, *args):
        return self._checks[res](*args)
        
    
    '''
    TODO:
    
    Log this:
    
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():90 [INFO] ============================================
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Name : eth12
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Device : eth12
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Status : Enabled
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | isActive : True
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Type : Ethernet 802.3
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | IPaddress : 192.168.112.24
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | MACaddress : 78:2b:cb:96:55:3e
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():90 [INFO] ============================================
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Name : lo
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Device : lo
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Status : Disabled
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | isActive : False
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Type : 772
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | IPaddress : 127.0.0.1
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | MACaddress : 00:00:00:00:00:00
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():90 [INFO] ============================================
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Name : vboxnet0
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Device : vboxnet0
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Status : Disabled
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | isActive : False
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | Type : Ethernet 802.3
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | IPaddress : 127.0.0.1
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():92 [INFO] | MACaddress : 0a:00:27:00:00:00
    apr 13 13:51:42 MIST sysMonitor.py.interfaces():93 [INFO] ============================================
    
    or, on windows:
    
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():93 [INFO] ============================================
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Status : 2
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Name : Scheda desktop Intel(R) PRO/1000 MT
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Descr : Connessione alla rete locale (LAN)
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | IP : 10.0.2.15
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Mask : 255.255.255.0
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | MAC : 08:00:27:27:60:B7
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | IfName : S
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | GUID : {F01A0ADB-6C17-420D-A837-C7F47D8B37F2}
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Type : Ethernet 802.3
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Gateway : 10.0.2.2
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():93 [INFO] ============================================
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Status : 0
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Name : RAS Async Adapter
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Descr : unknown
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | IP : unknown
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Mask : unknown
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | MAC : unknown
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | IfName : R
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | GUID : {78032B7E-4968-42D3-9F37-287EA86C0AAA}
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Type : unknown
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():95 [INFO] | Gateway : unknown
    Mar 21 14:47:23 MIST sysMonitor.py.interfaces():96 [INFO] ============================================
    
    Currently on WIn:
    
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():147 [INFO] ============================================
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _type_string : Ethernet 802.3
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _is_enabled : 2
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _name : Scheda desktop Intel(R) PRO/1000 MT
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _macaddr : 08:00:27:27:60:B7
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _ipaddr : 10.0.2.15
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _is_active : False
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():151 [INFO] ============================================
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():147 [INFO] ============================================
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _type_string : Unknown
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _is_enabled : False
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _name : RAS Async Adapter
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _macaddr : 00:00:00:00:00:00
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _ipaddr : 0.0.0.0
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():150 [INFO] | _is_active : False
    Apr 13 15:56:48 MIST sysMonitor.py.log_interfaces():151 [INFO] ============================================
    
    '''
    def log_interfaces(self):
        all_devices = self._profiler.get_all_devices()
        for device in all_devices:
            logger.info("============================================")
            device_dict = device.dict()
            for key in device_dict: 
                logger.info("| %s : %s" % (key, device_dict[key]))
            logger.info("============================================")
    

    def check_os(self, res = system_resource.RES_OS):
        value = 'unknown'
        try:
            value = platform.platform()
            info = ("Sistema Operativo %s" % value)
            status = True 
        except Exception as e:
            info = e
            status = False
        return system_resource.SystemResource(system_resource.RES_OS, status, value, info)


    def checkcpu(self):
        try:
            value = self._profiler.cpuLoad()
            if value < 0 or value > 100:
                raise SysmonitorException(sysmonitorexception.BADCPU, 'Valore di occupazione della cpu non conforme.')
        
            if value > th_cpu:
                raise SysmonitorException(sysmonitorexception.WARNCPU, 'CPU occupata')
            info = 'Utilizzato il %s%% del processore' % value
            status = True
        except Exception as e:
            info = e
            status = False
        return system_resource.SystemResource(system_resource.RES_CPU, status, value, info)

    
    def checkmem(self):
        try:
            avMem = self._profiler.total_memory()
            logger.debug("Memoria disponibile: %2f" % avMem)
            if avMem < 0:
                raise SysmonitorException(sysmonitorexception.BADMEM, 'Valore di memoria disponibile non conforme.')
            if avMem < th_avMem:
                raise SysmonitorException(sysmonitorexception.LOWMEM, 'Memoria disponibile non sufficiente.')
            
            memLoad = self._profiler.percentage_ram_usage()
            logger.debug("Memoria occupata: %d%%" % memLoad)
            if memLoad < 0 or memLoad > 100:
                raise SysmonitorException(sysmonitorexception.INVALIDMEM, 'Valore di occupazione della memoria non conforme.')
            if memLoad > th_memLoad:
                raise SysmonitorException(sysmonitorexception.OVERMEM, 'Memoria occupata.')
        
            info = 'Utilizzato il %s%% di %d GB della memoria' % (memLoad, avMem / (1000*1000*1000))
            status = True
        except Exception as e:
            info = e
            status = False
        return system_resource.SystemResource(system_resource.RES_RAM, status, memLoad, info)

    def checkwireless(self):
        try:
            value = None
            if self._profiler.is_wireless_active():
                value = 1
                raise SysmonitorException(sysmonitorexception.WARNWLAN, 'Wireless LAN attiva.')
            else:
                value = 0
                info = 'Dispositivi wireless non attivi.'
                status = True
        except Exception as e:
            logger.error("ERRORE", exc_info=True)
            info = e
            status = False
        return system_resource.SystemResource(system_resource.RES_WIFI, status, value, info)
                
    
    'TODO ma che fa questo?'
    def checkhosts(self, bandwidth_up=2048, bandwidth_down=2048, arping=1):
        call_ping = False
        try:
            ip = iptools.getipaddr()
            mask = iptools.get_network_mask(ip)
            dev = iptools.get_dev(ip = ip)
            
            logger.info("Indirizzo ip/mask: %s/%d, device: %s" % (ip, mask, dev))
            
            if iptools.is_public_ip(ip):
                value = 1
                info = 'La scheda di rete in uso ha un IP pubblico. Non controllo il numero degli altri host in rete.'
            else:
                if (arping == 0):
                    thres = th_host + 1
                else:
                    thres = th_host
                
                if (mask != 0):
                    value = checkhost.countHosts(ip, mask, bandwidth_up, bandwidth_down, thres, 1)
                    logger.info('Trovati %d host in rete.' % value)
                    
                    if value < 0:
                        raise SysmonitorException(sysmonitorexception.BADHOST, 'impossibile determinare il numero di host in rete.')
                    elif (value == 0):
                        if arping == 1:
                            logger.warning("Passaggio a PING per controllo host in rete")
                            call_ping = True
                            return self.checkhosts(bandwidth_up, bandwidth_down, 0)
                        else:
                            raise SysmonitorException(sysmonitorexception.BADHOST, 'impossibile determinare il numero di host in rete.')
                    elif value > thres:
                        raise SysmonitorException(sysmonitorexception.TOOHOST, 'Presenza altri host in rete.')
                else:
                    raise SysmonitorException(sysmonitorexception.BADMASK, 'Impossibile recuperare il valore della maschera dell\'IP: %s' % ip)
        except Exception as e:
            info = e
            status = False
        if call_ping:
            self.checkhosts(bandwidth_up, bandwidth_down, 0)
        return system_resource.SystemResource(system_resource.RES_HOSTS, status, value, info)


    def is_ethernet_active(self, res = system_resource.RES_ETH):
    
        try:
            value = -1
            num_active_eth = 0
            info = 'Dispositivi ethernet non presenti.'
            devices = self._profiler.get_all_devices()
            for device in devices:
                dev_type = device.type
                if (dev_type == 'Ethernet 802.3'):
                    
                    if (platform.system().lower().startswith('win')):
                        guid = device.guid
                        my_netstat = netstat.get_netstat(guid)
                        if (my_netstat.is_device_active()):
                            num_active_eth += 1
                        else:
                            logger.debug("Found inactive Ethernet device")

                    else:
                        if device.is_enabled and device.is_active:
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
            value = 0
            status = False
        return system_resource.SystemResource(system_resource.RES_ETH, status, value, info)
    
    
    
    def check_traffic(self, sec = 2, res = system_resource.RES_TRAFFIC):
        
        try:
            value = 'unknown'
            'TODO check for modified ip or dev'
            ip = iptools.getipaddr()
            dev = iptools.get_dev(ip = ip)
            logger.debug("getting stats from dev " + dev)
            start_rx_bytes = self._netstat.get_rx_bytes()
            start_tx_bytes = self._netstat.get_tx_bytes()
            logger.debug("start rx %d, start tx %d" % (start_rx_bytes,start_tx_bytes))
            start_time = time.time()
            time.sleep(sec)
            end_rx_bytes = self._netstat.get_rx_bytes()
            end_tx_bytes = self._netstat.get_tx_bytes()
            measure_time_millis = (time.time() - start_time) * 1000
            logger.debug("end rx %d, end tx %d" % (end_rx_bytes, end_tx_bytes))
            logger.debug("total time millis %d" % measure_time_millis)

            UP_kbps = (end_tx_bytes - start_tx_bytes) * 8 / measure_time_millis
            DOWN_kbps = (end_rx_bytes - start_rx_bytes) * 8 / measure_time_millis
            if ( (UP_kbps < 0) or (DOWN_kbps < 0)):
                    raise SysmonitorException(sysmonitorexception.FAILREADPARAM, "Ottenuto valore di traffico negativo, potrebbe dipendere dall'azzeramento dei contatori.")

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
        return system_resource.SystemResource(system_resource.RES_TRAFFIC, status, value, info)
    

    
    def mediumcheck(self):
    
        self.checkcpu()
        self.checkmem()
        #checktasks()
        #checkconnections()
        #checkfw()
        self.checkwireless()
    
    
    def checkall(self, up, down, ispid, arping = 1):
    
        self.mediumcheck()
        self.checkhosts(up, down, ispid, arping)
        # TODO: Reinserire questo check quanto corretto il problema di determinazione del dato
        #checkdisk()
    
    
    def _get_NetIF(self):
        my_interfaces = {}
        for ifName in netifaces.interfaces():
            #logger.debug((ifName,netifaces.ifaddresses(ifName)))
            mac = [i.setdefault('addr', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_LINK, [{'addr':''}])]
            ip = [i.setdefault('addr', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'addr':''}])]
            mask = [i.setdefault('netmask', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'netmask':''}])]
            if mask[0] == '0.0.0.0':
                mask = [i.setdefault('broadcast', '') for i in netifaces.ifaddresses(ifName).setdefault(netifaces.AF_INET, [{'broadcast':''}])]
            my_interfaces[ifName] = {'mac':mac, 'ip':ip, 'mask':mask}
        logger.debug('Network Interfaces:\n %s' % my_interfaces)
            
        return my_interfaces
    

if __name__ == '__main__':
    import log_conf
    log_conf.init_log()
#     import errorcode
    sysmonitor = SysMonitor()
#     print '\ncheckall'
#     try:
# #         print 'Test sysmonitor checkall: %s' % sysmonitor.checkall(1000, 2000, 'fst001')
#         print 'Test sysmonitor checkall: %s' % sysmonitor.checkall(1000, 2000, 'pippo')
#     except Exception as e:
#         print 'Errore: %s' % e
    try:
        print '\ncheckhosts (arping)'
        print 'Test sysmonitor checkhosts: %s' % sysmonitor.checkhosts(2000, 2000, 1)  #ARPING
    except Exception as e:
        print 'Errore: %s' % e
      
    try:
        print '\ncheckhosts (ping)'
        print 'Test sysmonitor checkhosts: %s' % sysmonitor.checkhosts(2000, 2000, 0)  #PING
    except Exception as e:
        print 'Errore: %s' % e
      
#     try:
#         print '\ncheckcpu'
#         print 'Test sysmonitor checkcpu: %s' % sysmonitor.checkcpu()
#     except Exception as e:
#         print 'Errore: %s' % e
#      
#     try:
#         print '\ncheckmem'
#         print 'Test sysmonitor checkmem: %s' % sysmonitor.checkmem()
#     except Exception as e:
#         print 'Errore: %s' % e
#      
#     try:
#         print '\ncheckwireless'
#         print 'Test sysmonitor checkwireless: %s' % sysmonitor.checkwireless()
#     except Exception as e:
#         print 'Errore: %s' % e
#       
#     try:
#         print '\nget MAC'
#         print 'Test sysmonitor get MAC: %s' % sysmonitor.get_mac(None)
#     except Exception as e:
#         print 'Errore: %s' % e
#         logger.error(e, exc_info=True)
#      
#     try:
#         print '\nLog interfaces'
#         print 'Test sysmonitor log interfaces: %s' % sysmonitor.log_interfaces()
#     except Exception as e:
#         print 'Errore: %s' % e
#         logger.error(e, exc_info=True)
#     try:
#     print '\ncheck ethernet'
#     print 'Test sysmonitor is_ethernet_active: %s' % sysmonitor.is_ethernet_active()
#     except Exception as e:
#         print 'Errore: %s' % e
      
    


