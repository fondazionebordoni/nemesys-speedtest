# test_task.py
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Fondazione Ugo Bordoni.
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
import unittest

from mist import task

empty_xml = ''
fake_xml = 'pippo'
generic_xml = '''<?xml version="1.0" encoding="UTF-8"?>
   <measure>
       <content/>
   </measure>
   '''
task_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<calendar>
   <task>
    <id>1</id>
    <nftpup mult="10">20</nftpup>
    <nftpdown>20</nftpdown>
    <nping icmp="1" delay="10">10</nping>
    <start now="1">2010-01-01 00:01:00</start>
    <srvid>fubsrvrmnmx03</srvid>
    <srvip>193.104.137.133</srvip>
    <srvname>NAMEX</srvname>
    <srvlocation>Roma</srvlocation>
    <ftpuppath>/upload/1.rnd</ftpuppath>
    <ftpdownpath>/download/8000.rnd</ftpdownpath>
   </task>
</calendar>
   '''


class TaskTests(unittest.TestCase):
    @staticmethod
    def test_not_task():
        try:
            t = task.xml2task(generic_xml)
            assert t is None
        except task.TaskException:
            assert True

    @staticmethod
    def test_task_happycase():
        t = task.xml2task(task_xml)
        assert t is not None
        assert t.id == "1"
        assert str(t.start) == "2010-01-01 00:01:00"
        # TODO check more fields


def main():
    unittest.main()


if __name__ == '__main__':
    from mist import log_conf
    log_conf.init_log()
    main()

