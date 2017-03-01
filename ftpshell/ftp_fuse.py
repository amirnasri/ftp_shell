"This module provides connection with fusepy module."

from fuse import FUSE, FuseOSError, Operations

class FtpFuse(Operations):
	def __init__(self, ftp_session):
		self.ftp_session = ftp_session


	def readdir(self, path, fh):
		print("readdir path=%s, fh=%d" % (path, fh))
		return list("abc")


	def getattr(self, path, fh=None):
		print("getattr path=%s, fh=%d" % (path, -1 if fh is None else fh))
		return dict()


