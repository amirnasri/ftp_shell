from distutils.core import setup

setup(
    name='ftpshell',
    version='2.2',
    author='Amir Nasri',
    author_email='amnasri@gmail.com',
    license='MIT',
    packages=['ftpshell', 'ftpshell.ftp'],
    scripts=['bin/ftpshell', 'bin/ftpmount', 'bin/ftpumount'],
    url='http://pypi.python.org/pypi/ftpshell/',
    description='FTP client in python.',
)
