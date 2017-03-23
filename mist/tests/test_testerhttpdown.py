# test_testerhttpdown.py
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.import Queue
import Queue
import threading
import unittest
from threading import Event

import mock

from mist import nem_exceptions
from mist.testerhttpdown import Downloader


class Data(object):
    def __init__(self, last_message='_ThisIsTheEnd_'):
        self.stop = False
        self.last_message = last_message

    def stop_data(self):
        self.stop = True

    def __iter__(self):
        while not self.stop:
            yield 'pippo'
        yield self.last_message


class HttpDownTests(unittest.TestCase):
    @mock.patch('mist.testerhttpdown.urllib2.urlopen')
    def test_one_download_ok(self, mock_urlopen):
        a = mock.Mock()
        a.getcode.side_effect = [200]
        data = Data()
        a.read.side_effect = data
        mock_urlopen.return_value = a
        result_queue = Queue.Queue()
        t = Downloader("fakeurl", Event(), result_queue, "fake_id")
        stop_timer = threading.Timer(2, data.stop_data)
        stop_timer.start()
        t.start()
        t.join(20)

        try:
            res = result_queue.get(block=False)
        except Queue.Empty:
            assert True is False
        assert res.n_bytes is not None
        assert res.error is None
        assert res.received_end is True

    @mock.patch('mist.testerhttpdown.urllib2.urlopen')
    def test_one_download_not_enough(self, mock_urlopen):
        a = mock.Mock()
        a.getcode.side_effect = [200]
        data = Data(last_message=None)
        a.read.side_effect = data
        mock_urlopen.return_value = a
        result_queue = Queue.Queue()
        t = Downloader("fakeurl", Event(), result_queue, "fake_id")
        stop_timer = threading.Timer(2, data.stop_data)
        stop_timer.start()
        t.start()
        t.join(20)

        try:
            res = result_queue.get(block=False)
        except Queue.Empty:
            assert True is False
        assert res.n_bytes is not None
        assert res.error['message'] == 'Non ricevuti dati sufficienti per completare la misura'
        assert res.error['code'] == nem_exceptions.SERVER_ERROR
        assert res.received_end is False

    @mock.patch('mist.testerhttpdown.urllib2.urlopen')
    def test_one_download_404(self, mock_urlopen):
        """Server answers with 404"""
        a = mock.Mock()
        a.getcode.side_effect = [404]
        data = Data(last_message=None)
        a.read.side_effect = data
        mock_urlopen.return_value = a
        result_queue = Queue.Queue()
        t = Downloader("fakeurl", Event(), result_queue, "fake_id")
        t.start()
        t.join(1)

        try:
            res = result_queue.get(block=False)
        except Queue.Empty:
            assert True is False
        assert res.n_bytes == 0
        assert 'Connessione HTTP fallita' in res.error['message']
        assert res.error['code'] == nem_exceptions.CONNECTION_FAILED
        assert res.received_end is False


if __name__ == '__main__':
    import mist.log_conf

    mist.log_conf.init_log()

    unittest.main()
