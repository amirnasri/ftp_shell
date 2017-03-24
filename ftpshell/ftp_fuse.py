"This module provides connection with fusepy module."
import os, stat
from fuse import FUSE, FuseOSError, Operations
import threading
import errno
import inspect

threadLock = threading.Lock()

def syncrnoize(f):
	def new_f(*args, **kwargs):
		print("#########acquireing lock " + " called by " + inspect.stack()[1][3])
		threadLock.acquire()
		try:
			ret = f(*args, **kwargs)
		except Exception as e:
			raise e
		finally:
			threadLock.release()
			print("#########released lock")
		return ret
	return new_f

class FtpFuse(Operations):
	def __init__(self, ftp_session, base_dir):
		"""
		:param ftp_session: An instance of :class:`FtpSession`
		:param base_dir: The directory on the ftp server to be mounted.
			All paths received from FUSE will be added to his path to obtain
			the absolute path on the server.
			Example: for base_dir="/usr/ftpuser/", FUSE path "/p" will be translated
			to "/usr/ftpuser/p"
		"""
		self.fs = ftp_session
		if not ftp_session.path_exists(base_dir):
			raise path_not_found_error
		self.base_dir = base_dir

	def abspath(self, path):
		return os.path.join(self.base_dir, path[1:])

	#@syncrnoize
	def access(self, path, mode):
		abs_path = self.abspath(path)
		access = self.fs.get_path_info(abs_path)['stat']['st_mode'] & mode
		print("access path=%s, mode=%d, access=%s" % (abs_path, mode, access))
		return access


	#@syncrnoize
	def readdir(self, path, fh):
		print("readdir path=%s, fh=%d" % (path, fh))
		if path is None or path[0] != "/":
			raise FileNotFoundError
		abs_path = self.abspath(path)
		dirents = []
		if self.fs.is_path_dir(abs_path):
			path_info = self.fs.get_path_info(abs_path)
			dirents.extend([l.split()[-1] for l in path_info['ls_data'].split('\r\n') if len(l) != 0])
		#print("readdir: dirents=%s " % str(dirents))
		for dirent in dirents:
			yield dirent
		#return dirents

	'''
	@syncrnoize
	def access(self, path, mode):
		print("=============access path=%s, mode=%s" % (path, mode))
		if path is None or path[0] != "/":
			return file_stat
		abs_path = self.base_dir, path[1:]
		print("=============getattr abs path=%s" % abs_path)
		path_info = self.fs.get_path_info(abs_path)
		if path_info is None:
			raise FuseOSError(errno.EACCES)
	'''

	#@syncrnoize
	def getattr(self, path, fh=None):
		#print("=============getattr1 path=%s, fh=" % path + str(fh))
		if path is None or path[0] != "/":
			raise FileNotFoundError
		abs_path = self.abspath(path)
		path_info = self.fs.get_path_info(abs_path)
		if path_info is None:
			raise FileNotFoundError
		return path_info['stat']

	# File methods
	# ============



import types

def dump_args(func):
	"This decorator dumps out the arguments passed to a function before calling it"
	argnames = func.__code__.co_varnames[:func.__code__.co_argcount]
	fname = func.__code__.co_name
	def echo_func(*args,**kwargs):
		arguments = ', '.join(
			'%s=%r' % entry
			for entry in list(zip(argnames,args[:len(argnames)]))+[("args",list(args[len(argnames):]))]+[("kwargs",kwargs)])
		print("%s(%s)" % (fname, arguments))
		return func(*args, **kwargs)
	return echo_func

for i in Operations.__dict__.items():
	if type(i[1])== types.FunctionType:
		setattr(Operations, i[0], dump_args(i[1]))