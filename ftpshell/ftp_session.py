"""
ftp session module.

This module provides FtpSession class which is
used by ftp_cli to establish a session with the ftp server and
 start the communication.
"""
import socket
import time
from .ftp_raw import FtpRawRespHandler as FtpRaw, raw_command_error
from .ftp_parser import parse_response_error
from .ftp_parser import ftp_client_parser
import inspect
import subprocess
import re
import sys
import getpass

class network_error(Exception): pass
class cmd_not_implemented_error(Exception): pass
class quit_error(Exception): pass
class connection_closed_error(Exception): pass
class login_error(Exception): pass
class response_error(Exception): pass

def ftp_command(f):
	f.ftp_command = True
	return f

class FtpSession:
	"""
	Provides function to establish a connection with the server
	and high level function to communicate with the server such
	as get, put, and ls. This class relies on ftp_parser module
	for parsing raw ftp response and on ftp_raw module for handling
	the low level raw ftp commands such as RETR, STOR, and LIST.
	"""
	READ_BLOCK_SIZE = 1024

	def __init__(self, server, port=21):
		self.text_file_extensions = set()
		self.server = server
		self.port = port
		self.load_text_file_extensions()
		self.passive = True
		self.verbose = True
		self.init_session()

	def init_session(self):
		self.cwd = ''
		self.cmd = None
		self.transfer_type = None
		self.parser = ftp_client_parser()
		self.connected = False
		self.logged_in = False
		self.data_socket = None
		self.client = None

	def close_server(self):
		self.disconnect_server()
		self.init_session()

	def connect_server(self, server, port):
		try:
			self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.client.settimeout(10)
			self.client.connect((server, port))
		except socket.error:
			print("Could not connect to the server.", file=sys.stdout)
		else:
			self.connected = True

	def disconnect_server(self):
		if self.connected:
			self.client.close()
			if self.data_socket:
				self.data_socket.close()
			self.connected = False

	def get_resp(self):
		while True:
			s = self.client.recv(FtpSession.READ_BLOCK_SIZE)
			if (s == b''):
				raise connection_closed_error
			try:
				resp = self.parser.get_resp(s, self.verbose)
			except parse_response_error:
				print('Error occurred while parsing response to ftp command %s\n' % self.cmd, file=sys.stdout)
				self.close_server()
				raise
			if resp:
				if self.parser.resp_failed(resp):
					raise response_error
				break

		resp_handler = FtpRaw.get_resp_handler(self.cmd)
		if resp_handler is not None:
			resp_handler(resp)

		return resp

	def send_raw_command(self, command):
		if self.verbose:
			print(command.strip())
		self.client.send(bytes(command, 'ascii'))
		self.cmd = command.split()[0].strip()


	def load_text_file_extensions(self):
		try:
			f = open('text_file_extensions')
			for line in f:
				self.text_file_extensions.add(line.strip())
		except:
			pass

	def get_welcome_msg(self):
		try:
			self.get_resp()
		except response_error:
			self.close_server()

	@staticmethod
	def calculate_data_rate(filesize, seconds):
		return filesize/seconds

	@classmethod
	def print_usage(cls):
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
	def get_file_info(path):
		# Get filename and file extension from path
		slash = path.rfind('/')
		if slash != -1:
			filename = path[slash + 1:]
		else:
			filename = path
		dot = filename.rfind('.')
		file_ext = ''
		if dot != -1:
			file_ext = filename[filename.rfind('.'):]
		return filename, file_ext

	def setup_data_transfer(self, data_command):
		# To prepare for data transfer, Send PASV (passive transfer mode)
		# or Port command (active transfer mode).
		if self.passive:
			self.send_raw_command("PASV\r\n")
			try:
				resp = self.get_resp()
			except response_error:
				print("PASV command failed.", file=sys.stdout)
				raise raw_command_error

			data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			data_socket.settimeout(10)
			data_socket.connect((resp.trans.server_address, resp.trans.server_port))
			self.send_raw_command(data_command)
			self.get_resp()
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

			port_h = int(port/256)
			port_l = port - port_h * 256
			self.send_raw_command("PORT %s\r\n" % (",".join(ip.split('.') + [str(port_h), str(port_l)])))

			try:
				resp = self.get_resp()
			except response_error:
				print("PORT command failed.", file=sys.stdout)
				raise raw_command_error

			self.send_raw_command(data_command)
			resp = self.get_resp()
			data_socket, address = data_socket.accept()
			if address[0] != self.client.getpeername()[0]:
				data_socket.close()
				data_socket = None
		return data_socket

	@ftp_command
	def get(self, args):
		""" usage: get path-to-file """
		if len(args) != 1:
			FtpSession.print_usage()
			return
		path = args[0]
		filename, file_ext = FtpSession.get_file_info(path)
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
			print("TYPE command failed.", file=sys.stdout)
			return

		if self.verbose:
			print("Requesting file '%s' from the server...\n" % filename)

		try:
			self.data_socket = self.setup_data_transfer("RETR %s\r\n" % path)
		except response_error:
			print("get: cannot access remote file '%s'. No such file or directory." % filename, file=sys.stdout)
			return

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

	@ftp_command
	def put(self, args):
		"""	usage: get path-to-file """
		if len(args) != 1:
			FtpSession.print_usage()
			return
		path = args[0]
		filename, file_ext = FtpSession.get_file_info(path)
		try:
			f = open(filename, "rb")
		except FileNotFoundError:
			print("put: cannot access local file '%s'. No such file or directory." % filename, file=sys.stdout)
			return

		# If transfer type is not set, send TYPE command depending on the type of the file
		# (TYPE A for ascii files and TYPE I for binary files)
		transfer_type = self.transfer_type
		if transfer_type is None:
			if file_ext != '' and file_ext in self.text_file_extensions:
				transfer_type = 'A'
			else:
				transfer_type = 'I'
		self.send_raw_command("TYPE %s\r\n" % transfer_type)
		self.get_resp()

		if self.verbose:
			print("Sending file %s to the ftp server...\n" % filename)

		self.data_socket = self.setup_data_transfer("STOR %s\r\n" % path)

		filesize = 0
		curr_time = time.time()
		while True:
			file_data = f.read(FtpSession.READ_BLOCK_SIZE)
			if file_data == b'':
				break
			if self.transfer_type == 'A':
				file_data = bytes(file_data.decode('ascii').replace('\r\n', '\n'), 'ascii')
			self.data_socket.send(file_data)
			filesize += len(file_data)
		elapsed_time = time.time()- curr_time
		self.data_socket.close()
		f.close()
		self.get_resp()
		if self.verbose:
			print("%d bytes sent in %f seconds (%.2f b/s)."
				%(filesize, elapsed_time, FtpSession.calculate_data_rate(filesize, elapsed_time)))

	def get_colored_ls_data(self, ls_data):
		lines = ls_data.split('\r\n')
		colored_lines = []
		import re
		#regex = re.compile()

		for l in lines:
			#re.sub(r'(d.*\s+(\w+\s+){7})(\w+)')
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

	@ftp_command
	def ls(self, args):
		"""	usage: ls [dirname] """
		if len(args) > 1:
			FtpSession.print_usage()
			return
		filename = ''
		if len(args) == 1:
			filename = args[0]

		'''
		self.send_raw_command("PASV\r\n")
		resp = self.get_resp()
		data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		data_socket.connect((resp.trans.server_address, resp.trans.server_port))
		'''
		data_command = "LIST %s\r\n" % filename
		self.data_socket = self.setup_data_transfer(data_command)
		if not self.data_socket:
			return

		ls_data = ''
		while True:
			ls_data_ = self.data_socket.recv(FtpSession.READ_BLOCK_SIZE).decode('utf-8', 'ignore')
			if ls_data_ == '':
				break
			ls_data += ls_data_

		self.data_socket.close()
		self.get_resp()
		if len(ls_data) == 0:
			print("ls: cannot access remote file '%s'. No such directory." % filename, file=sys.stdout)
			return

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
				print("cd: cannot access remote directory '%s'. No such directory." % path, file=sys.stdout)
				return

			self.send_raw_command("PWD\r\n")
			resp = self.get_resp()
			self.cwd = resp.cwd

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
	def mkdir(self, dirname):
		self.send_raw_command("MKD %s\r\n" % dirname)
		self.get_resp()

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

	def login(self, username, password, server_path):
		while not username:
			username = input('Username:')
		if username == 'anonymous':
			password = 'guest'
		if password is None:
			password = getpass.getpass(prompt='Password:')
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
		if server_path:
			self.cd([server_path])
		self.username = username
		self.logged_in = True

	@ftp_command
	def quit(self, args):
		raise quit_error

	def run_command(self, cmd_line):
		""" run a single ftp command received from the ftp_cli module.
		"""
		if cmd_line[0] == '!':
			subprocess.call(cmd_line[1:], shell=True)
			return
		cmd_line = cmd_line.split()
		cmd = cmd_line[0]
		cmd_args = cmd_line[1:]

		if hasattr(FtpSession, cmd):
			if not self.logged_in and (cmd != 'user' and cmd != 'quit'):
				print("Not logged in. Please login first with USER and PASS.")
				return
			getattr(FtpSession, cmd)(self, cmd_args)
		else:
			raise cmd_not_implemented_error

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
					"%s expects %d arguments, %d given.\nusage: %s" % (new_f.__code__.co_name, n_args, len(args[1]), doc_)
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
	#try:
	ftp.login("anonymous", "p")
	ftp.ls("upload")
	ftp.get("upload/anasri/a.txt")
	#except:
	#print("login failed.")

	ftp.session_close()

'''
TODO:
- Add mkdir, rm, rmdir, mv, status, user, pass, site, active(port), lcd, chmod, cat, help, put (use lftp syntax)
- Add command completion using tab based on method documents
- Add history search using arrow key
'''
