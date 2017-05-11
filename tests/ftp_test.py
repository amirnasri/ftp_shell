from ..ftpshell.ftp.ftp_session import FtpSession

def test_ftp_get():
	fs = FtpSession("localhost")
	fs.login("amir", "salam")
	fs.get(["f1"])

	#assert 1 == 1
