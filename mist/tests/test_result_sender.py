# test_result_sender.py
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

from mist import result_sender

xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
    <response>
    <message>Dati salvati su database</message>
    <code>0</code>
    </response>'''

generic_xml = '''<?xml version="1.0" encoding="UTF-8"?>
   <measure>
       <content/>
   </measure>
   '''

not_xml = '''pippo'''


class ResultSenderTests(unittest.TestCase):
    @staticmethod
    def test_happycase():
        code, message = result_sender.parse_response(xml_response)
        assert code == 0
        assert message == 'Dati salvati su database'

    @staticmethod
    def test_not_response():
        code, message = result_sender.parse_response(generic_xml)
        assert code == 99
        assert message == ''

    @staticmethod
    def test_not_xml():
        code, message = result_sender.parse_response(not_xml)
        assert code == 99
        assert message == ''


def main():
    unittest.main()


if __name__ == '__main__':
    from mist import log_conf
    log_conf.init_log()
    main()
