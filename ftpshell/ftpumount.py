import re
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
			pids.append(line.split()[1])
	if pids:
		subprocess.call(("kill -2 %s" % " ".join(pids)).split(), shell=False)

if __name__ == '__main__':
	main()
