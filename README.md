# About
This project provides two main scripts, `ftpshell` and `ftpmount`, that facilitate working with FTP servers. 

`ftpshell` is a command-line FTP client with an interface similar to the Bash shell. Main features provided by ftpshell
include:
* Support for common Bash commands such as `ls`, `rm`, `mv`, `mkdir`, and `rmdir`.
* Ability to run local binaries like `cat`, `find`, `grep`, etc on the remote FTP server.
* Recursive directory upload and download.
* Command auto-complete based on remote file system for download and local file system for upload.
* Improved file download and upload transfer speed using `mmap` and `sendfile` system calls.
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

# Usage
![Alt text](/screenshot_ftpshell1.png "Optional Title")
