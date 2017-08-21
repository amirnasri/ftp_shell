# About
This project provides two main scripts, `ftpshell` and `ftpmount`, that facilitate working with FTP servers. 

`ftpshell` is a command-line FTP client with an interface similar to the Bash shell. Main features provided by ftpshell
include:
* Support for common Bash commands such as `ls`, `rm`, `mv`, `mkdir`, and `rmdir`.
* Recursive directory upload and download.
* Command auto-complete. For file download auto-complete works based on remote file system while for upload
it works based on local file system.
* Improved download and upload file transfer speed using `mmap` and `sendfile`.
* Color-coded directory listing output. 

`ftpmount` allows the user to mount an FTP server on a local folder. Once mounted, all command and binaries available on the local machine can be run on the server as if it was a local folder.

# Installation
ftpshell can be install using the following command:

```bash
pip install ftpshell
```

The following prerequisites should be install before installing ftpshell:
* pysendfile: `pip install pysendfile`
* fusepy: `pip install fusepy`
