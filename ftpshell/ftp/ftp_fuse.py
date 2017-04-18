"This module provides connection with fusepy module."
from __future__ import print_function
import os, stat
from fuse import FUSE, FuseOSError, Operations
import threading
import errno
import mmap

class path_not_found_error(Exception): pass

threadLock = threading.Lock()

def syncrnoize(f):
	def new_f(*args, **kwargs):
		#print("#########acquireing lock " + " called by " + inspect.stack()[1][3])
		#threadLock.acquire()
		#try:
		ret = f(*args, **kwargs)

		'''
		except Exception as e:
			pass #raise e
		finally:
			#print("#########released lock")
		'''
		#threadLock.release()
		return ret
	return new_f

class FtpFuse(Operations):
	def __init__(self, ftp_session, base_dir):
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
		print('base_dir=%s' % base_dir)
		if not ftp_session.path_exists(base_dir):
			raise path_not_found_error("path %s does not exist on the server." % base_dir)
		self.base_dir = base_dir
		self.curr_file = None

	def abspath(self, path):
		return os.path.join(self.base_dir, path[1:])

	@syncrnoize
	def access(self, path, mode):
		abs_path = self.abspath(path)
		access = (self.fs.get_path_info(abs_path)['stat']['st_mode'] >> 6) & mode
		print("access path=%s, mode=%d, access=%s" % (abs_path, mode, access))
		if not access:
			raise FuseOSError(errno.EACCES)


	@syncrnoize
	def readdir(self, path, fh):
		import sys
		print("readdir path=%s, fh=%d, ver=%s" % (path, fh, sys.version))
		if path is None or path[0] != "/":
			raise OSError
		abs_path = self.abspath(path)
		dirents = []
		if self.fs.is_path_dir(abs_path):
			path_info = self.fs.get_path_info(abs_path)
			dirents.extend([l.split()[-1] for l in path_info['ls_data'].split('\r\n') if len(l) != 0])
		#print("readdir: dirents=%s " % str(dirents))
		for dirent in dirents:
			yield dirent
		#return dirents

	@syncrnoize
	def access(self, path, mode):
		print("=============access path=%s, mode=%s" % (path, mode))
		if path is None or path[0] != "/":
			return FuseOSError(errno.EACCES)
		abs_path = self.abspath(path)
		print("=============getattr abs path=%s" % abs_path)
		path_info = self.fs.get_path_info(abs_path)
		if path_info is None:
			raise FuseOSError(errno.EACCES)

	@syncrnoize
	def getattr(self, path, fh=None):
		if path is None or path[0] != "/":
			raise OSError
		abs_path = self.abspath(path)
		path_info = self.fs.get_path_info(abs_path)
		print("=============getattr1 path=%s, path_info=%s" % (path, path_info))
		if path_info is None:
			raise FuseOSError(errno.ENOENT)
		return path_info['stat']

	# File methods
	# ============

	@syncrnoize
	def create(self, path, mode, fi=None):
		if path is None or path[0] != "/":
			raise OSError
		abs_path = self.abspath(path)
		print("=============create abs_path=%s, fh=" % abs_path)
		self.fs._upload_file(abs_path, 0, b"")
		if self.curr_file:
			self.curr_file.close()
			self.curr_file = None
		return 0

	@syncrnoize
	def open(self, path, flags):
		if path is None or path[0] != "/":
			raise OSError
		abs_path = self.abspath(path)
		print("=============open abs_path=%s, fh=" % abs_path)
		if flags & os.O_CREAT:
			self.fs._upload_file(abs_path, 0, b"")
		if self.curr_file:
			self.curr_file.close()
			self.curr_file = None
		return 0

	@syncrnoize
	def read(self, path, length, offset, fh):
		if path is None or path[0] != "/":
			raise OSError
		abs_path = self.abspath(path)
		print("=============read abs_path=%s, fh=" % abs_path)
		if not self.curr_file:
			file_size = self.fs.size([abs_path])
			if file_size == 0:
				return b""
			print("filesize=%d" % file_size)
			mm_file = mmap.mmap(-1, file_size)
			#mm_file.seek(0)
			self.curr_file = mm_file
			self.fs.download_file(abs_path, 0, self.curr_file)
		self.curr_file.seek(offset)
		return self.curr_file.read(length)

	@syncrnoize
	def write(self, path, buf, offset, fh):
		if path is None or path[0] != "/":
			raise OSError
		abs_path = self.abspath(path)
		print("=============write abs_path=%s, fh=" % abs_path)
		self.fs._upload_file(abs_path, offset, buf)
		return len(buf)

	def unlink(self, path):
		abs_path = self.abspath(path)
		self.fs.rmfile(abs_path)

	def mkdir(self, path, mode):
		abs_path = self.abspath(path)
		self.fs.mkdir([abs_path])

	def rmdir(self, path):
		abs_path = self.abspath(path)
		self.fs.rmdir(abs_path)

	def rename(self, old, new):
		abs_old_path = self.abspath(old)
		abs_new_path = self.abspath(new)
		self.fs.mv([abs_old_path, abs_new_path])

	def truncate(self, path, length, fh=None):
		pass

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
import ftp_session


def dump_args(func):
	"This decorator dumps out the arguments passed to a function before calling it"
	argnames = func.__code__.co_varnames[:func.__code__.co_argcount]
	fname = func.__code__.co_name
	def echo_func(*args,**kwargs):
		arguments = ', '.join(
			'%s=%r' % entry
			for entry in list(zip(argnames,args[:len(argnames)]))+[("args",list(args[len(argnames):]))]+[("kwargs",kwargs)])
		print("%s(%s)" % (ftp_session.print_blue(fname), arguments))
		return func(*args, **kwargs)
	return echo_func

for i in Operations.__dict__.items():
	if type(i[1])== types.FunctionType:
		setattr(Operations, i[0], dump_args(i[1]))