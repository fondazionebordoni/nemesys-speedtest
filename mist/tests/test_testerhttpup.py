# test_testerhttpup.py
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.import unittest
import unittest

from mist import testerhttpup


class ServerResponseTest(unittest.TestCase):
    @staticmethod
    def test_server_response():
        res = '[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]'
        l = testerhttpup.test_from_server_response(res)
        assert l

if __name__ == '__main__':
    import mist.log_conf

    mist.log_conf.init_log()

    unittest.main()
