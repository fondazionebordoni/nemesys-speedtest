# httptester.py
# -*- coding: utf-8 -*-

# Copyright (c) 2015-2016 Fondazione Ugo Bordoni.
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

from datetime import datetime
import logging
import random
import socket
import threading
import time

from fakefile import Fakefile
import httpclient
from nem_exceptions import MeasurementException
import nem_exceptions
import netstat
from proof import Proof
import timeNtp

TOTAL_MEASURE_TIME = 10
# Long timeout since needed in some cases
TEST_TIMEOUT = 18
# 1 Gbps for 15 seconds
MAX_TRANSFERED_BYTES = 1000 * 1000000 * 15 / 8

logger = logging.getLogger(__name__)


class HttpTesterUp(object):
    """
    NOTE: not thread-safe, make sure to only call
    one measurement at a time!
    """

    def __init__(self, device, bufsize=8 * 1024):
        self._bufsize = bufsize
        self._netstat = netstat.Netstat(device)
        self.callback_update_speed = None
        self._time_to_stop = False

    def _init_counters(self):
        self._time_to_stop = False
        self._last_tx_bytes = self._netstat.get_tx_bytes()
        self._partial_tx_bytes = 0
        self._measure_count = 0
        self._read_measure_threads = []
        self._last_measured_time = time.time()

    def _read_up_measure(self):
        if not self._time_to_stop:
            self._measure_count += 1
            measuring_time = time.time()
            elapsed = (measuring_time - self._last_measured_time) * 1000.0
            new_tx_bytes = self._netstat.get_tx_bytes()
            tx_diff = new_tx_bytes - self._last_tx_bytes
            if (self._measure_count >= 2) and (self._measure_count < 12):
                self._partial_tx_bytes += tx_diff
            rate_tot = float(tx_diff * 8) / float(elapsed)
            self._last_tx_bytes = new_tx_bytes
            self._last_measured_time = measuring_time

            logger.debug("[HTTP] Reading... count = %d, speed = %d"
                         % (self._measure_count, int(rate_tot)))
            if self.callback_update_speed is not None:
                self.callback_update_speed(second=self._measure_count,
                                           speed=rate_tot)
            read_thread = threading.Timer(1.0, self._read_up_measure)
            self._read_measure_threads.append(read_thread)
            read_thread.start()

    def _stop_up_measurement(self):
        self._time_to_stop = True
        for t in self._read_measure_threads:
            t.join()

    def test_up(self,
                url,
                callback_update_speed=None,
                total_test_time_secs=TOTAL_MEASURE_TIME,
                # recv_bufsize=8 * 1024,
                num_sessions=1,
                tcp_window_size=-1):
        """
        Upload test is done server side. We just measure
        the average speed payload/net in order to
        verify spurious traffic.
        """
        logger.info("HTTP upload, %d sessions, TCP window size = %d"
                    % (num_sessions, tcp_window_size))
        start_timestamp = datetime.fromtimestamp(timeNtp.timestampNtp())
        measurement_id = "sess-%d" % random.randint(0, 100000)
        self.callback_update_speed = callback_update_speed
        upload_threads = []
        self._init_counters()
        # Read progress each second, just for display
        read_thread = threading.Timer(1.0, self._read_up_measure)
        read_thread.start()
        self._read_measure_threads.append(read_thread)
        self._starttime = time.time()
        start_tx_bytes = self._netstat.get_tx_bytes()
        for i in range(0, num_sessions):
            fakefile = Fakefile(MAX_TRANSFERED_BYTES)
            test_timeout = total_test_time_secs + TEST_TIMEOUT
            upload_thread = UploadThread(name='thread-%d' % i,
                                         httptester=self,
                                         fakefile=fakefile,
                                         url=url,
                                         upload_sending_timeout=test_timeout,
                                         measurement_id=measurement_id,
                                         # recv_bufsize=self._bufsize,
                                         bufsize=self._bufsize,
                                         tcp_window_size=tcp_window_size)
            upload_thread.start()
            upload_threads.append(upload_thread)
        thread_error = None
        resp_content = None
        for upload_thread in upload_threads:
            upload_thread.join()
            thread_error = upload_thread.get_error()
            thread_response = upload_thread.get_response()
            if thread_response is not None:
                resp_content = thread_response.content
                thread_response.close()
        self._time_to_stop = True
        if thread_error:
            raise MeasurementException(thread_error)
        (duration, bytes_received) = _test_from_server_response(resp_content)
        if duration < (total_test_time_secs * 1000) - 1:
            raise MeasurementException("Test non risucito - tempo ritornato "
                                       "dal server non corrisponde "
                                       "al tempo richiesto.",
                                       nem_exceptions.SERVER_ERROR)
        bytes_read = 0
        for upload_thread in upload_threads:
            bytes_read += upload_thread.get_bytes_read()
        tx_diff = self._netstat.get_tx_bytes() - start_tx_bytes
        if tx_diff < 0:
            raise MeasurementException("Ottenuto banda negativa, possibile "
                                       "azzeramento dei contatori.",
                                       nem_exceptions.COUNTER_RESET)
        if (bytes_read == 0) or (tx_diff == 0):
            raise MeasurementException("Test non risucito - "
                                       "connessione interrotta",
                                       nem_exceptions.BROKEN_CONNECTION)
        if tx_diff > bytes_read:
            spurious = (float(tx_diff - bytes_read) / float(tx_diff))
        else:
            logger.warn("Bytes read from file > tx_diff, "
                        "alternative calculation of spurious traffic")
            for thread in self._read_measure_threads:
                thread.join()
            spurious = (float(self._partial_tx_bytes - bytes_received) /
                        float(self._partial_tx_bytes))
        logger.info("Traffico spurio: %0.4f" % spurious)
        bytes_total = int(bytes_received * (1 + spurious))
        return Proof(test_type='upload_http',
                     start_time=start_timestamp,
                     duration=duration,
                     bytes_nem=bytes_received,
                     bytes_tot=bytes_total,
                     spurious=spurious)


def _test_from_server_response(response):
    """
    Server response is a comma separated string containing:
    <total_bytes received 10th second>, <total_bytes received 9th second>, ...
    """
    logger.debug("Ricevuto risposta dal server: %s" % str(response))
    if not response or len(response) == 0:
        raise MeasurementException("Nessuna risposta dal server",
                                   nem_exceptions.SERVER_ERROR)
    else:
        try:
            results = map(int, response.strip(']').strip('[').split(', '))
        except:
            raise MeasurementException("Ricevuto risposta errata dal server",
                                       nem_exceptions.SERVER_ERROR)
        testtime = len(results) * 1000
        partial_bytes = [float(x) for x in results]
        bytes_received = int(sum(partial_bytes))
    return testtime, bytes_received


class UploadThread(threading.Thread):
    def __init__(self, name, httptester, fakefile, url, upload_sending_timeout,
                 measurement_id, bufsize, tcp_window_size=None):
        threading.Thread.__init__(self)
        self._httptester = httptester
        self._name = name
        self._fakefile = fakefile
        self._url = url
        self._upload_sending_timeout = upload_sending_timeout
        self._measurement_id = measurement_id
        # self._recv_bufsize = recv_bufsize
        self._bufsize = bufsize
        self._tcp_window_size = tcp_window_size
        self._error = None
        self._response = None

    def run(self):
        chunk_generator = ChunkGenerator(self._fakefile, self._bufsize)
        response = None
        httpc = httpclient.HttpClient()
        try:
            logger.debug("%s Connecting to server %s", self._name, self._url)
            headers = {"X-measurement-id": self._measurement_id}
            response = httpc.post(self._url,
                                  data_source=chunk_generator.gen_chunk(),
                                  headers=headers,
                                  tcp_window_size=self._tcp_window_size,
                                  timeout=self._upload_sending_timeout)
        except Exception as e:
            logger.error("Failed connection to server", exc_info=True)
            self._error = "Errore di connessione: %s" % str(e)
        finally:
            self._httptester._stop_up_measurement()
            chunk_generator.stop()
            if response:
                response.close()
        logger.debug("%s done sending", self._name)
        if response is None:
            if not self._error:
                self._error = "Nessuna risposta dal server"
        elif response.status_code != 200:
            if not self._error:
                self._error = "Errore: %s" % response.status
        self._response = response

    def get_bytes_read(self):
        return self._fakefile.get_bytes_read()

    def get_error(self):
        return self._error

    def get_response(self):
        return self._response


class ChunkGenerator(object):
    def __init__(self, fakefile, num_bytes):
        self._fakefile = fakefile
        self._time_to_stop = False
        self._num_bytes = num_bytes

    def stop(self):
        self._time_to_stop = True

    def gen_chunk(self):
        while not self._time_to_stop:
            yield self._fakefile.read(self._num_bytes)


if __name__ == '__main__':
    import log_conf
    import iptools

    log_conf.init_log()
    socket.setdefaulttimeout(10)
    #    host = "193.104.137.133"
    host = "eagle2.fub.it"
    dev = iptools.get_dev()
    http_tester = HttpTesterUp(dev)
    print "\n------ UPLOAD ---------\n"
    res = http_tester.test_up("http://%s:8080/file.rnd" % host)
    print res
