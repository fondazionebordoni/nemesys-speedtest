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

import requests
import threading
import time
import urllib2

from errorcoder import Errorcoder
from fakefile import Fakefile
from logger import logging
import netstat
import paths
from measurementexception import MeasurementException


TOTAL_MEASURE_TIME = 10
MAX_TRANSFERED_BYTES = 100 * 1000000 * 11 / 8 # 100 Mbps for 11 seconds
BUF_SIZE = 8*1024
END_STRING = '_ThisIsTheEnd_'

logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)

''' 
NOTE: not thread-safe, make sure to only call 
one measurement at a time!
'''

class HttpTester:

    def __init__(self, dev, timeout_secs = 11, bufsize = 8 * 1024, rampup_secs = 2):
        self._maxRetry = 8 # Not used
        self._timeout_secs = timeout_secs
        self._num_bytes = bufsize
        self._rampup_secs = rampup_secs
        self._netstat = netstat.get_netstat(dev)
        self._init_counters()
        self._fakefile = None
        self._upload_sending_time_secs = TOTAL_MEASURE_TIME + 1
    
    def _init_counters(self):
        self._time_to_stop = False
        self._last_tx_bytes = self._netstat.get_tx_bytes()
        self._last_rx_bytes = self._netstat.get_rx_bytes()
        self._bytes_total = 0
        self._measures_tot = []
        self._measure_count = 0
        self._read_measure_threads = []
        self._last_measured_time = time.time()

#     def get_measures(self):
#         return self._measures
#         
    def test_down(self, url, total_test_time_secs = None, callback_update_speed = None):
        self.callback_update_speed = callback_update_speed
        if total_test_time_secs:
            self.total_measure_time = total_test_time_secs
        else:
            self.total_measure_time = TOTAL_MEASURE_TIME
        file_size = MAX_TRANSFERED_BYTES * self.total_measure_time / TOTAL_MEASURE_TIME
        self._init_counters()
        test = _init_test('download_http')
        read_thread = threading.Timer(1.0, self._read_down_measure)
        read_thread.start()
        self._read_measure_threads.append(read_thread)
        starttotalbytes = self._netstat.get_rx_bytes()
        startbytes = 0
        filebytes = 0
#         starttime = time.time()

        try:
            request = urllib2.Request(url, headers = {"X-requested-file-size" : file_size, "X-requested-measurement-time" : self.total_measure_time})
            response = urllib2.urlopen(request)
        except Exception as e:
            raise MeasurementException("Impossibile aprire la connessione HTTP: %s" % str(e))
        if response.getcode() != 200:
            raise MeasurementException("Impossibile aprire la connessione HTTP, codice di errore ricevuto: %d" % response.getcode())
        
        while not self._time_to_stop:
            my_buffer = response.read(self._num_bytes)
            if my_buffer: 
                filebytes += len(my_buffer)
            else: 
                self._time_to_stop = True
                raise MeasurementException("Non ricevuti dati sufficienti per completare la misura")
                
#         elapsed_time = float((time.time() - starttime) * 1000)
        measured_bytes = filebytes - startbytes
        total_bytes = self._netstat.get_rx_bytes() - starttotalbytes
        for read_thread in self._read_measure_threads:
            read_thread.join()

        if (total_bytes < 0):
            raise MeasurementException("Ottenuto banda negativa, possibile azzeramento dei contatori.")
        spurio = float(total_bytes-measured_bytes)/float(total_bytes)
        logger.info("Traffico spurio: %f" % spurio)

        # "Trucco" per calcolare i bytes corretti da inviare al backend basato sul traffico spurio
        test['bytes_total'] = self._bytes_total #sum(self._measures_tot)#total_bytes
        test['bytes'] = int(round(self._bytes_total * (1 - spurio))) #measured_bytes
        test['time'] = (self._endtime - self._starttime) * 1000.0
        test['rate_max'] = self._get_max_rate() 
        test['rate_tot_secs'] = self._measures_tot

        response.close()
        return test

    def _get_max_rate(self):
        try:
            return max(self._measures_tot)
        except Exception:
            return 0


    def _read_down_measure(self):

        if self._time_to_stop:
            logger.warn("Time to stop, not measuring")
            return
        measuring_time = time.time()
        elapsed = (measuring_time - self._last_measured_time)*1000.0
        
        new_rx_bytes = self._netstat.get_rx_bytes()
        rx_diff = new_rx_bytes - self._last_rx_bytes
        rate_tot = float(rx_diff * 8)/float(elapsed) 
        if self._measure_count >= self._rampup_secs:
            self._bytes_total += rx_diff
            self._measures_tot.append(rate_tot)
        if self.callback_update_speed:
            self.callback_update_speed(second=self._measure_count + 1, speed=rate_tot)

        logger.debug("Reading... count = %d, rx diff= %d, total = %d" 
              % (self._measure_count, rx_diff, new_rx_bytes))
        
        self._measure_count += 1
        if self._measure_count == self._rampup_secs:
            self._starttime = self._last_measured_time
        elif self._measure_count == (10 + self._rampup_secs):
            self._endtime = measuring_time
            self._time_to_stop = True
        
        if not self._time_to_stop:
            self._last_rx_bytes = new_rx_bytes
            self._last_measured_time = measuring_time
            read_thread = threading.Timer(1.0, self._read_down_measure)
            self._read_measure_threads.append(read_thread)
            read_thread.start()
            
    def _stop_down_measure(self):
        self._time_to_stop = True
            
           
    def gen_chunk(self):
        time_to_stop = False
        while not time_to_stop:
            elapsed = time.time() - self._starttime
            if not self._time_to_stop and (elapsed < self._upload_sending_time_secs) and (self._fakefile.get_bytes_read() < MAX_TRANSFERED_BYTES):
                yield self._fakefile.read(BUF_SIZE)
            elif not self._has_stopped:
                self._has_stopped = True
                yield END_STRING * (self._recv_bufsize / len(END_STRING) + 1)
            else:
                time_to_stop = True
                yield ""


        
    '''
    Upload test is done server side. We just measure
    the average speed payload/net in order to 
    verify spurious traffic.
    '''
    def test_up(self, url, file_size = MAX_TRANSFERED_BYTES, recv_bufsize = 8 * 1024):
        self._has_stopped = False
        self._time_to_stop = False
        self._recv_bufsize = recv_bufsize
        self._test = _init_test('upload_http')

        self._fakefile = Fakefile(file_size)
        response = None
        self._starttime = time.time()
        start_tx_bytes = self._netstat.get_tx_bytes()
        try:
            logger.info("Connecting to server, sending time is %d" % self._upload_sending_time_secs)
            response = requests.post(url, data=self.gen_chunk())#, hooks = dict(response = self._response_received))
        except Exception as e:
            raise MeasurementException("Errore di connessione: %s" % str(e))
        if not response:
            self._time_to_stop = True
            raise MeasurementException("Nessuna risposta") 
        if response.status_code != 200:
            self._time_to_stop = True
            raise MeasurementException("Ricevuto risposta %d dal server" % response.status_code)
        self._test = _test_from_server_response(response.content)
        if self._test['time'] < 9999:
            # Probably slow creation of connection, needs more time
            # Double the sending time
            self._upload_sending_time_secs = 2 * self._upload_sending_time_secs
            raise MeasurementException("Test non sufficientemente lungo, aumento del tempo di misura.")
        tx_diff = self._netstat.get_tx_bytes() - start_tx_bytes
        read_bytes = self._fakefile.get_bytes_read()
        spurious = (float(tx_diff - read_bytes)/float(tx_diff))
        self._test['bytes_total'] = int(self._test['bytes'] * (1 + spurious))
        return self._test
    
#     def __len__(self):
#         return 1
#     
def _init_test(testtype):
    test = {}
    test['type'] = testtype
    test['time'] = 0
    test['bytes'] = 0
    test['bytes_total'] = 0
    test['errorcode'] = 0
    return test
        
def _test_from_server_response(response):
    '''
    Server response is a comma separated string containing:
    <test time>, <total total_bytes received>, <total_bytes received last second>, <total_bytes received 9th second>, ... 
    '''
    logger.info("Ricevuto risposta dal server: %s" % str(response))
    test = {}
    test['type'] = 'upload_http'
    if not response or len(response) == 0:
        logger.error("Got empty response from server")
        test['rate_medium'] = -1
        test['rate_max'] = -1
        test['rate_secs'] = -1
        test['errorcode'] = 1
    else:
        results = str(response).split(',')
        test['time'] = int(results[0])
        total_bytes = int(results[1])
        test['bytes'] = total_bytes
        if test['time'] > 0:
            medium_rate = float(total_bytes) * 8 / test['time']
            test['rate_medium'] = medium_rate
        else:
            test['rate_medium'] = -1
        partial_bytes = [float(x) for x in results[2:]] 
        test['rate_secs'] = []
        if partial_bytes:
            bytes_max = max(partial_bytes)
            test['rate_max'] = bytes_max * 8 / 1000 # Bytes in one second
            if test['time'] > 0:
                test['rate_secs'] = [ b * 8 / 1000 for b in partial_bytes ]
        else:
            test['rate_max'] = 0
    return test
        
        
if __name__ == '__main__':
#    host = "10.80.1.1"
#    host = "193.104.137.133"
#    host = "regopptest6.fub.it"
    host = "eagle2.fub.it"
#    host = "rocky.fub.it"
#    host = "billia.fub.it"
    import sysMonitor
    dev = sysMonitor.getDev()
    http_tester = HttpTester(dev)
    print "\n------ DOWNLOAD -------\n"
    res = http_tester.test_down("http://%s" % host)
    print res
#     print "\n------ UPLOAD ---------\n"
#     res = http_tester.test_up("http://%s/file.rnd" % "193.104.137.133")
#     print res
#    res = http_tester.test_up("http://%s/" % host, file_size = MAX_TRANSFERED_BYTES, recv_bufsize = 1024)
