import logging
import os
import re
import readline

RE_SPACE = re.compile('.*\s+$', re.M)

class PathOps(object):
	def __init__(self, listdir, isdir, exists):
		self.listdir = listdir
		self.isdir = isdir
		self.exists = exists

class Completer(object):
	def __init__(self, commands):
		logging.basicConfig(filename='example.log', level=logging.DEBUG)
		self.complete_resp_list = None
		self.commands = commands
		self.path_ops_local = PathOps(Completer.listdir, os.path.isdir, os.path.exists)
		self.path_ops_remote = None

		def list_dir_local_dir_only(path):
			return ['%s/' % i for i in os.listdir(path) if os.path.isdir(os.path.join(path, i))]

		self.path_ops_dir_only_local = PathOps(list_dir_local_dir_only, os.path.isdir, os.path.exists)
		self.path_ops_dir_only_remote = None

	def set_ftp_session(self, ftp):
		self.ftp = ftp
		self.path_ops_remote = PathOps(ftp.list_dir, ftp.is_path_dir, ftp.path_exists)

		def list_dir_remote_dir_only(path):
			return ftp.list_dir(path, True)

		self.path_ops_dir_only_remote = PathOps(list_dir_remote_dir_only, ftp.is_path_dir, ftp.path_exists)


	def complete_local(self, args):
		if not args:
			return self.complete_path(self.path_ops_local, '.')
		return self.complete_path(self.path_ops_local, args[-1])


	def complete_remote(self, args):
		if not args:
			return self.complete_path(self.path_ops_remote, '.')
		return self.complete_path(self.path_ops_remote, args[-1])


	def complete_get(self, args):
		return self.complete_remote(args)


	def complete_put(self, args):
		return self.complete_local(args)


	def complete_mv(self, args):
		return self.complete_remote(args)


	def complete_rm(self, args):
		return self.complete_remote(args)


	def complete_ls(self, args):
		return self.complete_remote(args)


	def complete_mkdir(self, args):
		return self.complete_remote(args)


	def complete_cd(self, args):
		if not args:
			return self.complete_path(self.path_ops_dir_only_remote, '.')
		return self.complete_path(self.path_ops_dir_only_remote, args[-1])


	def complete_lcd(self, args):
		if not args:
			return self.complete_path(self.path_ops_dir_only_local, '.')
		return self.complete_path(self.path_ops_dir_only_local, args[-1])


	@staticmethod
	def listdir(root):
		"List directory 'root' appending the path separator to subdirs."
		res = []
		for name in os.listdir(root):
			path = os.path.join(root, name)
			if os.path.isdir(path):
				name += os.sep
			res.append(name)
		return res


	@staticmethod
	def complete_path(path_ops, path=None):
		"Perform completion of filesystem path."
		if not path:
			return path_ops.listdir('.')
		dirname, rest = os.path.split(path)
		tmp = dirname if dirname else '.'
		res = [os.path.join(dirname, p)
				for p in path_ops.listdir(tmp) if p.startswith(rest)]
		# more than one match, or single match which does not exist (typo)
		if len(res) > 1 or not path_ops.exists(path):
			return res
		# resolved to a single directory, so return list of files below it
		if path_ops.isdir(path):
			return [os.path.join(path, p) for p in path_ops.listdir(path)]
		# exact file match terminates this completion
		return [path + ' ']


	def complete_init(self):
		"Generic readline completion entry point."
		buffer = readline.get_line_buffer()
		line = readline.get_line_buffer().split()
		# show all commands
		if not line:
			cl = [c + ' ' for c in self.commands]
			logging.debug('returing |%s|' % cl)
			return cl

		# account for last argument ending in a space
		if RE_SPACE.match(buffer):
			line.append('')
		# resolve command to the implementation function
		cmd = line[0].strip()
		if cmd in self.commands:
			impl = getattr(self, 'complete_%s' % cmd)
			args = line[1:]
			if args:
				return (impl(args) + [None])
			return [cmd + ' ']
		return [c + ' ' for c in self.commands if c.startswith(cmd)] + [None]


	def complete(self, text, state):
		if state == 0:
			self.complete_resp_list = self.complete_init()
			logging.debug('|%s|' % self.complete_resp_list[state])

		return self.complete_resp_list[state]



if __name__ == '__main__':
	import logging
	logging.basicConfig(filename='example.log', level=logging.DEBUG)
	comp = Completer(['get'])
	# we want to treat '/' as part of a word, so override the delimiters
	readline.set_completer_delims(' \t\n;')
	readline.parse_and_bind("tab: complete")
	readline.set_completer(comp.complete)

	while True:
		raw_input('--> ')
