# This is a cache to store file information fetched from the server.
# Cache entries have the form (k, v) where the key is the absolute
# path of the resource on the server and v is dictionary with the following items:
# v['ls_data']: raw ls data fetched from the server
# v['stat']: dictionary containing stats information for the file (format is
#   the same as that returned by os.stat
# v['isdir']: True if the path is a directory otherwise False

import stat
import os

class FileInfoCache(object):
	file_mode_table = dict((k, v) for v, k in stat._filemode_table[0])
	def __init__(self, fs):
		self.fs = fs
		self.cache = dict()

	@staticmethod
	def get_file_mode(s):
		m = FileInfoCache.file_mode_table[s[0]]
		m += int("".join(map(lambda x: '0' if x == '-' else '1', s[1:])), 2)
		return m

	@staticmethod
	def parse_ls_line(line):
		fields = line.split()
		from .ftp_session import print_blue
		print_blue((repr(line), len(line)))
		print_blue(repr(fields))
		file_stat = dict()
		file_stat["st_mode"] = FileInfoCache.get_file_mode(fields[0])
		file_stat["st_atime"] = 0
		file_stat["st_ctime"] = 0
		file_stat["st_mtime"] = 0
		file_stat["st_nlink"] = int(fields[1])
		# file_stat["st_uid"] = fields[2]
		# file_stat["st_giu"] = fields[3]
		file_stat["st_uid"] = 0
		file_stat["st_gid"] = 0
		file_stat["st_size"] = int(fields[4])
		return " ".join(fields[8:]), file_stat

	def parse_ls_data(ls_data):
		"""
			Parse response from the server to LIST -a command.
		"""
		ls_lines = [l for l in ls_data.split("\r\n") if len(l) > 0]
		file_stats = dict()
		for l in ls_lines:
			filename, file_stat = FileInfoCache.parse_ls_line(l)
			file_stats[filename] = (file_stat, l + "\r\n")
		return file_stats

	def add_path_info(self, path, ls_data):
		abs_path = self.fs.get_abs_path(path)
		if not ls_data:
			self.cache[abs_path] = None
			return
		file_stats = FileInfoCache.parse_ls_data(ls_data)
		isdir = False

		v = dict()
		v['ls_data'] = ls_data
		if '.' in file_stats:
			isdir = True
			v['stat'] = file_stats['.'][0]
			v['isdir'] = True
		else:
			v['stat'] = list(file_stats.values())[0][0]
			v['isdir'] = False

		self.cache[abs_path] = v
		#print("added (%s, %s) to cache " % (abs_path, v))

		# Add to cache the file we get from doing LIST
		# on a directory.
		#print(file_stats)
		if isdir:
			for filename, (stat, l) in file_stats.items():
				# Don't cache directories since we don't have
				# ls_data for them.
				if not l.startswith('d'):
					v = dict()
					v['stat'] = stat
					v['isdir'] = False
					v['ls_data'] = l
					abs_path_ = os.path.join(abs_path, filename)
					self.cache[abs_path_] = v
					#print("added (%s, %s) to cache " % (abs_path_, v))

	def get_path_info(self, path):
		return self.cache[self.fs.get_abs_path(path)]

	def del_path_info(self):
		self.cache.clear()


















