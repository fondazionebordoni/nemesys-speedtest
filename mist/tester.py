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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from host import Host
from logger import logging
from optparse import OptionParser
import ping
from testerhttp import HttpTester
from testerftp import FtpTester
from measurementexception import MeasurementException

HTTP_BUFF = 8*1024

logger = logging.getLogger()


class Tester:

    def __init__(self, dev, ip, host, username = 'anonymous', password = 'anonymous@', timeout = 11):
        
        self._nic_if = dev
        self._if_ip = ip
        self._host = host
        
        self._ftp = None
        self._file = None
        self._filepath = None
        self._maxRetry = 8
        
        self._username = username
        self._password = password
        self._timeout = timeout
        
        self._testerhttp = HttpTester(dev, HTTP_BUFF)
        self._testerftp = FtpTester(dev, timeout, HTTP_BUFF)
        
        

    def testhttpdown(self, callback_update_speed, num_sessions = 7):
        url = "http://%s/file.rnd" % self._host.ip
        return self._testerhttp.test_down(url, 10, callback_update_speed, num_sessions=num_sessions)        
 
    def testhttpup(self, callback_update_speed, num_sessions=1):
        url = "http://%s/file.rnd" % self._host.ip
        return self._testerhttp.test_up(url, callback_update_speed, num_sessions=num_sessions)        
         
    def testftpdown(self, bytes, filename):
        return self._testerftp.testftpdown(self._host.ip, filename, bytes, self._username, self._password)

    def testftpup(self, bytes, filename):
        return self._testerftp.testftpup(self._host.ip, filename, bytes, self._username, self._password)

    def testping(self):
        
        # si utilizza funzione ping.py
        test = {}
        test['type'] = 'ping'
        test['time'] = 0
        test['errorcode'] = 0
        
#         self._timeout = float(22)
        
        try:
            # Il risultato deve essere espresso in millisecondi
            RTT = ping.do_one(self._host.ip, self._timeout) * 1000
            if (RTT != None):
                test['time'] = RTT
        except Exception as e:
            error = 'Impossibile eseguire il ping: %s' % e
            logger.error(error)
            raise Exception(error)

        return test
    
    


def main():
    import time
    #Aggancio opzioni da linea di comando
    
    parser = OptionParser(version = "0.10.1.$Rev$",
                                                description = "A simple bandwidth tester able to perform HTTP upload/download and PING tests.")
    parser.add_option("-t", "--type", choices = ('httpdown', 'httpup', 'ftpup', 'ping'),
                                    dest = "testtype", default = "httpdown", type = "choice",
                                    help = "Choose the type of test to perform: httpdown (default), httpup, ftpup, ping")
    parser.add_option("-b", "--bandwidth", dest = "bandwidth", default = "2M", type = "string",
                                    help = "The expected bandwith to measure, used for file size in FTP upload, e.g. 512k, 2M")
    parser.add_option("--ping-timeout", dest = "ping_timeout", default = "20.0", type = "float",
                                    help = "Ping timeout")
    parser.add_option("--sessions-up", dest = "sessions_up", default = "1", type = "int",
                                    help = "Number of sessions in upload (only HTTP)")
    parser.add_option("--sessions-down", dest = "sessions_down", default = "7", type = "int",
                                    help = "Number of sessions in download")
    parser.add_option("-n", "--num-tests", dest = "num_tests", default = "4", type = "int",
                                    help = "Number of tests to perform")
    parser.add_option("-H", "--host", dest = "host", default = "eagle2.fub.it",
                                    help = "An ipaddress or FQDN of server host")
    
    (options, _) = parser.parse_args()
    #TODO inserire controllo host
    import sysMonitor
#        This is for lab environment
#         ip = sysMonitor.getIp(host=options.host, port=80)
#         dev = sysMonitor.getDev(host=options.host, port=80)
    ip = sysMonitor.getIp()
    dev = sysMonitor.getDev()
    t = Tester(dev, ip, Host(options.host), timeout = float(options.ping_timeout), username = 'nemesys', password = '4gc0m244')
    if options.bandwidth.endswith("M"):
        bw = int(options.bandwidth[:-1]) * 1000000
    elif options.bandwidth.endswith("k"):
        bw = int(options.bandwidth[:-1]) * 1000
    else:
        print "Please specify bandwith in the form of 2M or 512k"
        return

    #     test = None
    print "==============================================="
    print ('Testing: %s' % options.host)
    for i in range(1, options.num_tests + 1):
        print "-----------------------------------------------"
        if i != 1:
            print "Sleeping...."
            print "-----------------------------------------------"
            time.sleep(5)
        print('test %d %s' % (i, options.testtype))
        if options.testtype == 'httpup':
            try:
                    res = t.testhttpup(None, int(options.sessions_up))
            except MeasurementException as e:
                    res = {'errorcode': 1, 'error': str(e)}
            printout_http(res)
        elif options.testtype == 'ftpup':
            file_size = bw * 10 / 8
            try:
                res = t.testftpup(file_size, '/upload/r.raw')
            except MeasurementException as e:
                res = {'errorcode': 1, 'error': str(e)}
            printout_ftp(res)
        elif options.testtype == 'ping':
            try:
                res = t.testping()
                print("Ping: %.2f milliseconds" % res['time'])
            except Exception as e:
#                                 res = {'errorcode': 1, 'error': str(e)}
                print("Error: %s" % str(e))
        else:
            try:
                    res = t.testhttpdown(None, int(options.sessions_down))
            except MeasurementException as e:
                    res = {'errorcode': 1, 'error': str(e)}
            printout_http(res)
    print "==============================================="


def printout_http(res):
    if res['errorcode'] == 0:
            print("Medium speed: %d" % (int(sum(res['rate_tot_secs']))/len(res['rate_tot_secs'])))
#                 print("Spurious traffic: %.2f%%" % float(res['spurious'] * 100))
    else:
            print("Error: %s" % res['error'])
#     tests = {
#         'httpdown': t.testhttpdown(None, options.sessions_down),
#         'httpup': t.testhttpup(None, options.sessions_up),
#         'ping': t.testping(),
#     }
#     test = tests.get(options.testtype)
# 
#     print test
#     return None


def printout_ftp(res):
    if res['errorcode'] == 0:
        speed = float(res['bytes_total'] * 8) / float(res['time'])
        print("Medium speed: %d" % int(speed))
#                 print("Spurious traffic: %.2f%%" % float(res['spurious'] * 100))
    else:
        print("Error: %s" % res['error'])


if __name__ == '__main__':
    main()
