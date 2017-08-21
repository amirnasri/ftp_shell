"This module provides connection with fusepy module."
from __future__ import print_function
import os, stat
from fuse import FUSE, FuseOSError, Operations
import threading
import errno
import signal
from .ftp_session import connection_closed_error

class path_not_found_error(Exception): pass

threadLock = threading.Lock()

def _print(*args, **kwargs):
	#print(*args, **kwargs)
	pass

def syncrnoize(f):
	def new_f(*args, **kwargs):
		#_print("#########acquireing lock " + " called by " + inspect.stack()[1][3])
		#threadLock.acquire()
		ret = f(*args, **kwargs)

		'''
		except Exception as e:
			pass #raise e
		finally:
			#_print("#########released lock")
		'''
		#threadLock.release()
		return ret
	return new_f

class FtpFuse(Operations):
	def __init__(self, ftp_session, base_dir=None):
		"""
		:param ftp_session: An instance of :class:`FtpSession`
		:param base_dir: The directory on the ftp server to be mounted.
			This is an absolute path (starts with a "/"). All paths received
			from FUSE will be added to his path to obtain the absolute path
			on the server.
			Example: for base_dir="/usr/ftpuser/", FUSE path "/p" will be
			translated to "/usr/ftpuser/p"
		"""
		self.fs = ftp_session
		_print('base_dir=%s' % base_dir)
		if base_dir and not ftp_session.path_exists(base_dir):
			raise path_not_found_error("path %s does not exist on the server." % base_dir)
		if not base_dir:
			base_dir = ftp_session.get_cwd()
		self.base_dir = base_dir
		self.curr_file = None

	def abspath(self, path):
		if self.base_dir:
			return os.path.join(self.base_dir, path[1:])
		else:
			return os.path.join(self.fs.cwd, path[1:])

	@syncrnoize
	def access(self, path, mode):
		abs_path = self.abspath(path)
		try:
			access = (self.fs.get_path_info(abs_path)['stat']['st_mode'] >> 6) & mode
			_print("access path=%s, mode=%d, access=%s" % (abs_path, mode, access))
		except connection_closed_error:
			os.kill(os.getpid(), signal.SIGINT)
			return
		except:
			raise FuseOSError(errno.EACCES)
		if not access:
			raise FuseOSError(errno.EACCES)

	@syncrnoize
	def readdir(self, path, fh):
		import sys
		_print("readdir path=%s, fh=%d, ver=%s" % (path, fh, sys.version))
		if path is None or path[0] != "/":
			raise FuseOSError(errno.EACCES)
		abs_path = self.abspath(path)
		try:
			path_info = self.fs.get_path_info(abs_path)
		except connection_closed_error:
			os.kill(os.getpid(), signal.SIGINT)
			return
		except:
			raise FuseOSError(errno.EACCES)

		for dirent in path_info['filenames']:
			yield dirent
		for dirent in path_info['dirnames']:
			yield dirent

	@syncrnoize
	def access(self, path, mode):
		_print("=============access path=%s, mode=%s" % (path, mode))
		if path is None or path[0] != "/":
			return FuseOSError(errno.EACCES)
		abs_path = self.abspath(path)
		_print("=============getattr abs path=%s" % abs_path)
		try:
			path_info = self.fs.get_path_info(abs_path)
		except connection_closed_error:
			os.kill(os.getpid(), signal.SIGINT)
			return
		except:
			raise FuseOSError(errno.EACCES)

		if path_info is None:
			raise FuseOSError(errno.EACCES)

	@syncrnoize
	def getattr(self, path, fh=None):
		if path is None or path[0] != "/":
			raise FuseOSError(errno.EACCES)

		abs_path = self.abspath(path)
		try:
			path_info = self.fs.get_path_info(abs_path)
		except connection_closed_error:
			os.kill(os.getpid(), signal.SIGINT)
			return
		except:
			raise FuseOSError(errno.ENOENT)
		_print("=============getattr1 path=%s, path_info=%s" % (path, path_info))

		if path_info is None:
			raise FuseOSError(errno.ENOENT)
		return path_info['stat']

	# File methods
	# ============

	@syncrnoize
	def create(self, path, mode, fi=None):
		if path is None or path[0] != "/":
			raise FuseOSError(errno.EACCES)
		abs_path = self.abspath(path)
		_print("=============create abs_path=%s, fh=" % abs_path)
		try:
			self.fs._upload_file(abs_path, 0, b"")
		except:
			raise FuseOSError(errno.EACCES)

		if self.curr_file:
			self.curr_file.close()
			self.curr_file = None
		return 0

	@syncrnoize
	def open(self, path, flags):
		if path is None or path[0] != "/":
			raise FuseOSError(errno.EACCES)
		abs_path = self.abspath(path)
		_print("=============open abs_path=%s, fh=" % abs_path)
		if flags & os.O_CREAT:
			try:
				self.fs._upload_file(abs_path, 0, b"")
			except:
				raise FuseOSError(errno.EACCES)

		if self.curr_file:
			self.curr_file.close()
			self.curr_file = None
		return 0

	@syncrnoize
	def read(self, path, length, offset, fh):
		if path is None or path[0] != "/":
			raise FuseOSError(errno.ENOENT)
		abs_path = self.abspath(path)
		_print("=============read abs_path=%s, fh=" % abs_path)
		if not self.curr_file:
			#file_size = self.fs.size([abs_path])
			#if file_size == 0:
			#	return b""
			#_print("filesize=%d" % file_size)
			#mm_file = mmap.mmap(-1, file_size)
			#mm_file.seek(0)
			try:
				self.curr_file = self.fs.download_file(abs_path, 0, True)
			except:
				raise FuseOSError(errno.ENOENT)

		self.curr_file.seek(offset)
		return self.curr_file.read(length)

	@syncrnoize
	def readlink(self, path):
		if path is None or path[0] != "/":
			raise FuseOSError(errno.ENOENT)
		abs_path = self.abspath(path)

		try:
			path_info = self.fs.get_path_info(abs_path)
		except IOError:
			os.kill(os.getpid(), signal.SIGINT)
			raise FuseOSError(errno.EACCES)
		except:
			raise FuseOSError(errno.EACCES)

		if path_info is None:
			raise FuseOSError(errno.EACCES)
		return path_info['slink']

	@syncrnoize
	def write(self, path, buf, offset, fh):
		if path is None or path[0] != "/":
			raise FuseOSError(errno.ENOENT)
		abs_path = self.abspath(path)
		_print("=============write abs_path=%s, fh=" % abs_path)
		try:
			self.fs._upload_file(abs_path, offset, buf)
		except:
			raise FuseOSError(errno.EACCES)
		return len(buf)

	@syncrnoize
	def unlink(self, path):
		abs_path = self.abspath(path)
		try:
			self.fs.rmfile(abs_path)
		except:
			raise FuseOSError(errno.ENOENT)

	@syncrnoize
	def mkdir(self, path, mode):
		abs_path = self.abspath(path)
		try:
			self.fs.mkdir([abs_path])
		except:
			raise FuseOSError(errno.ENOENT)

	@syncrnoize
	def rmdir(self, path):
		abs_path = self.abspath(path)
		try:
			self.fs.rmdir(abs_path)
		except:
			raise FuseOSError(errno.ENOENT)

	@syncrnoize
	def rename(self, old, new):
		abs_old_path = self.abspath(old)
		abs_new_path = self.abspath(new)
		try:
			self.fs.mv([abs_old_path, abs_new_path])
		except:
			raise FuseOSError(errno.ENOENT)

	@syncrnoize
	def truncate(self, path, length, fh=None):
		pass

	@syncrnoize
	def flush(self, path, fh):
		pass

	@syncrnoize
	def release(self, path, fh):
		if self.curr_file:
			self.curr_file.close()
			self.curr_file = None


import types
import sys
#TODO: use relative import
from . import ftp_session


def dump_args(func):
	"This decorator dumps out the arguments passed to a function before calling it"
	argnames = func.__code__.co_varnames[:func.__code__.co_argcount]
	fname = func.__code__.co_name
	def echo_func(*args,**kwargs):
		arguments = ', '.join(
			'%s=%r' % entry
			for entry in list(zip(argnames,args[:len(argnames)]))+[("args",list(args[len(argnames):]))]+[("kwargs",kwargs)])
		_print("%s(%s)" % (ftp_session.print_blue(fname), arguments))
		return func(*args, **kwargs)
	return echo_func

for i in Operations.__dict__.items():
	if type(i[1])== types.FunctionType:
		setattr(Operations, i[0], dump_args(i[1]))