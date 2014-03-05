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
from string import zfill
import threading
import time
import urllib2

from errorcoder import Errorcoder
from logger import logging
import netstat
import paths
from statistics import Statistics
from ftplib import FTP


TOTAL_MEASURE_TIME = 10
THRESHOLD_START = 0.05

logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)

''' 
NOTE: not thread-safe, make sure to only call 
one measurement at a time!
'''

class FtpTester:

    # TODO: 
    def __init__(self, dev, timeout=11, num_bytes=5 * 1024):
    
        self._maxRetry = 8
        self._timeout = timeout
        self._num_bytes = num_bytes
        self._netstat = netstat.get_netstat(dev)
        self._init_counters()
        self._is_up_test = False
        self._counting = False
    
    def get_measures(self):
        return self._measures
        
    def test_down(self, server, filename, bytes_to_transfer, username='anonymous', password='anonymous@'):
        self._is_up_test = False
        self._init_counters()
        self._test = _init_test('download')
        url = 'ftp://' + username + ':' + password + '@' + server + '/' + filename
        try:
            response = urllib2.urlopen(url)
        except Exception as e:
            self._test['errorcode'] = errors.geterrorcode(e)
            error = '[%s] Impossibile aprire la connessione FTP: %s' % (test['errorcode'], e)
            logger.error(error)
            return self._test
        
        # TODO: max retry?
        if (response.getcode() != None) and (response.getcode() != 230):
            test['errorcode'] = response.getcode()
            error = 'Ricevuto errore FTP: %s' % (response.getcode())
            logger.error(error)
            response.close()
            return self._test
        
        t_start = threading.Timer(1.0, self._read_measure)
        t_start.start()
        self._read_measure_threads.append(t_start)
        has_more = True
        
        while not self._go_ahead and has_more and not self._time_to_stop:
            buffer = response.read(self._num_bytes)
            if buffer: 
                self._transfered_bytes += len(buffer)
            else: 
                has_more = False
                
        if self._go_ahead:
            logger.debug("Starting FTP measurement....")
            self._start_total_bytes = self._netstat.get_rx_bytes()
            self._start_time = time.time()
            self._start_transfered_bytes = self._transfered_bytes
            while has_more and not self._time_to_stop:
                buffer = response.read(self._num_bytes)
                if buffer: 
                    self._transfered_bytes += len(buffer)
                    if (self._transfered_bytes - self._start_transfered_bytes) >= bytes_to_transfer:
                        self._time_to_stop = True
                else: 
                    has_more = False
                    
            if self._time_to_stop:
                self._end_time = time.time()
                self._wait_for_timers()
                self._calculate_statistics_down()
            else:
                test['errorcode'] = 99999 # TODO errors.geterrorcode("File non sufficientemente grande per la misura")
                self._time_to_stop = True
        else:
            self._test['errorcode'] = errors.geterrorcode("Bitrate non stabilizzata")
            
        response.close()
        return self._test
    
    def _init_counters(self):
        self._time_to_stop = False
        self._transfered_bytes = 0
        self._last_transfered_bytes = 0
        self._last_total_bytes = 0
        self._measures = []
        self._measure_count = 0
        self._go_ahead = False
        self._test = None
        self._read_measure_threads = []
        self._last_diff = 0
        self._max_transferred_bytes = 0
        self._last_measured_time = time.time()



    def _get_max_rate(self):
      
      max_rate = 0
      for (count, transferred, elapsed) in self._measures:
        max_rate = max(transferred*8.0/elapsed, max_rate)
      return max_rate

    
    def _read_measure(self):
        measuring_time = time.time()
        new_transfered_bytes = self._transfered_bytes

        diff = new_transfered_bytes - self._last_transfered_bytes
        elapsed = (measuring_time - self._last_measured_time)*1000.0
        if self._go_ahead:
            self._measures.append((self._measure_count, diff, elapsed))
        logger.debug("Reading... count = %d, diff = %d bytes, total = %d bytes, time = %d ms" % (self._measure_count, diff, self._transfered_bytes, elapsed))
        if (not self._go_ahead) and (self._last_transfered_bytes != 0) and (self._last_diff != 0):
            acc = abs((diff * 1.0 - self._last_diff) / self._last_diff)
            logger.debug("acc = abs((%d - %d)/%d) = %.4f" % (diff, self._last_diff, self._last_diff, acc))
            if acc < THRESHOLD_START:
                self._go_ahead = True
                if self._is_up_test:
                    self.start_up_measurement()
        
        self._last_diff = diff
        self._measure_count += 1
        self._last_transfered_bytes = new_transfered_bytes
        self._last_measured_time = measuring_time
        
        new_total_bytes = self._netstat.get_tx_bytes()
        diff_total_bytes = new_total_bytes - self._last_total_bytes 
        self._last_total_bytes = new_total_bytes
        
        if not self._time_to_stop:
            t = threading.Timer(1.0, self._read_measure)
            self._read_measure_threads.append(t)
            t.start()
    

    def _calculate_statistics_up(self):
        self._calculate_statistics_generic()
        total_bytes = self._netstat.get_tx_bytes() - self._start_total_bytes
        self._test['bytes_total'] = total_bytes 
    
    def _calculate_statistics_down(self):
        self._calculate_statistics_generic()
        total_bytes = self._netstat.get_rx_bytes() - self._start_total_bytes
        self._test['bytes_total'] = total_bytes 
        
    def _calculate_statistics_generic(self):
        elapsed_time = float((self._end_time - self._start_time) * 1000)
        measured_bytes = self._transfered_bytes - self._start_transfered_bytes
        kbit_per_second = (measured_bytes * 8.0) / elapsed_time
        self._test['bytes'] = measured_bytes
        self._test['time'] = elapsed_time
        self._test['rate_avg'] = kbit_per_second
        self._test['rate_max'] = self._get_max_rate()
        self._test['stats'] = Statistics(payload_up_nem_net=measured_bytes, packet_up_nem_net=(measured_bytes / self._num_bytes), packet_down_nem_net=(measured_bytes / self._num_bytes), packet_tot_all=100)
        logger.info("Banda: (%s*8)/%s = %s Kbps" % (measured_bytes, elapsed_time, kbit_per_second))
    

    def _wait_for_timers(self):
        for t in self._read_measure_threads:
            if (t.isAlive()):
                t.join()

    def test_up(self, server, filename, bytes_to_send, username='anonymous', password='anonymous@'):
        self._is_up_test = True
        self._init_counters()
        self._test = _init_test('upload')
        self._num_bytes_to_send = bytes_to_send
#         self._fakefile = FakefileFtp(self, bytes_to_send)
        t_start = threading.Timer(1.0, self._read_measure)
        t_start.start()
        self._read_measure_threads.append(t_start)
        ftpsession = FTP(server, username, password)
#        ftpsession.storbinary('STOR %s' % filename, self._fakefile)
        ftpsession.storbinary('STOR %s' % filename, self)
        self._wait_for_timers()
        self._calculate_statistics_up()
        return self._test
    
    def start_up_measurement(self):
        self._start_time = time.time()
        self._start_transfered_bytes = self._transfered_bytes
        self._start_total_bytes = self._netstat.get_tx_bytes()
        self._last_total_bytes =  self._start_total_bytes
#         self._fakefile.start_counting()
        self._counting = True
        self._go_ahead = True

    def stop_up_measurement(self):
        self._time_to_stop = True
        self._end_time = time.time()

    def add_data(self, bufsize):
        self._transfered_bytes += bufsize
        if (self._num_bytes is None):
            self._num_bytes = bufsize
        
    def get_transfered_bytes(self):
        return self._transfered_bytes

    def read(self, bufsize):
        data = ""
#         if self._counting and (self._transfered_bytes() >= self._num_bytes_to_send):
        if not self._time_to_stop:
            data = '%x' % random.randint(0, 2 ** (8 * bufsize) - 1)
            data = data.rjust(bufsize*2, '0')
            data = data.decode('hex')
            self._transfered_bytes += bufsize
            if self._go_ahead and (self._transfered_bytes >= self._num_bytes_to_send):
                self.stop_up_measurement()

        return data
    
    def start_counting(self):
        self._counting = True


class FakefileFtp:

    def __init__(self, ftptester, num_bytes_to_send):
        self._ftptester = ftptester
        self._num_bytes_to_send = num_bytes_to_send
        self._counting = False
    
    def read(self, bufsize):
        data = ""
        if self._counting and (self._ftptester.get_transfered_bytes() >= self._num_bytes_to_send):
            self._ftptester.stop_up_measurement()
        else:
            data = '%x' % random.randint(0, 2 ** (8 * bufsize) - 1)
            data = data.rjust(bufsize*2, '0')
            data = data.decode('hex')
            self._ftptester.add_data(bufsize)
        return data
    
    def start_counting(self):
        self._counting = True
    
def _init_test(type):
    test = {}
    test['type'] = type
    test['protocol'] = 'ftp'
    test['time'] = 0
    test['bytes'] = 0
    test['stats'] = {}
    test['errorcode'] = 0
    return test
        

if __name__ == '__main__':
    import platform
    platform_name = platform.system().lower()
    dev = None
    nap = "eagle2.fub.it"
#     nap = '193.104.137.133'
    if "win" in platform_name:
        dev = "Scheda Ethernet"
    else:
        dev = "eth0"
    t = FtpTester(dev)
        
#     print t.test_down(nap, '/download/40000.rnd', 1000000, 'nemesys', '4gc0m244')
    print "\n---------------------------\n"
    print t.test_up(nap, '/upload/r.raw', 100000000, 'nemesys', '4gc0m244')
    print "\n---------------------------\n"
#     print t.test_down("ftp://%s/" % host)
