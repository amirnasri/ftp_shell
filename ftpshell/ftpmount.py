from __future__ import print_function
from multiprocessing import Process
import os
import subprocess
import socket
import sys
import threading
from fuse import FUSE
from .ftp import ftp_session
from .ftp.ftp_parser import parse_response_error
from .ftp.ftp_session import login_error
from .ftp.ftp_fuse import FtpFuse
import ftpshell
#from .ftpshell import proc_input_args
#from .ftpshell import cli_error

"""
def run_fuse(ftp, mountpoint):
	# sys.stdout = sys.stderr = open(os.devnull, "w")
	print("fuse before")
	print("-------------%s" % ftp.shared_dict)
	try:
		mp_created = False
		if not os.path.exists(mountpoint):
			os.mkdir(mountpoint)
			mp_created = True
		mountpoint = os.path.abspath(mountpoint)
		# FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)

		FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
	except RuntimeError:
		print("runtoirj*************")
		subprocess.call(["fusermount", "-u", mountpoint], shell=False)
		FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
	finally:
		if mp_created:
			os.rmdir(mountpoint)
"""


def ftp_mount(server, user, mountpoint, base_dir=None, use_thread=False):
	"""Mount an ftp session on a mountpoint

	   Args:
	       ftp (FtpSession): An instance of FtpSession class which
	          already has a connection to an ftp-server.

	       mountpoint (str): Path to the directory whrere the ftp session
	       is to be mounted.

	       base_dir (str): Absolute path of the directory on the ftp server
	          to be mounted. If not provided, defaults to current server
	          directory.
	"""

	if not use_thread:
		#sys.stdout = sys.stderr = open(os.devnull, "w")
		print("fuse before")
		try:
			mp_created = False
			if not os.path.exists(mountpoint):
				os.mkdir(mountpoint)
				mp_created = True
			mountpoint = os.path.abspath(mountpoint)
			server_addr, server_port, server_path = server
			username, password = user

			ftp = None
			ftp = ftp_session.FtpSession(server_addr, server_port, verbose=True)
			try:
				ftp.login(username, password, server_path)
			except login_error:
				print("Login failed.")
			except (socket.error, parse_response_error, ftp_session.network_error):
				ftp.close_server()
				print("Connection was closed by the server.")

			try:
				FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
			except RuntimeError:
				print("runtoirj*************")
				subprocess.call(["fusermount", "-u", mountpoint], shell=False)
				FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
		#except:
		#	pass
		finally:
			if mp_created:
				os.rmdir(mountpoint)
			if ftp:
				ftp.close()
	else:
		#t = FtpMountThread(server, user, mountpoint)
		#t.start()
		#t.join()
		#return t
		#fuse_process = Process(target=ftp_mount, args=(server, user, mountpoint, None, False))
		#fuse_process.start()
		#print("started fuse process, pid=%d" % fuse_process.pid)
		# self.fuse_process = fuse_process
		#return fuse_process
		pid = os.fork()
		if not pid:
			ftp_mount(server, user, mountpoint, use_thread=False)
			sys.exit()

		return pid

	'''
	fuse_process = Process(target=run_fuse, args=(mountpoint,))
	fuse_process.start()
	print("started fuse process, pid=%d" % fuse_process.pid)
	#self.fuse_process = fuse_process
	return fuse_process
	'''
	#if not use_thread:
	#	run_fuse(ftp, mountpoint)

class FtpMountThread(threading.Thread):
	def __init__(self, server, user, mountpoint):
		super(FtpMountThread, self).__init__()
		self.server = server
		self.user = user
		self.mountpoint = mountpoint

	def run(self):
		ftp_mount(self.server, self.user, self.mountpoint, use_thread=False)

"""
def ftp_connect_mount(server, user, mountpoint):
	server_addr, server_port, server_path = server
	username, password = user
	ftp = ftp_session.FtpSession(server_addr, server_port)
	ftp.login(username, password, server_path)
	ftp_mount(ftp, mountpoint)
"""


def main():
	try:
		usage = 'Usage: ftpshell [username[:password]@]server[:port] mountpoint'
		server_addr, server_port, server_path, username, password, mountpoint = ftpshell.proc_input_args(usage)
		server = server_addr, server_port, server_path
		user = username, password
		fuse_process_pid = ftp_mount(server, user, mountpoint, use_thread=True)
	except ftpshell.cli_error:
		return
	#os.kill(fuse_process.pid, signal.SIGINT)
	#fuse_process.join()
	#print("fuse_process joined!")

	#print("Running fuse! %s" % ftp.get_cwd())
	#fuse_process = ftp_mount(ftp, mountpoint)
	#fuse_process.join()

	'''
	pid = os.fork()
	if not pid:
		# Child process
		#print("Running fuse! %s" % ftp.get_cwd())
		#sys.stdout = sys.stderr = open(os.devnull, "w")
		mp_created = False
		if not os.path.exists(mountpoint):
			os.mkdir(mountpoint)
			mp_created = True
		mountpoint = os.path.abspath(mountpoint)
		#FUSE(FtpFuse(ftp, ftp.get_cwd()), mountpoint, nothreads=True, foreground=True)
		if mp_created:
			os.rmdir(mountpoint)
	'''

	# except BaseException as e:
	#    print("Received unpexpected exception '%s'. Closing the session." % e.__class__.__name__)


if __name__ == '__main__':
	main()
