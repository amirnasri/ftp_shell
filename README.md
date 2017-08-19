# ftpshell
ftpshell is a command-line FTP client with an interface similar to the Bash shell. Main features provided by ftpshell
include:
* Support for common Bash commands such as `ls`, `rm`, `mv`, `mkdir`, and `rmdir`.
* Recursive directory upload and download.
* Command auto-complete. For file download auto-complete works based on remote file system while for upload
it works based on local file system.
* Improved download and upload file transfer speed using `mmap` and `sendfile`.
* Color-coded directory listing output. 
