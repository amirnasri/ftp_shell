import os
import subprocess
import sys
from ftpshell.ftpshell.ftp.ftp_session import FtpSession

def subprocess_check_call(cmd):
	subprocess.check_call(cmd.split(), shell=False)

def test_ftp_get():
	test_file = "ftp-test-file3"
	os.system("echo abcd > /tmp/%s" % test_file)
	#fs = FtpSession("172.18.2.169")
	#fs = FtpSession("localhost", verbose=True)
	fs = FtpSession("ftp.swfwmd.state.fl.us", verbose=True)

	try:
		fs.login("anonymous", "p")
		#fs.cd(["upload/anasri"])
		fs.cd(["/pub/incoming"])
		fs.rm([test_file])
		fs.put(["/tmp/" + test_file])
		save_stdout = sys.stdout
		sys.stdout = open("/tmp/stdout", "w")
		fs.ls([])
		sys.stdout = save_stdout
		try:
			subprocess_check_call("grep %s /tmp/stdout" % test_file)
			os.system("rm /tmp/stdout")
			subprocess_check_call("mv /tmp/%s /tmp/%s_copy" % (test_file, test_file))
			fs.get([test_file])
			subprocess_check_call("diff ./%s /tmp/%s_copy" % (test_file, test_file))
		except OSError:
			assert False
	except:
		raise
	finally:
		fs.close()
"""
	Test cases:

	put dir
	put file
	put /dir
	put /file
	put dir file /dir /file

	transfer large_file with time measurement

	move dir1 dir2
	move /dir1 /dir2

	remove dir1 dir2
	remove /dir1 /dir2

	different servers

	active passives



"""