# This is a cache to store file information fetched from the server.
# Cache entries have the form (k, v) where the key is the absolute
# path of the file on the server and v is a list with three elements:
# v[0]: raw ls data fetched from the server
# v[1]: dictionary containing stats information of the file (format is
#   the same as that return by os.stat
# v[2]: True if the file is a directory otherwise False

class FileInfoCache(object):
	def __init__(self, fs):
		self.fs = fs
		self.cache = dict()

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
		# file_stat["st_uid"] = fields[2]
		# file_stat["st_giu"] = fields[3]
		file_stat["st_uid"] = 0
		file_stat["st_giu"] = 0
		file_stat["st_size"] = int(fields[4])
		return fields[-1], file_stat

	def parse_ls_data(ls_data):
		"""
			Parse response from the server to LIST -a command.
		"""
		ls_lines = [l for l in ls_data.split("\r\n") if len(l) > 0]
		file_stats = dict()
		for l in ls_lines:
			filename, file_stat = FtpFuse.parse_ls_line(l)
			file_stats[filename] = file_stat
		return file_stats

	def add_path_info(self, path, ls_data):
		abs_path = self.fs.get_abs_path(path)
		file_stats = FileInfoCache.parse_ls_data(ls_data)
		isdir = False

		v = dict()
		v['ls_data'] = ls_data
		if '.' in file_stats:
			isdir = True
			v['stat'] = file_stats['.']
			v['isdir'] = True
		else:
			v['stat'] = file_stats.items()[0]
			v['isdir'] = False

		self.cache[file] = v
		print("added (%s, %s) to cache " % (file, v))

		if isdir:
			for filename, stat in file_stats:
				if not '.' in k_:
					v = dict()
					v['stat'] = stat
					filename = os.path.join(os.path.dirname(abs_path), filename)
					self.cache[filename] = v
					print("added (%s, %s) to cache " % (filename, v))

	def get_path_info(self, path):
		return self.cache[self.fs.get_abs_path(path)]
