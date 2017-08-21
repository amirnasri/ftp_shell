from __future__ import print_function
import argparse
from fuse import FUSE
import logging
import os
import socket
import subprocess
import sys
import threading
from .ftp import ftp_session
from .ftp.ftp_parser import parse_response_error
from .ftp.ftp_session import login_error
from .ftp.ftp_fuse import FtpFuse

"""
def run_fuse(ftp, mountpoint):
	# sys.stdout = sys.stderr = open(os.devnull, "w")
	print("fuse before")
	try:
		mp_created = False
		if not os.path.exists(mountpoint):
			os.mkdir(mountpoint)
			mp_created = True
		mountpoint = os.path.abspath(mountpoint)
		# FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)

		FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
	except RuntimeError:
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
		ftp = None
		mp_created = False
		try:
			if not os.path.exists(mountpoint):
				os.mkdir(mountpoint)
				mp_created = True
			mountpoint = os.path.abspath(mountpoint)
			server_addr, server_port, server_path = server
			username, password = user

			ftp = ftp_session.FtpSession(server_addr, server_port, verbose=False)
			try:
				ftp.login(username, password, server_path)
			except login_error:
				logging.error("Login failed.")
			except (socket.error, parse_response_error, ftp_session.network_error):
				ftp.close_server()
				logging.error("Connection was closed by the server.")

			sys.stdout = sys.stderr = open(os.devnull, "w")
			try:
				FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
			except RuntimeError:
				logging.error('Failed to run fuse process.')
				subprocess.call(["fusermount", "-u", mountpoint], shell=False)
				#FUSE(FtpFuse(ftp), mountpoint, nothreads=True, foreground=True)
		except:
			raise
		finally:
			if mp_created:
				os.rmdir(mountpoint)
			if ftp:
				ftp.close()
	else:
		'''t = FtpMountThread(server, user, mountpoint)
		t.start()
		t.join()
		return t
		fuse_process = Process(target=ftp_mount, args=(server, user, mountpoint, None, False))
		fuse_process.start()
		print("started fuse process, pid=%d" % fuse_process.pid)
		self.fuse_process = fuse_process
		return fuse_process
		'''

		# FUSE does not create a child process. So the process that calls
		# FUSE will not exit until the FUSE operation in finished (normally a kill -x
		# signal sent to process running FUSE). To be albe to run FUSE in the background,
		# fork the process and run FUSE int he child process. The parent process returns with
		# the child pid and exits immediately.
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

def arg_parse(*args, **kwargs):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '{{u{:p}}@}server{:port}',
        help='Server and user information. '
             '{u}: user, {p}:password, {server}: remote server, {port}: server port. example: anonymous@ftp.example.com/upload/')
    parser.add_argument(
        'mountpoint',
        help='Local directory where FTP server is to be mounted.')
    parser.add_argument(
        '-l', '--logfile', default='~/.ftpshell/log',
        help='File to use for logging (default: %(default)s).')

    return parser.parse_args(*args, **kwargs)


def main():
	from . import ftpshell
	args = arg_parse()
	if args.logfile == '~/.ftpshell/log':
		if not os.path.isdir(os.path.expanduser('~/.ftpshell/')):
			try:
				os.mkdir(os.path.expanduser('~/.ftpshell/'))
			except OSError:
				args.logfile = ''
	if args.logfile:
		try:
			logging.basicConfig(filename=args.logfile, level=logging.DEBUG)
		except IOError:
			args.logfile = ''

	try:
		#usage = 'Usage: ftpshell [username[:password]@]server[:port] mountpoint'
		server_addr, server_port, server_path, username, password, mountpoint = ftpshell.proc_input_args()
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
