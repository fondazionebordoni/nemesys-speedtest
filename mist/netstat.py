'''
Created on 13/nov/2013

@author: ewedlund
'''

import platform


LINUX_RESOURCE_PATH="/sys/class/net"


def get_netstat(if_device):
	platform_name = platform.system().lower()
	print "returning netstat for platform ", platform_name
	if "win" in platform_name:
		return NetstatWindows(if_device)
	elif "linux" in platform_name:
		return NetstatLinux(if_device)
	elif "darwin" in platform_name:
		return NetstatDarwin(if_device)

'''
Eccezione istanzazione Risorsa
'''
class NetstatException(Exception):

	def __init__(self, message):
		Exception.__init__(self, message)


class Netstat(object):

	def __init__(self, if_device=None):
		self.if_device = if_device

	def get_if_device(self):
		return self.if_device

class NetstatWindows(Netstat):
	'''
    Netstat funcions on Linux platforms
    '''

	def _get_entry(self, entry_name):
		whereCondition = " WHERE Name Like \"%" + self.if_device + "%\""
		result = _execute_query("Win32_PerfRawData_Tcpip_NetworkInterface", whereCondition, entry_name)
		if (result):
			try:
				for obj in result:
					entry_value = _getSingleInfo(obj, entry_name)
			except:
				raise NetstatException("Could not get " + entry_name + " from result")
		else:
			raise NetstatException("Query for " + entry_name + " returned empty result")
		return entry_value


	def get_rx_bytes(self):
		return self._get_entry("BytesReceivedPerSec")

	def get_tx_bytes(self):
		return self._get_entry("BytesSentPerSec")

	def get_timestamp(self):
		timestamp = float(self._get_entry("Timestamp_Perftime"))
		frequency = float(self._get_entry("Frequency_Perftime"))
		return timestamp/frequency

class NetstatLinux(Netstat):
	'''
    Netstat funcions on Linux platforms
    '''

	def __init__(self, if_device):
		# TODO Check if interface exists
		super(NetstatLinux, self).__init__(if_device)
		self.rx_bytes_file=LINUX_RESOURCE_PATH + "/"  + if_device + "/statistics/rx_bytes"
		self.tx_bytes_file=LINUX_RESOURCE_PATH + "/"  + if_device + "/statistics/tx_bytes"

	def get_rx_bytes(self):
		return _read_number_from_file(self.rx_bytes_file)

	def get_tx_bytes(self):
		return _read_number_from_file(self.tx_bytes_file)



class NetstatDarwin(object):
	'''
    Netstat funcions on MacOS platforms
    '''

def _read_number_from_file(filename):
	with open(filename) as f:
		return int(f.readline())

def _execute_query(wmi_class, whereCondition="", param="*"):
	try:
		import win32com.client
	except ImportError:
		raise NetstatException("Missing WMI library")
	try:
		objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator")
		objSWbemServices = objWMIService.ConnectServer(".", "root\cimv2")
		colItems = objSWbemServices.ExecQuery("SELECT " + param + " FROM " + wmi_class + whereCondition)
	except:
		raise NetstatException("Errore nella query al server root\cimv2")
	return colItems

def _getSingleInfo(obj, attr):
	val = obj.__getattr__(attr)
	if val != None:
		return val
	else:
		return None


if __name__ == '__main__':
	import time
# 	my_netstat = get_netstat("eth0")
#TODO: get if name
	my_netstat = get_netstat("eth0")
# 	ifdev = my_netstat.get_if_device()
# 	print ifdev
#    timestamp,frequency =
# 	timestamp1 = my_netstat.get_timestamp()
# 	print "Time1, frequency: %f" % (timestamp1)
# 	time.sleep(5)
# 	timestamp2 = my_netstat.get_timestamp()
# 	print "Time2, frequency: %f" % (timestamp2)
	#time_passed = (timestamp2-timestamp2)/frequency
# 	print "Time passed: %f" % (timestamp2 - timestamp1)
# 	print "Timestamp", my_netstat.get_timestamp()
	print "RX bytes", my_netstat.get_rx_bytes()
	print "TX bytes", my_netstat.get_tx_bytes()