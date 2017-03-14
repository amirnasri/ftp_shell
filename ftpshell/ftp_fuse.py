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

	@staticmethod
	def get_file_mode(s):
		m = FtpFuse.file_mode_table[s[0]]
		m += int("".join(map(lambda x: '0' if x == '-' else '1', s[1:])), 2)
		return m

	@staticmethod
	def parse_ls_line(line):
		fields = line.split()
		file_stat = dict()
		file_stat["st_mode"] = FtpFuse.get_file_mode(fields[0])
		file_stat["st_mtime"] = 0
		file_stat["st_nlink"] = int(fields[1])
		file_stat["st_uid"] = fields[2]
		file_stat["st_giu"] = fields[3]
		file_stat["st_size"] = int(fields[4])
		return fields[-1], file_stat

	@staticmethod
	def parse_ls_data(ls_data):
		ls_lines = [l for l in ls_data.split("\r\n") if len(l) > 0]
		print(ls_lines)
		ls_info = dict()
		for l in ls_lines:
			filename, file_stat = FtpFuse.parse_ls_line(l)
			ls_info[filename] = file_stat
		return ls_info

	@syncrnoize
	def access(self, path, mode):
		print("=============access path=%s, mode=%s" % (path, mode))
		#if not os.access(full_path, mode):
		ls_data = self.fs._ls(path)
		if not ls_data:
			raise FuseOSError(errno.EACCES)

	def getattr(self, path, fh=None):
		print("=============getattr path=%s, fh=" % path + str(fh))
		file_stat = dict()
		if path is None or path[0] != "/":
			return file_stat
		cwd = self.fs.get_cwd()
		print("cwd=" + cwd)
		path = cwd + path
		#if path[-1] == "/":
		#	path = path[:-1]
		#print(path, self.fs.isdir(path))
		#dirname = ""
		isdir = self.fs.isdir(path)
		#isdir = True
		#if isdir:
		#	dirname = os.path.dirname(path)
		#	ls_data = self.fs._ls(dirname)
		#else:
		print("=============getattr new path=%s" % path)
		ls_data = self.fs._ls(path)
		print(ls_data)
		ls_info = FtpFuse.parse_ls_data(ls_data)
		print(ls_info)
		try:
			if isdir:
				file_stat = ls_info['.']
			else:
				file_stat = ls_info[os.path.basename(path)]
		except KeyError:
			pass
		print("=============getattr ends!")
		return file_stat


