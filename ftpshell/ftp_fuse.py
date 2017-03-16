"This module provides connection with fusepy module."
import os, stat
from fuse import FUSE, FuseOSError, Operations
import threading
import errno

threadLock = threading.Lock()

def syncrnoize(f):
	def new_f(*args, **kwargs):
		print("#########acquireing lock")
		threadLock.acquire()
		ret = f(*args, **kwargs)
		threadLock.release()
		print("#########released lock")
		return ret
	return new_f

class FtpFuse(Operations):
	file_mode_table = dict((k, v) for v, k in stat._filemode_table[0])

	def __init__(self, ftp_session):
		self.fs = ftp_session

	def readdir(self, path, fh):
		print("readdir path=%s, fh=%d" % (path, fh))
		return list("abc")

	@syncrnoize
	def access(self, path, mode):
		print("=============access path=%s, mode=%s" % (path, mode))
		#if not os.access(full_path, mode):
		ls_data = self.fs._ls(path)
		if not ls_data:
			raise FuseOSError(errno.EACCES)

	@syncrnoize
	def getattr(self, path, fh=None):
		print("=============getattr path=%s, fh=" % path + str(fh))
		file_stat = dict()
		if path is None or path[0] != "/":
			return file_stat
		cwd = self.fs.get_cwd()
		print("cwd=" + cwd)
		abs_path = self.fs.get_abs_path(path[1:])
		isdir = self.fs.isdir(abs_path)

		print("=============getattr abs path=%s" % abs_path)

		self.fs.get_file_info(self, file):

		ls_data = self.fs._ls(abs_path)
		print(ls_data)
		file_stats = FtpFuse.parse_ls_data(ls_data)
		#FtpFuse.add_path_cache(isdir, path, ls_info)
		print(file_stats)
		try:
			if isdir:
				file_stat = file_stats["."]
			else:
				file_stat = file_stats[os.path.basename(path)]
		except KeyError:
			pass
		print("=============getattr ends! %s, isdir=%d, os.path.basename(path)=%s" % (str(file_stat), isdir, os.path.basename(path)))
		return file_stat


