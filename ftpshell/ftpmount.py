from __future__ import print_function
import os
import sys
import socket
from fuse import FUSE
from .ftp import ftp_session
from .ftp.ftp_parser import parse_response_error
from .ftp.ftp_session import login_error
from .ftp.ftp_fuse import FtpFuse
from .ftpshell import proc_input_args
from .ftpshell import cli_error

def main():
	try:
		usage = 'Usage: ftpshell [username[:password]@]server[:port] mountpoint'
		server, port, server_path, username, password, mountpoint = proc_input_args(usage)
		ftp = ftp_session.FtpSession(server, port)
		ftp.login(username, password, server_path)
	except cli_error:
		return
	except login_error:
		print("Login failed.")
	except (socket.error, parse_response_error, ftp_session.network_error):
		ftp.close_server()
		print("Connection was closed by the server.")
	pid = os.fork()
	if not pid:
		# Child process
		print("Running fuse!")
		#sys.stdout = sys.stderr = open(os.devnull, "w")
		mp_created = False
		if not os.path.exists(mountpoint):
			mp_created = True
			os.mkdir(mountpoint)
		mountpoint = os.path.abspath(mountpoint)
		FUSE(FtpFuse(ftp, ftp.get_cwd()), mountpoint, nothreads=True, foreground=True)
		if mp_created:
			os.rmdir(mountpoint)

	# except BaseException as e:
	#    print("Received unpexpected exception '%s'. Closing the session." % e.__class__.__name__)


if __name__ == '__main__':
	main()
