import os
import subprocess
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
		fs.ls([])
	except:
		raise
	finally:
		fs.close()
	#assert 1 == 1
