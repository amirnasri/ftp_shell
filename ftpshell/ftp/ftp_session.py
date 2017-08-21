"""
ftp session module.

This module provides FtpSession class which is used by ftp_cli
to establish a session with the ftp server and start
the communication. FtpSession class can also be used as an
stand-alone ftp-session as described in class documentation.
"""
from __future__ import print_function
import getpass
import inspect
import mmap
import os
import re
import sys
import signal
import socket
import subprocess
import threading
import time
import types
from . import _sendfile
from .ftp_raw import FtpRawRespHandler as FtpRaw
from .ftp_raw import raw_command_error
from .ftp_parser import parse_response_error
from .ftp_parser import FtpClientParser
from .file_info_cache import FileInfoCache
from .ftp_parser import connection_closed_error


class network_error(Exception): pass
class cmd_not_implemented_error(Exception): pass
class quit_error(Exception): pass
class login_error(Exception): pass
class response_error(Exception): pass
class transfer_complete(Exception): pass


def ftp_command(f):
	f.ftp_command = True
	return f


# TODO: remove!
def print_blue(s):
	return (LsColors.BOLD + LsColors.OKBLUE + "%s" % (s,) + LsColors.ENDC)


session_counter = 0

class FtpSession:
	"""Provides function to establish a connection with the server
	and high level function to communicate with the server such
	as get, put, and ls. This class relies on ftp_parser module
	for parsing raw ftp response and on ftp_raw module for handling
	the low level raw ftp commands such as RETR, STOR, and LIST.

	Example:
	    >>> fs = FtpSession("ftp.example.com")
	    >>> fs.login("username", "passwd")
	    >>> fs.get(["f1", "f2"])
	"""
	READ_BLOCK_SIZE = 1 << 19

	def __init__(self, server, port=21, verbose=False, transfer_type='binary', transfer_mode='passive', logfile=None):
		"""
		Args:
			server (str): domain-name or IP address of the ftp-server.
			port (int): port number the ftp-server is listening on.

		"""
		global session_counter

		self.text_file_extensions = set()
		self.server = server
		self.port = port
		self.load_text_file_extensions()
		self.transfer_type = 'A'
		if transfer_type == 'binary':
			self.transfer_type = 'I'
		self.passive = False
		if transfer_mode == 'passive':
			self.passive = True
		self.verbose = verbose
		self.logfile = logfile
		self.file_info_cache = FileInfoCache(self)
		self.stdout = sys.stderr
		self.mountpoint = None
		self.devnull = open(os.devnull, "wb")
		# self.shared_dict = Manager().dict()
		self.fuse_process = None
		self.session_id = session_counter
		session_counter += 1
		self.init_session()
		#print("Created session %d" % self.session_id)

	def init_session(self):
		self.cwd = ''
		self.cmd = None
		self.transfer_type = None
		self.parser = FtpClientParser()
		self.connected = False
		self.logged_in = False
		self.data_socket = None
		self.client = None
		self.home_dir = None

	def close_server(self):
		self.disconnect_server()
		self.init_session()

	def connect_server(self, server, port):
		try:
			self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.client.settimeout(10)
			self.client.connect((server, port))
		except socket.error:
			print("Could not connect to the server.", file=self.stdout)
		else:
			self.connected = True

	def disconnect_server(self):
		if self.connected:
			self.client.close()
			if self.data_socket:
				self.data_socket.close()
			self.connected = False

	def get_resp(self):
		"""Get a response to the current ftp request.

		Blocks until the ftp parser returns a complete response or raises an error.
		Then processes the response using the registered raw ftp response handler.
		"""
		try:
			resp = self.parser.get_resp(self.client, self.verbose)
		except parse_response_error:
			print('Error occurred while parsing response to ftp command %s\n' % self.cmd, file=self.stdout)
			self.close_server()
			raise
		if resp.resp_code == 421:
			raise connection_closed_error
		if self.parser.resp_failed(resp):
			raise response_error
		# print("got resp: \n" + str(resp))
		resp_handler = FtpRaw.get_resp_handler(self.cmd)
		if resp_handler is not None:
			try:
				resp_handler(resp)
			except raw_command_error:
				raise response_error

		return resp

	def send_raw_command(self, command):
		if self.verbose:
			print(command.strip())
		self.client.send(command)
		self.cmd = command.split()[0].strip()

	def load_text_file_extensions(self):
		try:
			filename = os.path.join(os.path.dirname(__file__), 'text_file_extensions')
			f = open(filename)
			for line in f:
				self.text_file_extensions.add(line.strip())
		except:
			pass

	def get_welcome_msg(self):
		try:
			self.get_resp()
		except response_error:
			self.close_server()

	def get_abs_path(self, path):
		if path.startswith("/"):
			return os.path.normpath(path)
		return os.path.normpath(os.path.join(self.cwd, path))

	@staticmethod
	def calculate_data_rate(filesize, seconds):
		return filesize / seconds

	@classmethod
	def print_usage(cls, fname=None):
		if not fname:
			fname = inspect.stack()[1][3]
		if hasattr(cls, fname):
			doc = getattr(getattr(cls, fname), '__doc__', None)
			if doc:
				doc = doc.split('\n')
				for line in doc:
					p = line.find('usage:')
					if p != -1:
						print(line[p:])

	@ftp_command
	def ascii(self, args):
		if len(args) != 0:
			FtpSession.print_usage()
			return
		self.transfer_type = 'A'
		print("Switched to ascii mode")

	@ftp_command
	def binary(self, args):
		if len(args) != 0:
			FtpSession.print_usage()
			return
		self.transfer_type = 'I'
		print("Switched to binary mode")

	@staticmethod
	def get_file_ext(filename):
		dot = filename.rfind('.')
		file_ext = ''
		if dot != -1:
			file_ext = filename[filename.rfind('.'):]
		return file_ext

	def setup_data_transfer(self, data_command):
		# import inspect
		# print("calling setup data transfer " + str(data_command).strip() + " called by " + inspect.stack()[1][3])
		# To prepare for data transfer, Send PASV (passive transfer mode)
		# or Port command (active transfer mode).
		if self.passive:
			self.send_raw_command("PASV\r\n")
			try:
				resp = self.get_resp()
			except response_error:
				print("PASV command failed.", file=self.stdout)
				raise

			data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			data_socket.settimeout(10)
			data_socket.connect((resp.trans.server_address, resp.trans.server_port))
			self.send_raw_command(data_command)
			# thread1 = FtpSession.myThread("Thread-1", self, data_socket, data_command, resp)
			# thread1.start()
			resp = self.get_resp()
			# thread1.join()
		else:
			s = socket.socket()
			s.connect(("8.8.8.8", 80))
			ip = s.getsockname()[0]
			s.close()
			if not ip:
				raise network_error("Could not get local IP address.")
			data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			data_socket.settimeout(10)
			data_socket.bind((ip, 0))
			data_socket.listen(1)
			_, port = data_socket.getsockname()
			if not port:
				raise network_error("Could not get local port.")

			port_h = int(port / 256)
			port_l = port - port_h * 256
			self.send_raw_command("PORT %s\r\n" % (",".join(ip.split('.') + [str(port_h), str(port_l)])))

			try:
				resp = self.get_resp()
			except response_error:
				print("PORT command failed.", file=self.stdout)
				raise

			self.send_raw_command(data_command)
			resp = self.get_resp()
			data_socket, address = data_socket.accept()
			if address[0] != self.client.getpeername()[0]:
				data_socket.close()
				data_socket = None
		return data_socket

	MIN_MMAP_SIZE = 1 << 40
	def get_mmap_download(self, transfer_type, path, anonymous):
		# If transfer type is binary and file size is "large"
		# use mmap to make transfer more efficient

		mm_file = None
		filename = os.path.basename(path)
		file_size = self.size([path])
		if transfer_type == 'I':
			if file_size > FtpSession.MIN_MMAP_SIZE:
				if not anonymous:
					f = file(filename, "w+b")
					f.seek(file_size - 1)
					f.write('\0')
					f.close()
					f = open(filename, "r+b")
					mm_file = mmap.mmap(f.fileno(), file_size)
					print(mm_file)
					f.close()
		elif anonymous:
			print("*********%s" % file_size)
			mm_file = mmap.mmap(-1, file_size)
			print("*********%s" % mm_file)
		if not mm_file:
			mm_file = open(filename, "w+b")
		return mm_file


	def download_file(self, path, offset, anonymous=False):
		"""Download a single file located at `path` on the server.

		Args:
		    path (str): path of the file to the downloaded. The path can be absolute
		        or relative to the current server directory.
		    offset (int): byte position to start the download from.
		    mm_file : memory-map object where the downloaded bytes should be written.

		Returns (bytes):
		    A buffer containing the contents of the file.

		"""
		file_ext = FtpSession.get_file_ext(path)
		# If transfer type is not set, send TYPE command depending on the type of the file
		# (TYPE A for ascii files and TYPE I for binary files)
		transfer_type = self.transfer_type
		if transfer_type is None:
			if file_ext != '' and file_ext in self.text_file_extensions:
				transfer_type = 'A'
			else:
				transfer_type = 'I'
		self.send_raw_command("TYPE %s\r\n" % transfer_type)
		try:
			self.get_resp()
		except response_error:
			print("TYPE command failed.", file=self.stdout)
			raise

		mm_file = self.get_mmap_download(transfer_type, path, anonymous)

		if offset != 0:
			self.send_raw_command("REST %d\r\n" % offset)
			try:
				self.get_resp()
			except response_error:
				print("REST command failed.", file=self.stdout)
				raise
		mm_file.seek(offset)

		self.data_socket = self.setup_data_transfer("RETR %s\r\n" % path)
		curr_time = time.time()
		file_data = bytes()
		tsize = 0
		while True:
			file_data = self.data_socket.recv(FtpSession.READ_BLOCK_SIZE)
			if file_data == '':
				break
			if transfer_type == 'A':
				# file_data_ = bytes(file_data.decode('ascii').replace('\r\n', '\n'), 'ascii')
				file_data = file_data.replace('\r\n', '\n')
			# file_data += file_data_
			mm_file.write(file_data)
			tsize += len(file_data)

		if self.verbose:
			elapsed_time = time.time() - curr_time
			print("%d bytes received in %.2f seconds (%.2f b/s)."
			      % (tsize, elapsed_time, FtpSession.calculate_data_rate(tsize, elapsed_time)))
		self.get_resp()
		self.data_socket.close()
		return mm_file

		"""
		f = open(filename, "wb")
		filesize = 0
		curr_time = time.time()
		while True:
			file_data = self.data_socket.recv(FtpSession.READ_BLOCK_SIZE)
			if file_data == b'':
				break
			if self.transfer_type == 'A':
				file_data = bytes(file_data.decode('ascii').replace('\r\n', '\n'), 'ascii')
			f.write(file_data)
			filesize += len(file_data)
		elapsed_time = time.time()- curr_time
		self.get_resp()
		f.close()
		self.data_socket.close()
		if self.verbose:
			print("%d bytes received in %f seconds (%.2f b/s)."
				%(filesize, elapsed_time, FtpSession.calculate_data_rate(filesize, elapsed_time)))
		"""
	# return file_data

	@ftp_command
	def size(self, args):
		if len(args) != 1:
			FtpSession.print_usage()
			return -1
		path = args[0]
		self.send_raw_command("SIZE %s\r\n" % path)
		try:
			resp = self.get_resp()
		except response_error:
			print("SIZE command failed.", file=self.stdout)
			raise
		return resp.size

	'''
	a/b/c/d/e

	a/b/c
	mkdir c
	cd c
	getdir d
	'''

	def download_dir(self, path):
		if path and path[-1] == '/':
			path = path[:-1]

		basename = os.path.basename(path)
		try:
			os.mkdir(basename)
		except OSError:
			print("get: cannot create local folder '%s'. Folder already exists." % basename, file=self.stdout)
			raise
		os.chdir(basename)
		path_info = self.get_path_info(path)
		filenames = path_info['filenames']
		dirnames = path_info['dirnames']
		for filename in filenames:
			mm_file = self.download_file(os.path.join(path, filename), 0)
			mm_file.close()
		for dirname in dirnames:
			self.download_dir(os.path.join(path, dirname))
		os.chdir('..')

	@ftp_command
	def get(self, args):
		""" usage: get path-to-file(s) """
		if len(args) == 0:
			FtpSession.print_usage()
			return

		paths = args
		for path in paths:
			f = None
			mm_file = None
			# fileno = os.open(filename, os.O_WRONLY | os.O_CREAT)
			"""
			f = file(filename, "w+b")
			file_size = self.size([path])
			f.seek(file_size - 1)
			f.write('\0')
			f.close()
			f = open(filename, "r+b")
			mm_file = mmap.mmap(f.fileno(), file_size)
			"""
			try:
				isdir = self.is_path_dir(path)
			except response_error:
				continue
			try:
				if isdir:
					self.download_dir(path)
				else:
					mm_file = self.download_file(path, 0)
					mm_file.close()
			except response_error:
				print("get: cannot access remote file '%s'. No such file or directory." % path, file=self.stdout)
			except OSError:
				pass


	def _upload_file(self, remote_path, offset, file_data):
		"""Upload a single file to location `remote_path` on the server.

		Args:
		    remote_path (str): path where the file is to be uploaded. The
		        path can be absolute or relative to the server current directory.
		    offset (int): file position to start the upload.
		    #TODO: check file data type
		    file_data (bytes): A buffer containing the contents of the file.

		"""

		# If transfer type is not set, send TYPE command depending on the type of the file
		# (TYPE A for ascii files and TYPE I for binary files)
		transfer_type = self.transfer_type
		file_ext = self.get_file_ext(remote_path)
		if transfer_type is None:
			if file_ext != '' and file_ext in self.text_file_extensions:
				transfer_type = 'A'
			else:
				transfer_type = 'I'
		self.send_raw_command("TYPE %s\r\n" % transfer_type)
		try:
			self.get_resp()
		except response_error:
			print("TYPE command failed.", file=self.stdout)
			raise

		if offset:
			self.send_raw_command("REST %d\r\n" % offset)
			try:
				self.get_resp()
			except response_error:
				print("REST command failed.", file=self.stdout)
				raise

		self.data_socket = self.setup_data_transfer("STOR %s\r\n" % remote_path)

		if self.transfer_type == 'A':
			file_data = bytes(file_data.decode('ascii').replace('\r\n', '\n'), 'ascii')
		self.data_socket.send(file_data)
		self.data_socket.close()
		self.get_resp()

		# TODO: only delte path from cache
		self.file_info_cache.del_path_info()

	def upload_file(self, local_path, remote_path):
		""" Upload a single file to the server current directory.
			Example: d1/d2/f1 will be uploaded at <curr-server-directory>/f1.
		Args:
		    local_path (str): path to the local file (relative or absolute).
		    remote_path (str): path to the remote file (relative or absolute).

		"""
		if self.verbose:
			print("Uploading file %s to the server...\n" % local_path)
		try:
			f = open(local_path, "rb")
		except IOError as e:
			print(e)
			return
		curr_time = time.time()
		'''offset = 0
		while True:
			file_data = f.read(FtpSession.READ_BLOCK_SIZE)
			if file_data == b'':
				break
			self._upload_file(remote_path, offset, file_data)
			# if self.transfer_type == 'A':
			#	file_data = bytes(file_data.decode('ascii').replace('\r\n', '\n'), 'ascii')
			# self.data_socket.send(file_data)
			offset += len(file_data)
		'''



		# If transfer type is not set, send TYPE command depending on the type of the file
		# (TYPE A for ascii files and TYPE I for binary files)
		transfer_type = self.transfer_type
		file_ext = self.get_file_ext(remote_path)
		if transfer_type is None:
			if file_ext != '' and file_ext in self.text_file_extensions:
				transfer_type = 'A'
			else:
				transfer_type = 'I'
		self.send_raw_command("TYPE %s\r\n" % transfer_type)
		try:
			self.get_resp()
		except response_error:
			print("TYPE command failed.", file=self.stdout)
			raise

		self.data_socket = self.setup_data_transfer("STOR %s\r\n" % remote_path)

		offset = 0
		if self.transfer_type == 'A':
			while True:
				file_data = f.read(FtpSession.READ_BLOCK_SIZE)
				if file_data == b'':
					break
				file_data = bytes(file_data.decode('ascii').replace('\r\n', '\n'), 'ascii')
				self.data_socket.send(file_data)
		else:
			'''
			while True:
				sent = sendfile.sendfile(self.data_socket.fileno(), f.fileno(), offset, FtpSession.READ_BLOCK_SIZE)
				if sent == 0:
					break
				offset += sent
			'''
			offset = _sendfile.sendfile(self.data_socket, f, 0)

			'''READ_BLOCK_SIZE = 1 << 19
			print(READ_BLOCK_SIZE)
			while True:
				file_data = f.read(READ_BLOCK_SIZE)
				if file_data == b'':
					break
				self.data_socket.send(file_data)
				offset += len(file_data)
			'''
		self.data_socket.close()
		self.get_resp()

		elapsed_time = time.time() - curr_time
		f.close()
		if self.verbose:
			filesize = offset
			print("%d bytes sent in %f seconds (%.2f b/s)."
			      % (filesize, elapsed_time, FtpSession.calculate_data_rate(filesize, elapsed_time)))

	def upload_path(self, local_path):
		""" Upload a single local path to the server current directory.

		Args:
		    local_path (str): path to a local file or folder. Paths may be absolute such as /d1/d2/, /d1/f1
		    or relative such as d1/d2, d1/f1.

		"""
		if os.path.isfile(local_path):
			self.upload_file(local_path, os.path.basename(local_path))
			# TODO: only delte path from cache
			self.file_info_cache.del_path_info()

		elif os.path.isdir(local_path):
			real_path = os.path.realpath(local_path)
			dirname = os.path.dirname(real_path)
			curr_dir = os.path.realpath('.')
			os.chdir(dirname)
			import pdb
			for root, dirnames, filenames in os.walk(os.path.basename(real_path)):
				if root:
					self.send_raw_command("MKD %s\r\n" % root)
					try:
						self.get_resp()
					except response_error:
						print("put: cannot create remote directory '%s'." % root, file=self.stdout)
						os.chdir(curr_dir)
						return
					except:
						os.chdir(curr_dir)
						raise

				for f in filenames:
					file_path = os.path.join(root, f)
					self.upload_file(file_path, file_path)
			os.chdir(curr_dir)

			# TODO: only delte path from cache
			self.file_info_cache.del_path_info()
		else:
			print("put: cannot access local file '%s'. No such file or directory." % local_path, file=self.stdout)

	@ftp_command
	def put(self, args):
		"""	usage: put local-path(s)

			Args:
				args (iterable of str): list of local-paths to be uploaded. Paths can point to
				either directories or files and may contain wildcards.

		"""
		paths = args
		# Expand paths using local shell.
		# TODO: use python globbing functions instead.
		# After expanding we can have absolute paths like /d1/d2/, /d1/f1 or relative paths
		# like d1/d2, d1/f1.
		expanded_paths = subprocess.check_output("echo %s" % " ".join(paths), shell=True).strip().split()
		for path in expanded_paths:
			# self.upload_path(path.decode("utf-8"))
			self.upload_path(path)

	def get_colored_ls_data(self, ls_data):
		lines = ls_data.split('\r\n')
		colored_lines = []
		import re
		# regex = re.compile()

		for l in lines:
			# re.sub(r'(d.*\s+(\w+\s+){7})(\w+)')
			if l:
				p = l.rfind(' ')
				if p == -1:
					continue
				fname = l[p + 1:].strip()
				if fname == '':
					continue
				color_prefix = ''
				color_postfix = ''
				if l[0] == 'd':
					color_prefix = LsColors.BOLD + LsColors.OKBLUE
					color_postfix = LsColors.ENDC
				elif LsColors.d:
					dot = fname.rfind('.')
					if dot != -1:
						ext = fname[dot + 1:]
						if ext in LsColors.d:
							color_prefix = LsColors.d[ext]
							color_postfix = LsColors.ENDC
				l = l[:p + 1] + color_prefix + l[p + 1:] + color_postfix

			colored_lines.append(l)

		return "\r\n".join(colored_lines)

	def get_path_info(self, path):
		"""Get path information. First look if the information for
		path is already cached. If not ask the server and add the
		information to the cache.

		:param path: str, path of file or directory on the server.
			The path can be absolute, or relative to the server current
			directory.
		//TODO: define return type
		:return:
		"""
		try:
			return self.file_info_cache.get_path_info(path)
		except KeyError:
			# KeyError indicates that the path does not exist in the cache. This
			# in turn means that the no list information has been fetched from
			# the server for this path. If list information was fetched previousely
			# but indicated that the path did not exist, the path is added to cache
			# with value None.
			ls_data = self._ls(path)
			self.file_info_cache.add_path_info(path, ls_data)
			return self.file_info_cache.get_path_info(path)

	class LsDataThread(threading.Thread):
		def __init__(self, name, data_socket):
			super(FtpSession.LsDataThread, self).__init__()
			self.name = name
			self.data_socket = data_socket
			# In response to LIST command, some servers do not close the data connection
			# after data transfer is complete. Possibly they assume the response to LIST
			# is small and fits in one packet. So the client can close the connection after
			# receiving the first packet.
			# To make ls work for these servers, set the data socket to non-blocking, so that
			# read any data that is available in the socket without blocking and then close
			# the connection.
			# data_socket.setblocking(False)
			self.ls_data = ""

		def run(self):
			# print("Starting " + self.name)
			try:
				ls_data = ""
				while True:
					ls_data_ = self.data_socket.recv(FtpSession.READ_BLOCK_SIZE)  # .decode('utf-8', 'ignore')
					if ls_data_ == "":
						break
					ls_data += ls_data_
				# print(ls_data)
				self.ls_data = ls_data
			except BaseException as e:
				print("Received unpexpected exception '%s'." % e.__class__.__name__)
			self.data_socket.close()

	def _ls(self, path, verbose=False):
		save_verbose = self.verbose
		self.verbose = verbose
		data_command = "LIST -a %s\r\n" % path
		self.data_socket = self.setup_data_transfer(data_command)
		t = FtpSession.LsDataThread("LsDataThread", self.data_socket)
		t.start()
		self.get_resp()
		t.join()
		ls_data = t.ls_data.decode('utf-8')
		self.data_socket.close()
		self.verbose = save_verbose
		return ls_data

	@ftp_command
	def ls(self, args):
		"""	usage: ls [dirname] """
		if len(args) > 1:
			FtpSession.print_usage()
			return
		path = ""
		if len(args) == 1:
			path = args[0]
		try:
			# ls_data = self._ls(self.get_abs_path(filename), self.verbose)
			path_info = self.get_path_info(path)
		except response_error:
			if self.data_socket:
				self.data_socket.close()
			print("ls: cannot access remote directory '%s'. No such file or directory." % path, file=self.stdout)
			return
		if path_info is None:
			# try:
			#	list(map(lambda x: x.split()[-1] if x else x, self._ls(os.path.dirname(filename), True).split('\r\n'))).index(filename)
			# except ValueError:
			print("ls: cannot access '%s'. No such file or directory." % path, file=self.stdout)
			return
		ls_data = path_info['ls_data']
		ls_data_colored = self.get_colored_ls_data(ls_data)
		print(ls_data_colored, end='')

	@ftp_command
	def pwd(self, args=None):
		self.send_raw_command("PWD\r\n")
		resp = self.get_resp()
		self.cwd = resp.cwd

	def get_cwd(self):
		if not self.cwd:
			self.pwd()
		return self.cwd

	@ftp_command
	def cd(self, args):
		""" usage: cd [dirname] """
		if len(args) > 1:
			FtpSession.print_usage()
			return
		path = None
		if len(args) == 1:
			path = args[0]

		if not path:
			self.send_raw_command("PWD\r\n")
			self.get_resp()
		else:
			self.send_raw_command("CWD %s\r\n" % path)
			try:
				self.get_resp()
			except response_error:
				print("cd: cannot access remote directory '%s'. No such directory." % path, file=self.stdout)
				return

			self.send_raw_command("PWD\r\n")
			resp = self.get_resp()
			self.cwd = resp.cwd

	@ftp_command
	def lcd(self, args):
		""" usage: lcd [local-dirname] """
		if len(args) > 1:
			FtpSession.print_usage()
			return
		path = None
		if len(args) == 1:
			path = args[0]

		if path:
			try:
				os.chdir(path)
			except OSError:
				print("lcd: cannot access local directory '%s'. No such directory." % path, file=self.stdout)

	@ftp_command
	def passive(self, args):
		"""	usage: passive[on | off] """
		if len(args) > 1:
			FtpSession.print_usage()
			return
		if len(args) == 0:
			self.passive = not self.passive
		elif len(args) == 1:
			if args[0] == 'on':
				self.passive = True
			elif args[0] == 'off':
				self.passive = False
			else:
				FtpSession.print_usage()
				return
		print("passive %s" % ('on' if self.passive else 'off'))

	@ftp_command
	def verbose(self, args):
		'''
			usage: verbose [on|off]
		'''
		if len(args) > 1:
			FtpSession.print_usage()
			return
		if len(args) == 0:
			self.verbose = not self.verbose
		elif len(args) == 1:
			if args[0] == 'on':
				self.verbose = True
			elif args[0] == 'off':
				self.verbose = False
			else:
				FtpSession.print_usage()
				return
		print("verbose %s" % ('on' if self.verbose else 'off'))

	@ftp_command
	def mkdir(self, args):
		"""	usage: mkdir remote-directory
		"""
		if len(args) > 1 or len(args) == 0:
			FtpSession.print_usage()
			return
		dirname = args[0]
		self.send_raw_command("MKD %s\r\n" % dirname)
		try:
			self.get_resp()
		except response_error:
			print("mkdir: cannot create remote directory '%s'." % dirname, file=self.stdout)
			return
		self.file_info_cache.del_path_info()

	def rmdir(self, path):
		"""ls_data = self.get_path_info(path)['ls_data']
		regex = re.compile(r'^((\S+\s+){8})(.*)')
		for ls_line in ls_data.split('\r\n'):
			if len(ls_line) == 0:
				continue
			filename = regex.search(ls_line).groups()[2]
			if filename == '.' or filename == '..':
				continue
			if ls_line[0] == 'd':
				self.rmdir(os.path.join(path, filename))
			else:
				self.rmfile(os.path.join(path, filename))
		"""
		path_info = self.get_path_info(path)
		filenames = path_info['filenames']
		dirnames = path_info['dirnames']
		for filename in filenames:
			self.rmfile(os.path.join(path, filename))
		for dirname in dirnames:
			self.rmdir(os.path.join(path, dirname))

		self.send_raw_command("RMD %s\r\n" % path)
		self.get_resp()

		# TODO: only delte path from cache
		self.file_info_cache.del_path_info()

	def rmfile(self, path):
		self.send_raw_command("DELE %s\r\n" % path)
		self.get_resp()
		# TODO: only delte path from cache
		self.file_info_cache.del_path_info()

	def path_exists(self, path):
		path_info = self.get_path_info(path)
		return path_info is not None

	def is_path_dir(self, path):
		path_info = self.get_path_info(path)
		if path_info:
			return path_info['isdir']

	def list_dir(self, path, dir_only=False):
		path_info = self.get_path_info(path)
		if path_info:
			list = ['%s/' % d for d in path_info['dirnames']]
			if not dir_only:
				list.extend(path_info['filenames'])
			return sorted(list)

	@ftp_command
	def rm(self, args):
		"""	usage: mkdir remote-file(s)
		"""
		if len(args) == 0:
			FtpSession.print_usage()
			return
		for path in args:
			try:
				isdir = self.is_path_dir(path)
			except response_error:
				continue
			try:
				if isdir:
					resp = raw_input("rm: '%s' is a directory. Are you sure you want to remove it? (y/[n])" % path)
					if (resp == 'y'):
						print(self.verbose)
						self.rmdir(path)
				else:
					self.rmfile(path)
			except response_error:
				print("rm: cannot delete remote directory '%s'." % path, file=self.stdout)
			else:
				self.file_info_cache.del_path_info()

	def mvdir(self, old_path, new_path):
		self.send_raw_command("MKD %s\r\n" % new_path)
		self.get_resp()
		"""ls_data = self.get_path_info(old_path)['ls_data']
		regex = re.compile(r'^((\S+\s+){8})(.*)')
		for ls_line in ls_data.split('\r\n'):
			if len(ls_line) == 0:
				continue
			filename = regex.search(ls_line).groups()[2]
			if filename == '.' or filename == '..':
				continue
			old_path_ = os.path.join(old_path, filename)
			new_path_ = os.path.join(new_path, filename)

			if ls_line[0] == 'd':
				mv_func = self.mvdir
			else:
				mv_func = self.mvfile
			mv_func(old_path_, new_path_)
		"""
		path_info = self.get_path_info(old_path)
		filenames = path_info['filenames']
		dirnames = path_info['dirnames']
		print(filenames, dirnames)
		for filename in filenames:
			old_path_ = os.path.join(old_path, filename)
			new_path_ = os.path.join(new_path, filename)
			self.mvfile(old_path_, new_path_)
		for dirname in dirnames:
			old_path_ = os.path.join(old_path, dirname)
			new_path_ = os.path.join(new_path, dirname)
			self.mvdir(old_path_, new_path_)

		self.send_raw_command("RMD %s\r\n" % old_path)
		self.get_resp()

	def mvfile(self, old_path, new_path):
		self.send_raw_command("RNFR %s\r\n" % old_path)
		self.get_resp()
		self.send_raw_command("RNTO %s\r\n" % new_path)
		self.get_resp()

	@ftp_command
	def mv(self, args):
		"""	usage: mv old-name new-name
		"""
		if len(args) != 2:
			FtpSession.print_usage()
			return

		old_path = args[0]
		new_path = args[1]

		try:
			isdir = self.is_path_dir(old_path)
		except response_error:
			print("mv: cannot stat file %s." % old_path, file=self.stdout)
			return
		try:
			if isdir:
				self.mvdir(old_path, new_path)
			else:
				self.mvfile(old_path, new_path)
		except response_error:
			print("mv: cannot move file %s." % old_path, file=self.stdout)
		else:
			# TODO: only delte path from cache
			self.file_info_cache.del_path_info()

	@ftp_command
	def user(self, args):
		'''
			usage: user username
		'''
		if len(args) != 1:
			FtpSession.print_usage()
			return

		username = args[0]
		if not self.connected:
			self.connect_server(self.server, self.port)
		self.send_raw_command("USER %s\r\n" % username)
		try:
			resp = self.get_resp()
		except response_error:
			raise login_error

		if (resp.resp_code == 331):
			password = None
			if username == 'anonymous':
				password = 'guest'
			if password is None:
				password = getpass.getpass(prompt='Password:')
			if password is None:
				raise login_error
			self.send_raw_command("PASS %s\r\n" % password)
			try:
				resp = self.get_resp()
			except response_error:
				raise login_error
		elif (resp.resp_code == 230):
			pass
		else:
			raise login_error
		self.username = username
		self.logged_in = True

	@ftp_command
	def login(self, username, password, server_path=""):
		if self.logged_in:
			print("Already logged in.", file=self.stdout)
			return
		if not username:
			raise login_error
		self.connect_server(self.server, self.port)
		self.get_welcome_msg()
		self.send_raw_command("USER %s\r\n" % username)
		try:
			resp = self.get_resp()
		except response_error:
			raise login_error

		if (resp.resp_code == 331):
			if password is None:
				raise login_error
			self.send_raw_command("PASS %s\r\n" % password)
			try:
				resp = self.get_resp()
			except response_error:
				raise login_error
		elif (resp.resp_code == 230):
			pass
		else:
			raise login_error
		self.home_dir = self.get_cwd()
		if server_path:
			self.cd([server_path])
		self.username = username
		self.logged_in = True

		# self.mountpoint = os.path.expanduser('~/.ftpshell4')
		'''
		pid = os.fork()
		if not pid:
			# Child process
			#print("Running fuse!")
			#sys.stdout = sys.stderr = open(os.devnull, "w")
			FUSE(FtpFuse(self, self.get_cwd()), self.mountpoint, nothreads=True, foreground=True)
			sys.exit()
		'''

		def run_fuse(self):
			sys.stdout = sys.stderr = open(os.devnull, "w")
			print("fuse before")
			try:
				FUSE(FtpFuse(self), self.mountpoint, nothreads=True, foreground=True)
			except RuntimeError:
				print("runtoirj*************")
				subprocess.call(["fusermount", "-u", self.mountpoint], shell=False)
				FUSE(FtpFuse(self), self.mountpoint, nothreads=True, foreground=True)


			# fuse_process = Process(target=run_fuse, args=(self,))
			# fuse_process.start()
			# print("started fuse process, pid=%d" % fuse_process.pid)
			# self.fuse_process = fuse_process

	def close(self):
		# Terminate the fuse process
		if self.fuse_process:
			try:
				print("terminating fuse process, pid=%d" % self.fuse_process.pid)
				os.kill(self.fuse_process.pid, signal.SIGINT)
				subprocess.call(["fusermount", "-u", self.mountpoint], shell=False)
				self.fuse_process.join()
			except:
				pass
		#print("session %d closed" % self.session_id)

	@ftp_command
	def quit(self, args):
		raise quit_error

	@staticmethod
	def get_ftp_commands():
		l = []
		for k, v in FtpSession.__dict__.items():
			if type(v) == types.FunctionType and hasattr(v, 'ftp_command'):
				l.append(k)
		return l

	@ftp_command
	def help(self, args):
		"""	usage: help command-name
		"""
		if len(args) == 1:
			self.print_usage(args[0])
		elif len(args) == 0:
			print("The following is a list of available commands:")
			for i, cmd in enumerate(sorted(FtpSession.get_ftp_commands())):
				print("%-20s" % cmd, end="")
				if (i + 1) % 4 == 0:
					print()
			print()
		else:
			FtpSession.print_usage()


def check_args(f):
	def new_f(*args, **kwargs):
		if hasattr(f, '__doc__'):
			doc = f.__doc__.split('\n')
			doc_ = None
			for line in doc:
				p = line.find('usage:')
				if p != -1:
					doc_ = line[p + 6:]
					break
			if doc_:
				n_args = len(doc_.split()) - 1
				print(n_args, args, kwargs)
				assert n_args == len(args[1]), \
					"%s expects %d arguments, %d given.\nusage: %s" % (
					new_f.__code__.co_name, n_args, len(args[1]), doc_)
				f(*args, **kwargs)

	return new_f


# Type of data transfer on the data channel
class transfer_type:
	list = 1
	file = 2


class LsColors:
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

	regex = re.compile(r'\*\.(.+)=(.+)')
	output = subprocess.check_output(['echo $LS_COLORS'], shell=True)
	d = {}
	if output:
		output = str(output).split(':')
		for i in output:
			m = regex.match(i)
			if m:
				d[m.group(1)] = ('\033[%sm' % m.group(2))


if __name__ == '__main__':
	ftp = FtpSession("172.18.2.169", 21)
	# try:
	ftp.login("anonymous", "p")
	ftp.ls("upload")
	ftp.get("upload/anasri/a.txt")
	# except:
	# print("login failed.")

	ftp.session_close()

'''
TODO:
- Add mv, status, site, active(port), chmod, cat (use lftp syntax)
- Add recursive directory download support and wildcard expansion for get
- Add history search using arrow key
- Add more exception handleing to ftpfuse, especially for timeout. Remove unncessary comments.
- Remove verbosity for ftpmount
'''
