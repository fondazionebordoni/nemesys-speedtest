# timeNtp.py
# -*- coding: utf-8 -*-

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

import ntplib
import time
import ping

SERVERNTP = ["ntp.spadhausen.com","ntp.fub.it","time.windows.com","0.pool.ntp.org","1.pool.ntp.org","2.pool.ntp.org","3.pool.ntp.org"]


def _timestamp(server):
    TimeRX = ntplib.NTPClient().request(server, version=3)
    return TimeRX.tx_time
    
def _ping(server):
    delay = ping.do_one("%s" % server, 1) * 1000
    return delay
    
def timestampNtp():
    local = True
    for server in SERVERNTP:
        timestamp = None
        try:
            delay = _ping(server)
            if (delay is not None):
                timestamp = _timestamp(server)
                if (timestamp is not None):
                    local = False
                    break
        except Exception:
            pass
    if local:
        timestamp = time.time()
    return timestamp

if __name__ == '__main__':
    request_num = 8
    for x in range(request_num):
        print timestampNtp()
