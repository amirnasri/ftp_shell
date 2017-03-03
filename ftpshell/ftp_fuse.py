"This module provides connection with fusepy module."
import os, stat
from fuse import FUSE, FuseOSError, Operations

class FileStat(object):
	def __init__(self, mode, nlink, uid, gid, size, mtime):
		self.mode = mode
		self.nlink = nlink
		self.uid = uid
		self.gid = gid
		self.size = size
		self.mtime = mtime

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
		mode = FtpFuse.get_file_mode(fields[0])
		mtime = 0
		return fields[-1], FileStat(mode, int(fields[1]), fields[2], fields[3], int(fields[4]), mtime)

	@staticmethod
	def parse_ls_data(ls_data):
		ls_lines = [l for l in ls_data.split("/r/n") if len(l) > 0]
		ls_info = dict()
		for l in ls_lines:
			name, fs = FtpFuse.parse_ls_line(l)
			ls_info[name] = fs
		return ls_info

	def getattr(self, path, fh=None):
		print("getattr path=%s, fh=%d" % (path, -1 if fh is None else fh))
		if path is None or path[0] != "/":
			return dict()
		path = path[1:]
		if path and path[-1] == "/":
			path = path[:-1]
		if self.fs.isdir(path):
			ls_data = self.ftp_session._ls(os.path.dirname(path))
		else:
			ls_data = self.ftp_session._ls(path)
		return dict()


