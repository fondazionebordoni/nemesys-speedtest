# tester.py
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

import random
import requests
from string import lowercase
import threading
import time
import urllib2

from errorcoder import Errorcoder
from fakefile import Fakefile
from logger import logging
import netstat
import paths
from statistics import Statistics
from measurementexception import MeasurementException
from multiprocessing import Queue


TOTAL_MEASURE_TIME = 10
RAMPUP_TIME = 3.0
MAX_TRANSFERED_BYTES = 100 * 1000000 * 8 * 15 # 100 Mbps for 15 seconds

logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)

''' 
NOTE: not thread-safe, make sure to only call 
one measurement at a time!
'''

class HttpTester:

    # TODO: 
    def __init__(self, dev, ip, host, timeout_secs = 11, bufsize = 8 * 1024):
    
    
        self._maxRetry = 8 # Not used
        self._timeout_secs = timeout_secs # Not used
        self._num_bytes = bufsize
        self._netstat = netstat.get_netstat(dev)
        self._init_counters()
        self._fakefile = None
    
    def _init_counters(self):
        self._time_to_stop = False
        self._go_ahead = False
        self._transfered_bytes = 0
        self._last_transfered_bytes = 0
        self._measures = []
        self._measure_count = 0
        self._test = None
        self._read_measure_threads = []
        self._max_transferred_bytes = 0
        self._last_measured_time = time.time()

    def get_measures(self):
        return self._measures
        
    def test_down(self, url):
        self._init_counters()
        test = _init_test('download')
        bit_per_second = -1
        t_end = None

        try:
            response = urllib2.urlopen(url)
        except Exception as e:
            raise MeasurementException("Impossibile aprire la connessione HTTP")
        if response.getcode() != 200:
            raise MeasurementException("Impossibile aprire la connessione HTTP, codice di errore ricevuto: %d" % response.getcode())
        
        # TODO: use requests lib instead?
        self._starttime = time.time()
        t_start = threading.Timer(1.0, self._read_down_measure)
        t_start.start()
        has_more = True
        
        while not self._go_ahead and has_more:
            my_buffer = response.read(self._num_bytes)
            if my_buffer: 
                self._transfered_bytes += len(my_buffer)
            else: 
                has_more = False
                                
        if self._go_ahead:
            logger.debug("Starting HTTP measurement....")
            start_total_bytes = self._netstat.get_rx_bytes()
            start_time = time.time()
            start_transfered_bytes = self._transfered_bytes
            t_end = threading.Timer(TOTAL_MEASURE_TIME, self._stop_measurement)
            t_end.start()
            while has_more and not self._time_to_stop:
                my_buffer = response.read(self._num_bytes)
                if my_buffer: 
                    self._transfered_bytes += len(my_buffer)
                else: 
                    has_more = False
                    
            if self._time_to_stop:
                end_time = time.time()
                elapsed_time = float((end_time - start_time) * 1000)
                measured_bytes = self._transfered_bytes - start_transfered_bytes
                total_bytes = self._netstat.get_rx_bytes() - start_total_bytes
                if (total_bytes < 0):
                    raise MeasurementException("Ottenuto banda negativa, possibile azzeramento dei contatori.")
                    #test['errorcode'] = errors.geterrorcode("Ottenuto banda negativa, possibile azzeramento dei contatori.")
                kbit_per_second = (measured_bytes * 8.0) / elapsed_time
                test['bytes'] = measured_bytes
                test['time'] = elapsed_time
                test['rate_avg'] = kbit_per_second
                test['rate_max'] = self._get_max_rate() 
                test['bytes_total'] = total_bytes
                test['stats'] = Statistics(byte_down_nem = measured_bytes, byte_down_all = total_bytes)
                logger.info("Banda: (%s*8)/%s = %s Kbps" % (measured_bytes, elapsed_time, kbit_per_second))
            else:
                raise MeasurementException("File non sufficientemente grande per la misura")
#                test['errorcode'] = errors.geterrorcode("File non sufficientemente grande per la misura")
        else:
            self._stop_measurement()
            raise MeasurementException("Bitrate non stabilizzata")
#            test['errorcode'] = errors.geterrorcode("Bitrate non stabilizzata")
            
        t_start.join()
        if t_end:
            t_end.join()
        response.close()
        return test

    def _get_max_rate(self):
      
      max_rate = 0
      for (count, transferred, elapsed) in self._measures:
        max_rate = max(transferred*8.0/elapsed, max_rate)      
      return max_rate

    def _stop_measurement(self):
        logger.debug("Stopping....")
        self._time_to_stop = True
        for t in self._read_measure_threads:
           t.join()
    
   
    def _read_down_measure(self):
        measuring_time = time.time()
        new_transfered_bytes = self._transfered_bytes

        diff = new_transfered_bytes - self._last_transfered_bytes
        elapsed = (measuring_time - self._last_measured_time)*1000.0
        if self._go_ahead:
            self._measures.append((self._measure_count, diff, elapsed))
        
        logger.debug("Reading... count = %d, diff = %d bytes, total = %d bytes, time = %d ms" % (self._measure_count, diff, self._transfered_bytes, elapsed))

        if (not self._go_ahead) and (measuring_time - self._starttime) > RAMPUP_TIME:
                self._go_ahead = True

        self._measure_count += 1
        self._last_transfered_bytes = new_transfered_bytes
        self._last_measured_time = measuring_time
          
        if not self._time_to_stop:
            t = threading.Timer(1.0, self._read_down_measure)
            self._read_measure_threads.append(t)
            t.start()
            
            
    def _read_up_measure(self):
        measuring_time = time.time()
        new_transfered_bytes = self._fakefile.get_bytes_read()
        diff = new_transfered_bytes - self._last_transfered_bytes
        elapsed = (measuring_time - self._last_measured_time)*1000.0
        if self._go_ahead:
            self._measures.append((self._measure_count, diff, elapsed))
        logger.debug("Reading... count = %d, diff = %d bytes, total = %d bytes, time = %d ms" % (self._measure_count, diff, new_transfered_bytes, elapsed))
        if not self._go_ahead and measuring_time - self._starttime > RAMPUP_TIME:
            logger.debug("Starting...")
            self._go_ahead = True
            self._measurement_starttime = time.time()
            self.startbytes = new_transfered_bytes
            self.starttotalbytes = self._netstat.get_tx_bytes()
            t_end = threading.Timer(10.0, self._stop_up_measure)
            t_end.start()
        
        self._measure_count += 1
        self._last_transfered_bytes = new_transfered_bytes
        self._last_measured_time = measuring_time
          
        if not self._time_to_stop:
            t = threading.Timer(1.0, self._read_up_measure)
            self._read_measure_threads.append(t)
            t.start()
    
    def _stop_up_measure(self):
        self._time_to_stop = True
        if self._go_ahead:
            endtime = time.time()
            endbytes = self._fakefile.get_bytes_read()
            elapsed_time = float((endtime - self._measurement_starttime) * 1000)
            measured_bytes = endbytes - self.startbytes
            kbit_per_second = (measured_bytes * 8.0) / elapsed_time
            total_bytes = self._netstat.get_tx_bytes() - self.starttotalbytes
            if (total_bytes < 0):
                if self._exception_queue:
                    self._exception_queue.put("Ottenuto banda negativa, possibile azzeramento dei contatori")
            else:
                self._test['bytes'] = measured_bytes
                self._test['time'] = elapsed_time
                self._test['rate_avg'] = kbit_per_second
                self._test['rate_max'] = self._get_max_rate() 
                self._test['bytes_total'] = total_bytes
                self._test['stats'] = Statistics(byte_up_nem = measured_bytes, byte_up_all = total_bytes)
            logger.info("Banda: (%s*8)/%s = %s Kbps" % (measured_bytes, elapsed_time, kbit_per_second))
        else:
            if self._exception_queue:
                self._exception_queue.put("Errore di connessione")
            
            
    def _kill_up_measure(self):
        self._time_to_stop = True
            
            
    def read(self, bufsize = -1):
        if self._time_to_stop:
            return '_ThisIsTheEnd_'
        return self._fakefile.read(bufsize)
        

    def test_up(self, url):
        self._exception_queue = Queue()
        self._init_counters()
        self._test = _init_test('upload')
        self._fakefile = Fakefile(MAX_TRANSFERED_BYTES)
        self._starttime = time.time()
        t = threading.Timer(1.0, self._read_up_measure)
        t.start()
        try:
            response = requests.post(url, data=self)
        except Exception as e:
            if not self._time_to_stop:
                logger.debug("Connection error")
                self._kill_up_measure()
                raise MeasurementException("Errore di connessione")
        t.join()
        if not self._exception_queue.empty():
            error = self._exception_queue.get()
            raise MeasurementException(error)
        return self._test
    
    def __len__(self):
        return 1
    
def _init_test(type):
    test = {}
    test['type'] = type
    test['protocol'] = 'http'
    test['time'] = 0
    test['bytes'] = 0
    test['stats'] = {}
    test['errorcode'] = 0
    return test
        
if __name__ == '__main__':
    import platform
    platform_name = platform.system().lower()
    dev = None
    host = "eagle2.fub.it"
#    host = "billia.fub.it"
    import sysMonitor
    dev = sysMonitor.getDev()
    ip = sysMonitor.getIp()
    t = HttpTester(dev, ip, "pippo")
    print "\n---------------------------\n"
#    print t.test_up("http://%s/" % host)
    print "\n---------------------------\n"
    print t.test_down("http://%s/" % host)
