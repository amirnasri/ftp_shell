from __future__ import print_function
import os
import readline
import subprocess

class Completer(object):
	""" Class to provide tab-completion functionality
	to the command line.
	"""
	def __init__(self, options):
		self.options = sorted(options)
		return

	def complete(self, text, state):
		response = None
		print(text, state)
		response = None
		if state == 0:
			if text:
				if text.startswith('put '):
					fname_prefix = text[4:]
					listdir = os.listdir('.')
					self.matches = [s
									for s in listdir
									if s and s.startswith(fname_prefix)]
					if len(self.matches) == 1:
						self.matches = ["put " + i for i in self.matches]

				else:
					self.matches = [s
									for s in self.options
									if s and s.startswith(text)]

			else:
				self.matches = self.options[:]

		# Return the state'th item from the match list,
		# if we have that many.
		try:
			response = self.matches[state]
		except IndexError:
			response = None
		return response

if __name__ == '__main__':
	# Setup readline to provide tab completion for the command line.
	word_list = ['get', 'gets', 'put']
	readline.set_completer(Completer(word_list).complete)
	readline.parse_and_bind('tab: complete')

	while True:
		raw_input('--> ')
