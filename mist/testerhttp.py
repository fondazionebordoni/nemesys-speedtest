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

import urllib2
import threading
import datetime
from logger import logging
from errorcoder import Errorcoder
#import paths


THRESHOLD_START=0.1
logger = logging.getLogger()
#errors = Errorcoder(paths.CONF_ERRORS)
errors = Errorcoder("../config/errorcodes.conf")

''' 
NOTE: not thread-safe, make sure to only call 
one measurement at a time!
'''

class HttpTester:

    #TODO: 
    def __init__(self, dev, ip, host, timeout = 11, num_bytes = 5*1024):
    
        self._maxRetry = 8
        
        self._timeout = timeout
        self._num_bytes = num_bytes
        
        self._time_to_stop = False
        self._bytes_read = 0
        self._last_bytes_read = 0
        self._last_diff = 0
        self._measures = []
        self._measure_count = 0
        self._go_ahead = False
        
    def test_down(self, url):
        self._http_server = url
        
        test = {}
        test['type'] = 'download'
        test['protocol'] = 'http'
        test['time'] = 0
        test['bytes'] = 0
        test['stats'] = {}
        test['errorcode'] = 0

        bit_per_second = -1

        try:
            response = urllib2.urlopen(url)
        except Exception as e:
            test['errorcode'] = errors.geterrorcode(e)
            error = '[%s] Impossibile aprire la connessione HTTP: %s' % (test['errorcode'], e)
            logger.error(error)
            return test
        
        #TODO: max retry?
        if response.getcode() != 200:
            test['errorcode'] = errors.geterrorcode(response.getcode())
            error = '[%s] Ricevuto errore HTTP: %s' % (response.getcode())
            logger.error(error)
            return test
        
        # TODO: use requests lib instead?
        t = threading.Timer(1.0, self._read_measure)
        t.start()
        has_more = True
        
        while not self._go_ahead and has_more and not self._time_to_stop:
            buffer = response.read(self._num_bytes)
            if buffer: 
                self._bytes_read += len(buffer)
            else: 
                has_more = False
        if self._go_ahead:
            logger.debug("Starting HTTP measurement....")
            start_time = datetime.datetime.now()
            start_bytes_read = self._bytes_read
            t = threading.Timer(10, self._stop_measurement)
            t.start()
            while has_more and not self._time_to_stop:
                buffer = response.read(self._num_bytes)
                if buffer: 
                    self._bytes_read += len(buffer)
                else: 
                    has_more = False
            # TODO: abort the connection Not needed?
            if self._time_to_stop:
                end_time = datetime.datetime.now()
                elapsed_time = end_time - start_time
                elapsed_time_seconds = elapsed_time.seconds + elapsed_time.microseconds/1000000.0
                measured_bytes = self._bytes_read - start_bytes_read
                bit_per_second = measured_bytes * 8.0 / elapsed_time_seconds
                test['bytes'] = measured_bytes
                test['time'] = elapsed_time_seconds
                test['rate'] = bit_per_second
                logger.info("Banda: (%s*8)/%s = %s Kbps" % (measured_bytes,elapsed_time_seconds,bit_per_second))
            else:
                test['errorcode'] = errors.geterrorcode("File non sufficientemente grande per la misura")
        else:
            test['errorcode'] = errors.geterrorcode("Bitrate non stabilizzata")
        return test
        

    def _stop_measurement(self):
        self._read_measure()
        logger.debug("Stopping....")
        self._time_to_stop = True
    
    def _read_measure(self):
        new_bytes_read = self._bytes_read
        # TODO add to array of measurements
        diff = new_bytes_read - self._last_bytes_read
        logger.debug("reading count = %d, diff is %d" % (self._measure_count,diff))

        if (not self._go_ahead) and (self._last_bytes_read != 0):
            acc = (diff - self._last_diff)/self._last_diff
            if acc < THRESHOLD_START:
                self._go_ahead = True
        #else:
        self._last_diff = diff
        self._measures.append((self._measure_count, diff))
        self._measure_count += 1
        self._last_bytes_read = new_bytes_read
        if not self._time_to_stop:
            t = threading.Timer(1.0, self._read_measure)
            t.start()

        
    # TODO: also read spurious traffic!

if __name__ == '__main__':
    t = HttpTester("eth0", "192.168.112.24", "pippo")
    print t.test_down("http://regopptest6.fub.it")