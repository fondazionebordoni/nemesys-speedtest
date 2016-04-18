# httptester.py
# -*- coding: utf8 -*-

# Copyright (c) 2015 Fondazione Ugo Bordoni.
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

import logging
import random
import socket
import threading
import time

from fakefile import Fakefile
import httpclient
from measurementexception import MeasurementException
import netstat


TOTAL_MEASURE_TIME = 10
MAX_TRANSFERED_BYTES = 100 * 1000000 * 15 / 8 # 100 Mbps for 15 seconds
END_STRING = '_ThisIsTheEnd_'

logger = logging.getLogger(__name__)

'''
NOTE: not thread-safe, make sure to only call 
one measurement at a time!
'''

class HttpTesterUp:

    def __init__(self, dev, bufsize = 8 * 1024, rampup_secs = 2):
        self._num_bytes = bufsize
        self._rampup_secs = rampup_secs
        self._netstat = netstat.get_netstat(dev)
        self._fakefile = None
    
    def _init_counters(self):
        self._time_to_stop = False
        self._last_tx_bytes = self._netstat.get_tx_bytes()
        self._measure_count = 0
        self._read_measure_threads = []
        self._last_measured_time = time.time()


    def _read_up_measure(self):
        if not self._time_to_stop:
            self._measure_count += 1
            measuring_time = time.time()
            elapsed = (measuring_time - self._last_measured_time)*1000.0
            
            new_tx_bytes = self._netstat.get_tx_bytes()
            tx_diff = new_tx_bytes - self._last_tx_bytes
            rate_tot = float(tx_diff * 8)/float(elapsed) 
            logger.debug("[HTTP] Reading... count = %d, speed = %d" 
                  % (self._measure_count, int(rate_tot)))
            if self.callback_update_speed:
                self.callback_update_speed(second=self._measure_count, speed=rate_tot)
        
            self._last_tx_bytes = new_tx_bytes
            self._last_measured_time = measuring_time
            read_thread = threading.Timer(1.0, self._read_up_measure)
            self._read_measure_threads.append(read_thread)
            read_thread.start()


    def _stop_up_measurement(self):
        self._time_to_stop = True
        for t in self._read_measure_threads:
            t.join()

   
    '''
    Upload test is done server side. We just measure
    the average speed payload/net in order to 
    verify spurious traffic.
    '''
    def test_up(self, 
                url, 
                callback_update_speed = None, 
                total_test_time_secs = TOTAL_MEASURE_TIME, 
#                 file_size = MAX_TRANSFERED_BYTES, 
                recv_bufsize = 8 * 1024, 
#                 is_first_try = True, 
                num_sessions = 1,
                tcp_window_size = -1):
        
        logger.info("HTTP upload, %d sessions, TCP window size = %d" % (num_sessions, tcp_window_size))
        measurement_id = "sess-%d" % random.randint(0, 100000)
        self.callback_update_speed = callback_update_speed
        upload_threads = []
        'TODO: not needed?'
        self._upload_sending_timeout = total_test_time_secs * 2 + self._rampup_secs + 1
        self._init_counters()
        # Read progress each second, just for display
        read_thread = threading.Timer(1.0, self._read_up_measure)
        read_thread.start()
        self._read_measure_threads.append(read_thread)
        self._starttime = time.time()
        start_tx_bytes = self._netstat.get_tx_bytes()
        for _ in range(0, num_sessions):
            upload_thread = UploadThread(httptester = self, 
                                         fakefile = Fakefile(MAX_TRANSFERED_BYTES), 
                                         url=url, 
                                         upload_sending_timeout = self._upload_sending_timeout, #TODO not needed?
                                         measurement_id=measurement_id, 
                                         recv_bufsize=recv_bufsize, 
                                         num_bytes=self._num_bytes,
                                         tcp_window_size = tcp_window_size)
            upload_thread.start()
            upload_threads.append(upload_thread)
        for upload_thread in upload_threads:
            upload_thread.join()
            thread_error = upload_thread.get_error()
            thread_response = upload_thread.get_response()
            if thread_response != None:
                response_content = thread_response.content
                thread_response.close()
        self._time_to_stop = True
        if thread_error:
            raise MeasurementException(thread_error)
        test = _test_from_server_response(response_content)
        
        if test['time'] < (total_test_time_secs * 1000) - 1:
            raise MeasurementException("Test non risucito - tempo ritornato dal server non corrisponde al tempo richiesto.")
        bytes_read = 0
        for upload_thread in upload_threads:
            bytes_read += upload_thread.get_bytes_read()
        tx_diff = self._netstat.get_tx_bytes() - start_tx_bytes
        if (tx_diff < 0):
            raise MeasurementException("Ottenuto banda negativa, possibile azzeramento dei contatori.")
        if (bytes_read == 0) or (tx_diff == 0):
            raise MeasurementException("Test non risucito - connessione interrotta")
        spurious = (float(tx_diff - bytes_read)/float(tx_diff))
        logger.info("Traffico spurio: %0.4f" % spurious)
        test['bytes_total'] = int(test['bytes'] * (1 + spurious))
        test['rate_tot_secs'] = [x * (1 + spurious) for x in test['rate_secs']]
        test['spurious'] = spurious
        return test
    

def _test_from_server_response(response):
    '''
    Server response is a comma separated string containing:
    <total_bytes received 10th second>, <total_bytes received 9th second>, ... 
    '''
    logger.info("Ricevuto risposta dal server: %s" % str(response))
    test = {}
    test['type'] = 'upload_http'
    if not response or len(response) == 0:
        logger.error("Got empty response from server")
        test['rate_medium'] = -1
        test['rate_max'] = -1
        test['rate_secs'] = -1
    else:
        try:
            results = map(int, response.strip(']').strip('[').split(', '))
        except:
            raise MeasurementException("Ricevuto risposta errata dal server")
        test['time'] = len(results) * 1000
        partial_bytes = [float(x) for x in results] 
        test['rate_secs'] = []
        if partial_bytes:
            bytes_max = max(partial_bytes)
            test['rate_max'] = bytes_max * 8 / 1000 # Bytes in one second
            if test['time'] > 0:
                test['rate_secs'] = [ b * 8 / 1000 for b in partial_bytes ]
        else:
            test['rate_max'] = 0
        test['bytes'] = sum(partial_bytes)
    return test

class UploadThread(threading.Thread):
    
    def __init__(self, httptester, fakefile, url, upload_sending_timeout, measurement_id, recv_bufsize, num_bytes, tcp_window_size = None):
        threading.Thread.__init__(self)
        self._httptester = httptester
        self._fakefile = fakefile
        self._url = url
        self._upload_sending_timeout = upload_sending_timeout
        self._measurement_id = measurement_id
        self._recv_bufsize = recv_bufsize
        self._num_bytes = num_bytes
        self._tcp_window_size = tcp_window_size
        self._error = None
        self._response = None

    def run(self):
        chunk_generator = ChunkGenerator(self._fakefile, self._num_bytes)
        response = None
        my_http_client = httpclient.HttpClient()
        try:
            logger.info("Connecting to server, sending time is %d" % self._upload_sending_timeout)
            headers = {"X-measurement-id" : self._measurement_id}
            response = my_http_client.post(self._url, 
                                           data_source=chunk_generator.gen_chunk(), 
                                           headers = headers, 
                                           tcp_window_size = self._tcp_window_size, 
                                           timeout = self._upload_sending_timeout)
        except Exception as e:
            logger.error("Failed connection to server", exc_info=True)
            self._error = "Errore di connessione: %s" % str(e)
        finally:
            self._httptester._stop_up_measurement()
            chunk_generator.stop()
            if response:
                try:
                    response.close()
                except:
                    pass
        if response == None:
            if not self._error:
                self._error = "Nessuna risposta dal server" 
        elif response.status_code != 200:
            if not self._error:
                self._error = "Ricevuto risposta %d dal server" % response.status_code
        self._response = response

    def get_bytes_read(self):
        return self._fakefile.get_bytes_read()
    
    def get_error(self):
        return self._error
    
    def get_response(self):
        return self._response



class ChunkGenerator:

    def __init__(self, fakefile, num_bytes):
        self._fakefile = fakefile
        self._time_to_stop = False
        self._num_bytes = num_bytes
    
    def stop(self):
        self._time_to_stop = True
    
    def gen_chunk(self):
        while not self._time_to_stop:
            yield self._fakefile.read(self._num_bytes)
        yield ""

        
if __name__ == '__main__':
    import log_conf
    log_conf.init_log()
    socket.setdefaulttimeout(10)
#    host = "10.80.1.1"
#    host = "193.104.137.133"
#    host = "regopptest6.fub.it"
    host = "eagle2.fub.it"
#     host = "rambo.fub.it"
#     host = "regoppwebtest.fub.it"
#    host = "rocky.fub.it"
#    host = "billia.fub.it"
    import iptools
    dev = iptools.get_dev()
    http_tester = HttpTesterUp(dev)
#     print "\n------ DOWNLOAD -------\n"
#     for _ in range(0, 10):
#         res = http_tester.test_down("http://%s:80" % host, num_sessions=7)
#         print res
    print "\n------ UPLOAD ---------\n"
    res = http_tester.test_up("http://%s:8080/file.rnd" % host)#, num_sessions=1, tcp_window_size=8192)
    print res
#     print "\n------ UPLOAD ---------\n"
#     res = http_tester.test_up("http://%s:80/file.rnd" % host, num_sessions=2)
#     print res
#     print "\n------ UPLOAD ---------\n"
#     res = http_tester.test_up("http://%s:80/file.rnd" % host, num_sessions=3)
#     print res
#     print "\n------ UPLOAD ---------\n"
#     res = http_tester.test_up("http://%s:80/file.rnd" % host, num_sessions=4)
#     print res
#     print "\n------ UPLOAD ---------\n"
#     res = http_tester.test_up("http://%s:80/file.rnd" % host, num_sessions=5)
#     print res
