import os

from mist import xmlutils
import unittest

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
MEASURE_XML_FILE = os.path.join(os.path.dirname(__file__), 'resources/measure_xml_file.xml')

class XmlUtilsTests(unittest.TestCase):
    @staticmethod
    def test_empty_xml():
        try:
            xmlutils.getxml(empty_xml)
        except Exception as e:
            assert str(e) == "Ricevuto un messaggio vuoto"

    @staticmethod
    def test_not_xml():
        try:
            xmlutils.getxml(fake_xml)
        except Exception as e:
            assert str(e) == "Errore di formattazione del messaggio"

    @staticmethod
    def test_not_task():
        print '(getxml) XML legittimo: %s' % generic_xml
        xml = xmlutils.getxml(generic_xml)
        assert xml is not None

    '''XML to task'''

    @staticmethod
    def test_not_task():
        task = xmlutils.xml2task(generic_xml)
        assert task is None

    @staticmethod
    def test_task_happycase():
        task = xmlutils.xml2task(task_xml)
        assert task.id == "1"
        print task.start
        assert str(task.start) == "2010-01-01 00:01:00"
        # TODO check more fields

    @staticmethod
    def test_getstarttime_from_file():
        starttime = xmlutils.getstarttime(MEASURE_XML_FILE)
        assert str(starttime) == "2011-06-09 11:32:34"


def main():
    unittest.main()


if __name__ == '__main__':
    from mist import log_conf
    log_conf.init_log()
    main()



