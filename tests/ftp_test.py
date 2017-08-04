import os
import subprocess
import sys
from ..ftpshell.ftp.ftp_session import FtpSession

def subprocess_check_call(cmd):
	subprocess.check_call(cmd.split(), shell=False)

def test_ftp_get_file():
	test_file = 'ftp-test-file3'
	os.system('echo abcd > /tmp/%s' % test_file)
	fs = FtpSession('172.18.2.169')
	#fs = FtpSession('localhost', verbose=True)
	#fs = FtpSession('ftp.swfwmd.state.fl.us', verbose=True)

	try:
		fs.login('anonymous', 'p')
		fs.cd(['upload/anasri'])
		#fs.cd(['/pub/incoming'])
		fs.rm([test_file])
		# Upload a test file to the server and then download
		# the uploaded file. If the two files differ fail the test.
		fs.put(['/tmp/' + test_file])
		save_stdout = sys.stdout
		sys.stdout = open('/tmp/stdout', 'w')
		fs.ls([])
		sys.stdout = save_stdout
		try:
			subprocess_check_call('grep %s /tmp/stdout' % test_file)
			os.system('rm /tmp/stdout')
			subprocess_check_call('mv /tmp/%s /tmp/%s_copy' % (test_file, test_file))
			fs.get([test_file])
			subprocess_check_call('diff ./%s /tmp/%s_copy' % (test_file, test_file))
		except OSError:
			assert False
	except:
		raise
	finally:
		os.remove(test_file)
		fs.close()


def get_rand_int():
	import random
	return random.randint(10**4, 10**5)

def test_ftp_get_folder():
	rand = get_rand_int()
	curr_dir = os.getcwd()
	os.chdir('/tmp')
	test_folder = 'ftp-test-folder_%s' % str(rand)
	if os._exists(test_folder):
		os.rmdir(test_folder)
	os.mkdir(test_folder)
	os.chdir(test_folder)
	for i in range(5):
		rand = get_rand_int()
		with open('%s' % rand, 'w') as f:
			f.write('%s\n' % rand)
	for i in range(3):
		test_sub_folder = '%s_sub_%d' %(test_folder, get_rand_int())
		os.mkdir(test_sub_folder)
		os.chdir(test_sub_folder)
		for i in range(4):
			rand = get_rand_int()
			with open('%s' % rand, 'w') as f:
				f.write('%s\n' % rand)
		os.chdir('..')
	os.chdir(curr_dir)

	fs = FtpSession('172.18.2.169')
	#fs = FtpSession('localhost', verbose=True)
	#fs = FtpSession('ftp.swfwmd.state.fl.us', verbose=True)
	print('test_folder=%s' %  test_folder)
	try:
		fs.login('anonymous', 'p')
		fs.cd(['upload/anasri'])
		#fs.cd([''/pub/incoming'])
		#fs.rm([test_folder])

		# Upload a test folder to the server and then download
		# the uploaded folder. If the two folders differ fail the test.
		fs.put(['/tmp/' + test_folder])
		save_stdout = sys.stdout
		sys.stdout = open('/tmp/stdout', 'w')
		fs.ls([])
		sys.stdout = save_stdout
		try:
			subprocess_check_call('grep %s /tmp/stdout' % test_folder)
			os.system('rm /tmp/stdout')
			subprocess_check_call('mv /tmp/%s /tmp/%s_copy' % (test_folder, test_folder))
			fs.get([test_folder])
			subprocess_check_call('diff -r ./%s /tmp/%s_copy' % (test_folder, test_folder))
			subprocess_check_call('rm -fr ./%s /tmp/%s_copy' % (test_folder, test_folder))
		except OSError:
			assert False

		# Rename the test folder to a different folder and donwload it again.
		# Compare it to the original folders and fail the test if the folders differ.
		try:
			fs.mv(['/tmp/%s' % test_folder, '/tmp/%s_mv' % test_folder])
			fs.get(['/tmp/%s_mv' % test_folder])
			subprocess_check_call('diff -r ./%s /tmp/%s_mv' % (test_folder, test_folder))
			subprocess_check_call('rm -fr ./%s /tmp/%s_mv' % (test_folder, test_folder))
		except OSError:
			assert False

	except:
		raise
	finally:
		fs.close()

'''
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



'''