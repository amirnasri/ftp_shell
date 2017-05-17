import os
import subprocess
import sys
from ftpshell.ftp.ftp_session import FtpSession

def subprocess_call(cmd):
	subprocess.call(cmd.split(), shell=False)

def test_ftp_get():
	test_file = "ftp-test-file"
	os.system("echo abcd > /tmp/%s" % test_file)
	#fs = FtpSession("172.18.2.169")
	fs = FtpSession("localhost")
	try:
		fs.login("anonymous", "p")
		#fs.cd(["upload/anasri"])
		fs.rm([test_file])
		fs.put(["/tmp/" + test_file])
		save_stdout = sys.stdout
		sys.stdout = open("/tmp/stdout", "w")
		fs.ls([])
		sys.stdout = save_stdout
		try:
			subprocess.check_call(("grep %s /tmp/stdout" % test_file).split())
		except OSError:
			assert False
		os.system("rm /tmp/stdout")
		subprocess_call("mv /tmp/%s /tmp/%s_copy" % (test_file, test_file))
		fs.get([test_file])
	except:
		raise
	finally:
		fs.close()
	#assert 1 == 1
