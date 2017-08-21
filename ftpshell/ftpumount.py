import os
import re
import signal
import subprocess

def main():
	pids = []
	try:
		ps_output = subprocess.check_output("ps aux".split(), shell=False)
	except subprocess.SubprocessError:
		return
	regex = re.compile("python.*ftpmount")
	for line in ps_output.split("\n"):
		if line and regex.search(line):
			pids.append(int(line.split()[1]))
	for pid in pids:
		os.kill(pid, signal.SIGINT)

if __name__ == '__main__':
	main()
