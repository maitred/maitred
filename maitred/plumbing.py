"""Handle large numbers of pipes."""

import os
import io
import pty
import select
import collections

CHILD_PID = 0

STDIN_FILENO = 0
STDOUT_FILENO = 1
STDERR_FILENO = 2

ENDL = '\n'
PTY_ENDL = '\r\n'

CHUNK_SIZE = 4096

class Process:
    """A subprocess with IO pipes tied to a pseudoterminal."""

    def __init__(self, pid, stdin, stdout, stderr):
        """Initialize a Process object.

        keyword arguments:
        pid -- an integral process id
        stdin -- a WritePipe for standard input
        stdout -- a ReadPipe for standard output
        stderr -- a ReadPipe for standard error

        """
        self.pid = pid
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pipes = (stdin, stdout, stderr)

        self.__lines_read = collections.deque()
        self.__current_line = ''

    def write(self, text):
        """Non-blocking write to the subprocess's stdin."""
        self.stdin.write(text, blocking=False)

    def readline(self):
        """Non-blocking read from the subprocess's stdout.

        If there is currently nothing to read, return None.

        """
        self.__sync_read()
        if self.__lines_read:
            return self.__lines_read.popleft() + '\n'

    def readlines(self):
        """Non-blocking read from the subprocess's stdout.

        If there is currently nothing to read, return None.

        """
        self.__sync_read()
        while self.__lines_read:
            yield self.__lines_read.popleft() + '\n'

    def __sync_read(self):
        # Helper function for non-blocking update read from pipes.
        new_text = self.stdout.read(blocking=False)
        if new_text is None:
            return

        text = self.__current_line + new_text
        *new_lines, self.__current_line = text.split(ENDL)
        self.__lines_read.extend(new_lines)

class Pipe(io.TextIOBase):
    """A file-like object representing a UNIX pipe."""

    def __init__(self, fd, pty=False):
        self.fd = fd
        self.pty = pty
        self.buffer = bytearray()

    def fileno(self):
        return self.fd

class ReadPipe(Pipe):
    """A file-like object for reading from a UNIX pipe."""

    def readable(self):
        return True

    def flush(self):
        while self.readbuffer():
            pass

    def read(self, blocking=True):
        if blocking:
            self.flush()
        elif not self.buffer:
            return None
        text = self.buffer.decode()
        if self.pty:
            text = text.replace(PTY_ENDL, ENDL)
        self.buffer = bytearray()
        return text

    def readbuffer(self):
        try:
            raw_bytes = os.read(self.fd, CHUNK_SIZE)
        except (OSError, IOError):
            return
        self.buffer.extend(raw_bytes)
        return len(raw_bytes)

class WritePipe(Pipe):
    """A file-like object for writing to a UNIX pipe."""

    def writable(self):
        return True

    def flush(self):
        while self.buffer:
            self.writebuffer()

    def write(self, text, blocking=True):
        raw_bytes = text.encode()
        self.buffer.extend(raw_bytes)
        if blocking:
            self.flush()

    def writebuffer(self):
        if not self.buffer:
            return 0
        n = os.write(self.fd, self.buffer)
        self.buffer = self.buffer[n:]
        return n

class ProcessManager:
    """Central manager of a large number of Process objects."""

    def __init__(self):
        self.__fdtable = {}
        self.__poller = select.poll()

    def spawn(self, argv):
        """Create a new Process, using tokenized arguments argv."""
        process = fork_exec(argv)
        self.register(process)
        return process

    def register(self, process):
        """Register an already-created Process with the manager."""
        for pipe in process.pipes:
            self.__fdtable[pipe.fileno()] = (process, pipe)
            self.__poller.register(pipe)

    def sync(self, blocking=False, timeout=0):
        """Flush the read and write buffers of each Process."""
        timeout = None if blocking else timeout
        for fd, eventmask in self.__poller.poll(timeout):
            process, pipe = self.__fdtable[fd]
            if (select.POLLNVAL | select.POLLERR) & eventmask:
                self.close(process)
                continue
            if (select.POLLHUP | select.POLLIN) & eventmask:
                if pipe.readable():
                    pipe.readbuffer()
            if select.POLLOUT & eventmask:
                if pipe.writable():
                    pipe.writebuffer()

    def close(self, process):
        """Deregister a Process and close each of its pipes."""
        for pipe in process.pipes:
            try:
                self.__poller.unregister(pipe)
            except KeyError:
                pass
            pipe.close()

def fork_exec(argv):
    """Spawn a subprocess with arguments argv using fork then execlp."""

    # Create pipes for stdin, stdout, stderr.
    pty_master_fd, pty_slave_fd = pty.openpty()
    pipe_read_fd, pipe_write_fd = os.pipe()
    err_read_fd, err_write_fd = os.pipe()

    # Fork the process.
    pid = os.fork()

    # In the child process, attach pipes to sdtin, stdout, and stderror. Then
    # use execlp to overwrite the current process with the new subprocess.
    if pid == CHILD_PID:
        os.close(pty_master_fd)
        os.close(pipe_write_fd)
        os.close(err_read_fd)
        os.setsid()

        os.dup2(pipe_read_fd, STDIN_FILENO)
        os.dup2(pty_slave_fd, STDOUT_FILENO)
        os.dup2(err_write_fd, STDERR_FILENO)
        if(pty_slave_fd > STDERR_FILENO):
            os.close(pty_slave_fd)

        # Force interpretation as a tty by opening it as such.
        temp_fd = os.open(os.ttyname(STDOUT_FILENO), os.O_RDWR)
        os.close(temp_fd)

        os.execlp(argv[0], *argv)

    # In the parent process, attach the other end of each pipe to a single
    # Process object, and return it.
    os.close(pty_slave_fd)
    os.close(pipe_read_fd)
    os.close(err_write_fd)
    pipe_in = WritePipe(pipe_write_fd)
    pipe_out = ReadPipe(pty_master_fd, pty=True)
    pipe_err = ReadPipe(err_read_fd)
    return Process(pid, stdin=pipe_in, stdout=pipe_out, stderr=pipe_err)
