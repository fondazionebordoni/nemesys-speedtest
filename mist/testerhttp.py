# httptester.py
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
MAX_TRANSFERED_BYTES = 100 * 1000000 * 11 / 8 # 100 Mbps for 11 seconds
END_STRING = '_ThisIsTheEnd_'

logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)

''' 
NOTE: not thread-safe, make sure to only call 
one measurement at a time!
'''

class HttpTester:

    # TODO: 
    def __init__(self, dev, timeout_secs = 11, bufsize = 8 * 1024, rampup_secs = 0):
    
    
        self._maxRetry = 8 # Not used
        self._timeout_secs = timeout_secs # Not used
        self._num_bytes = bufsize
        self._rampup_secs = rampup_secs
        self._netstat = netstat.get_netstat(dev)
        self._init_counters()
        self._fakefile = None
    
    def _init_counters(self):
        self._time_to_stop = False
        self._go_ahead = False
        self._file_bytes = 0
        self._last_file_bytes = 0
        self._last_tx_bytes = self._netstat.get_tx_bytes()
        self._last_rx_bytes = self._netstat.get_rx_bytes()
        self._initial_rx_bytes = self._last_rx_bytes
        self._initial_tx_bytes = self._last_tx_bytes
        self._measures = []
        self._measure_count = 0
        self._test = None
        self._read_measure_threads = []
        self._last_measured_time = time.time()

    def get_measures(self):
        return self._measures
        
    def test_down(self, url):
        self._init_counters()
        test = _init_test('download')
        t_end = None
        try:
            response = urllib2.urlopen(url)
        except Exception as e:
            raise MeasurementException("Impossibile aprire la connessione HTTP")
        if response.getcode() != 200:
            raise MeasurementException("Impossibile aprire la connessione HTTP, codice di errore ricevuto: %d" % response.getcode())
        
        t_start = threading.Timer(self._rampup_secs, self._start_measure)
        t_start.start()
        has_more = True
        while not self._go_ahead and has_more and not self._time_to_stop:
            my_buffer = response.read(self._num_bytes)
            if my_buffer: 
                self._file_bytes += len(my_buffer)
            else: 
                has_more = False
                
        if self._go_ahead:
    
            self._starttime = time.time()
            t = threading.Timer(1.0, self._read_down_measure)
            t.start()
            self._read_measure_threads.append(t)
            
            logger.debug("Starting HTTP measurement....")
            self.starttotalbytes = self._netstat.get_rx_bytes()
            self._measurement_starttime = time.time()
            self.startbytes = 0
            self._starttime = time.time()
            t_end = threading.Timer(TOTAL_MEASURE_TIME, self._stop_down_measure)
            t_end.start()
            while has_more and not self._time_to_stop:
                my_buffer = response.read(self._num_bytes)
                if my_buffer: 
                    self._file_bytes += len(my_buffer)
                else: 
                    has_more = False
                    
            if self._time_to_stop:
                end_time = time.time()
                elapsed_time = float((end_time - self._measurement_starttime) * 1000)
                measured_bytes = self._file_bytes - self.startbytes
                total_bytes = self._netstat.get_rx_bytes() - self.starttotalbytes
                if (total_bytes < 0):
                    raise MeasurementException("Ottenuto banda negativa, possibile azzeramento dei contatori.")
                kbit_per_second = (measured_bytes * 8.0) / elapsed_time
                test['bytes'] = measured_bytes
                test['time'] = elapsed_time
                test['rate_medium'] = kbit_per_second
                test['rate_max'] = self._get_max_rate() 
                test['rate_secs'] = self._measures
                test['bytes_total'] = total_bytes
                spurio = float(test['bytes_total']-test['bytes'])/float(test['bytes_total'])
                test['spurious'] = spurio 
                test['stats'] = Statistics(byte_down_nem = measured_bytes, byte_down_all = total_bytes)
                logger.info("Banda (payload): (%s*8)/%s = %s Kbps" % (measured_bytes, elapsed_time, kbit_per_second))
                logger.info("Banda (totale): (%s*8)/%s = %s Kbps" % (total_bytes, elapsed_time, (total_bytes*8/elapsed_time)))
                logger.info("Traffico spurio: %f" % spurio)
            else:
                raise MeasurementException("File non sufficientemente grande per la misura")
        else:
            raise MeasurementException("File non sufficientemente grande per fare partire la misura")
            
        for t in self._read_measure_threads:
           t.join()
        t_start.join()
        if t_end:
            t_end.join()
        response.close()
        return test

    def _get_max_rate(self):
      return max(self._measures)

    def _start_measure(self):
        logger.info("Starting measure...")
        self._go_ahead = True

    def _stop_measurement(self):
        logger.debug("Stopping....")
        self._time_to_stop = True
        for t in self._read_measure_threads:
           t.join()
    
   
    def _read_down_measure(self):
        measuring_time = time.time()
        new_transfered_bytes = self._file_bytes
        new_rx_bytes = self._netstat.get_rx_bytes()
        rx_diff = new_rx_bytes - self._last_rx_bytes
        diff = new_transfered_bytes - self._last_file_bytes
        elapsed = (measuring_time - self._last_measured_time)*1000.0
        rate = float(diff*8)/float(elapsed)
        self._measures.append(rate)
        
        logger.debug("Reading... count = %d, diff = %d, total = %d, rx diff= %d, total = %d, rx - read = %d" 
              % (self._measure_count, diff, new_transfered_bytes, rx_diff, new_rx_bytes, (rx_diff - diff)))
        self._measure_count += 1
        self._last_file_bytes = new_transfered_bytes
        self._last_rx_bytes = new_rx_bytes
        self._last_measured_time = measuring_time
          
        if not self._time_to_stop:
            t = threading.Timer(1.0, self._read_down_measure)
            self._read_measure_threads.append(t)
            t.start()
            
    def _stop_down_measure(self):
        self._time_to_stop = True
            
            
    def read(self, bufsize = -1):
        elapsed = time.time() - self._starttime
        if not self._time_to_stop and (elapsed < self._timeout_secs) and (self._fakefile.get_bytes_read() < MAX_TRANSFERED_BYTES):
            return self._fakefile.read(bufsize)
        elif not self._has_stopped:
            self._has_stopped = True
            return END_STRING * (self._recv_bufsize / len(END_STRING) + 1)
        else:
            return None

        
    '''
    Upload test is done server side. We just measure
    the average speed payload/net in order to 
    verify spurious traffic.
    '''
    def test_up(self, url, file_size = MAX_TRANSFERED_BYTES, recv_bufsize = 8 * 1024):
        self._has_stopped = False
        self._recv_bufsize = recv_bufsize
        self._test = _init_test('upload')
        headers = {'X-buf-size': str(recv_bufsize)}

        self._fakefile = Fakefile(file_size)
        response = None
        self._starttime = time.time()
        start_tx_bytes = self._netstat.get_tx_bytes()
        try:
            response = requests.post(url, headers=headers, data=self)#, hooks = dict(response = self._response_received))
        except Exception as e:
            raise MeasurementException("Errore di connessione: %s" % str(e))
        if response:
            if response.status_code == 200:
                self._test = _test_from_server_response(response.content)
            else:
                raise MeasurementException("Ricevuto risposta %d dal server" % response.status_code)
        else:
            raise MeasurementException("Nessuna risposta") 
        tx_diff = self._netstat.get_tx_bytes() - start_tx_bytes
        read_bytes = self._fakefile.get_bytes_read()
        spurious = (float(tx_diff - read_bytes)/float(tx_diff))
        self._test['spurious'] = spurious
        return self._test
    
    def _response_received(self, r, *args, **kwargs):
        logger.info("Got response: %s" % r.text)
        self._time_to_stop = True
    
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
        
def _test_from_server_response(response):
    test = {}
    test['type'] = 'upload'
    test['protocol'] = 'http'
    results = str(response).split(',')
    medium_rate = float(results[0])
    partial_rates = [float(x) for x in results[1:]] 
    test['rate_medium'] = medium_rate
    test['rate_max'] = max(partial_rates)
    test['rate_secs'] = partial_rates
    test['errorcode'] = 0
    return test
        
        
# def pippo(r, *args, **kwargs):
#     print "Pippo"
    
if __name__ == '__main__':
#    host = "10.80.1.1"
#    host = "193.104.137.133"
#    host = "regopptest6.fub.it"
    host = "eagle2.fub.it"
#    host = "rocky.fub.it"
#    host = "billia.fub.it"
    import sysMonitor
    dev = sysMonitor.getDev()
    t = HttpTester(dev, rampup_secs=0)
#    print "\n------ UPLOAD ---------\n"
#    res = t.test_up("http://%s/" % host, file_size = MAX_TRANSFERED_BYTES, recv_bufsize = 1024)
#    print("Medium: %s, Max: %s, Spurious: %s" % (res['rate_medium'], res['rate_max'], res['spurious']))
    print "\n------ DOWNLOAD -------\n"
    res = t.test_down("http://%s/" % host)
    print("Medium: %s, Max: %s, Spurious: %s" % (res['rate_medium'], res['rate_max'], res['spurious']))
    print res['rate_secs']
