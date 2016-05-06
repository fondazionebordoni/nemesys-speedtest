# task.py
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

from collections import OrderedDict
import logging

import httputils
from server import Server
import xmlutils


logger = logging.getLogger(__name__)

def download_task(url, certificate, client_id, version, md5conf, timeout, server=None):
    '''Scarica il prossimo task dallo scheduler'''

    try:
        connection = httputils.getverifiedconnection(url=url, certificate=certificate, timeout=timeout)
        if (server != None):
            connection.request('GET', '%s?clientid=%s&version=%s&confid=%s&server=%s' % (url.path, client_id, version, md5conf, server.ip))
        else:
            connection.request('GET', '%s?clientid=%s&version=%s&confid=%s' % (url.path, client_id, version, md5conf))
        
        data = connection.getresponse().read()
        task = xmlutils.xml2task(data)
        
        if (task == None): 
            logger.info('Lo scheduler ha inviato un task vuoto.')
        else:
            logger.info("--------[ TASK ]--------")
            for key, val in task.dict.items():
                logger.info("%s : %s" % (key, val))
            logger.info("------------------------")
            
    except Exception as e:
        logger.error('Impossibile scaricare lo scheduling. Errore: %s.' % e, exc_info=True)
        return None
    
    return task


class Task:

    def __init__(self, task_id, start, server, ping=4, nicmp=1, delay=1, now=False, message=None, http_download=4, http_upload=4):
        
        self._id = task_id
        self._start = start
        self._server = server
        self._ftpup_bytes = 0
        self._http_upload = http_upload
        self._http_download = http_download
        self._ping = ping
        self._nicmp = nicmp
        self._delay = delay
        self._now = now
        self._message = message

    @property
    def id(self):
        return self._id

    @property
    def start(self):
        return self._start

    @property
    def server(self):
        return self._server

    @property
    def http_download(self):
        return self._http_download

    @property
    def http_upload(self):
        return self._http_upload

    @property
    def ping(self):
        return self._ping

    @property
    def nicmp(self):
        return self._nicmp

    @property
    def delay(self):
        return self._delay

    @property
    def now(self):
        return self._now

    @property
    def message(self):
        return self._message

    @property
    def ftpup_bytes(self):
        return self._ftpup_bytes

    def set_ftpup_bytes(self, num_bytes):
        self._ftpup_bytes = num_bytes

    @property
    def dict(self):
        task = OrderedDict \
        ([ \
        ('Task id',self.id),\
        ('Start time',self.start),\
        ('Server id',self.server.id),\
        ('Server name',self.server.name),\
        ('Server ip',self.server.ip),\
        ('Server location',self.server.location),\
        ('Ping number',self.ping),\
        ('Ping repeat',self.nicmp),\
        ('Ping delay',self.delay),\
        ('Download HTTP number',self.http_download),\
        ('Upload HTTP number',self.http_upload),\
        ('Now parameter',self.now),\
        ('Message',self.message) \
        ])
        return task 
            
    def __str__(self):
        return 'id: %s; start: %s; serverip: %s; ping %d; ncimp: %d; delay: %d; now %d; message: %s; http_download: %d; http_upload: %d' % \
            (self.id, self.start, self.server.ip, self.ping, self.nicmp, self.delay, self.now, self.message, self.http_download, self.http_upload)

if __name__ == '__main__':
    import log_conf
    log_conf.init_log()
    s = Server('s1', '127.0.0.1')
    p = Task(0, '2010-01-01 10:01:00', s, 'r.raw', 'upload/r.raw')
    print p
