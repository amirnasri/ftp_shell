"This module provides connection with fusepy module."
import os
from fuse import FUSE, FuseOSError, Operations

class FtpFuse(Operations):
	def __init__(self, ftp_session):
		self.fs = ftp_session


	def readdir(self, path, fh):
		print("readdir path=%s, fh=%d" % (path, fh))
		return list("abc")

	@staticmethod
	def get_dir(path):

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


