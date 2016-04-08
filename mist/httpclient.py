# httpclient.py 
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

"""
Minimal httpclient so that we can set 
TCP window size
"""

import socket
import urlparse
from optparse import OptionParser
import logging

logger = logging.getLogger(__name__)

class HttpException(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)
        self._message = message.decode('utf-8')

    @property
    def message(self):
        return self._message



def post(url, headers = None, tcp_window_size = None, data_source = None):
    url_res = urlparse.urlparse(url)
    server = url_res.hostname
    port = url_res.port
    if not port:
        port = 80
    
    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    if tcp_window_size != None and tcp_window_size > 0:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, tcp_window_size)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, tcp_window_size)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        s.connect((server, port))
    except:
        raise HttpException("Impossibile connettersi al server %s sulla porta %d" % (server, port))
    post_request = "POST /misurainternet.txt HTTP/1.0\r\n"
    if tcp_window_size != None and tcp_window_size > 0:
        post_request = "%s%s:%s\r\n" % (post_request, "X-Tcp-Window-Size", tcp_window_size)
    for header in headers.items():
        post_request = "%s%s:%s\r\n" % (post_request, header[0], header[1])
    post_request = "%s\r\n" % post_request
    
    s.send(post_request)
    bytes_sent = 0
    if data_source != None:
        for data_chunk in data_source:
            if data_chunk == None or data_chunk == "":
                try:
                    s.send("0\r\n")
                    s.send("\r\n")
                except:
                    pass
                break
            try:
                chunk_size = len(data_chunk)
                bytes_sent += s.send("%s\r\n" % hex(chunk_size)[2:])
                bytes_sent += s.send("%s\r\n" % data_chunk)
            except:
                break
    logger.debug("sent %d bytes" % bytes_sent)
    return HttpResponse(s)

class HttpResponse(object):
    '''Read from socket and parse
    
    HTTP/1.1 200 OK
    Content-Type: text/plain;charset=ISO-8859-1
    Content-Length: 81
    Server: Jetty(8.1.16.v20140903)
    
    [11758564,11691628,11771232,11656120,11534992,11603564,11724892,11764052,11781776]
    '''
    def __init__(self, recv_socket):
        self.recv_socket = recv_socket
        done = False
        all_data = ""
        while not done:
            data = None
            try:
                data = self.recv_socket.recv(1)
                if not data:
                    break
            except:
                break
            all_data = "%s%s" % (all_data, data)
        if all_data and '\n' in all_data:
            lines = all_data.split('\n')
            try:
                response = lines[0].strip("HTTP/1.1").strip()
                self._response_code = int(response.split()[0])
                self._response_cause = response.split()[1]
            except:
                self._response_code = 999
                self._response_cause = "Non-HTTP response received"
            i = 1
            # Find an empty line, the content is what comes after
            self._content = ""
            while i < len(lines):
                if lines[i].strip() == "":
                    self._content = lines[i + 1:][0]
                    break
                i += 1
        else:
            self._response_code = 999
            self._response_cause = "No data received from server"
            self._content = ""
        try:
            recv_socket.close()
        except:
            pass


    @property
    def status_code(self):
        return self._response_code
    
    @property
    def content(self):
        return self._content

    def close(self):
        try:
            self.recv_socket.close()
        except:
            pass

def _do_one_upload(window_size):
    from fakefile import Fakefile
    my_file = Fakefile(100 * 1000000 * 13 / 8)
    from testerhttp import ChunkGenerator
    chunk_generator = ChunkGenerator(my_file, 13, 1025, 8 * 1024)
    import random
    measurement_id = "sess-%d" % random.randint(0, 100000)
    headers = {"X-requested-measurement-time" : "12",
                "X-measurement-id" : measurement_id,
                "Transfer-Encoding": "chunked"}
#           "Accept": "*/*"}
    response = post("http://rambo.fub.it:8080", data_source=chunk_generator.gen_chunk(), headers=headers, tcp_window_size = window_size)
    print "Response content: ", response.content
    int_array = map(int, response.content.strip(']').strip('[').split(', '))
    medium_rate = 8.0 * sum(int_array)/len(int_array)
    print "medium rate: %.2f" % medium_rate
    response.close()

def main():
    import threading
    parser = OptionParser(version = "0.10.1.$Rev$",
                          description = "A simple HTTP client to perform HTTP upload tests.")
    parser.add_option("-s", "--sessions", dest = "sessions_up", default = "1", type = "int",
                    help = "Number of sessions in upload")
    parser.add_option("-w", "--window-size", dest = "window_size", default = "-1", type = "int",
                    help = "Window size in bytes")
    (options, _) = parser.parse_args()
    for _ in range(0, options.sessions_up):
        threading.Thread(target=_do_one_upload, args = (options.window_size,)).start()


if __name__ == '__main__':
    import log_conf
    log_conf.init_log()
    main()
