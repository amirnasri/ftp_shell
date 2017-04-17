import os
import subprocess

def main():
	pids = []
	ps_output = subprocess.check_output("ps aux | grep ftpmount | grep -v grep", shell=True)
	for line in ps_output.split("\n"):
		if len(line) == 0:
			continue
		pids.append(line.split()[1])
	os.system("kill -2 %s" % " ".join(pids))

if __name__ == '__main__':
	main()
