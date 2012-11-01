#!/usr/bin/env python

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
    def __init__(self, pid, stdin, stdout, stderr):
        self.pid = pid
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pipes = (stdin, stdout, stderr)

        self.__lines_read = collections.deque()
        self.__current_line = ''

    def write(self, text):
        self.stdin.write(text, blocking=False)

    def readline(self):
        self.__sync_read()
        if self.__lines_read:
            return self.__lines_read.popleft() + '\n'

    def readlines(self):
        self.__sync_read()
        while self.__lines_read:
            yield self.__lines_read.popleft() + '\n'

    def __sync_read(self):
        new_text = self.stdout.read(blocking=False)
        if new_text is None:
            return

        text = self.__current_line + new_text
        *new_lines, self.__current_line = text.split(ENDL)
        self.__lines_read.extend(new_lines)

class Pipe(io.TextIOBase):
    def __init__(self, fd, pty=False):
        self.fd = fd
        self.pty = pty
        self.buffer = bytearray()

    def fileno(self):
        return self.fd

class ReadPipe(Pipe):
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
    def __init__(self):
        self.__fdtable = {}
        self.__poller = select.poll()

    def spawn(self, argv):
        process = fork_exec(argv)
        self.register(process)
        return process

    def register(self, process):
        for pipe in process.pipes:
            self.__fdtable[pipe.fileno()] = (process, pipe)
            self.__poller.register(pipe)

    def sync(self, blocking=False, timeout=0):
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
        for pipe in process.pipes:
            try:
                self.__poller.unregister(pipe)
            except KeyError:
                pass
            pipe.close()

def fork_exec(argv):
    pty_master_fd, pty_slave_fd = pty.openpty()
    pipe_read_fd, pipe_write_fd = os.pipe()
    err_read_fd, err_write_fd = os.pipe()
    pid = os.fork()

    # Child:
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

        temp_fd = os.open(os.ttyname(STDOUT_FILENO), os.O_RDWR)
        os.close(temp_fd)

        os.execlp(argv[0], *argv)

    # Parent
    os.close(pty_slave_fd)
    os.close(pipe_read_fd)
    os.close(err_write_fd)

    pipe_in = WritePipe(pipe_write_fd)
    pipe_out = ReadPipe(pty_master_fd, pty=True)
    pipe_err = ReadPipe(err_read_fd)

    return Process(pid, stdin=pipe_in, stdout=pipe_out, stderr=pipe_err)

# Test case:
if __name__ == '__main__':
    import time
    manager = ProcessManager()

    hello = manager.spawn(['echo', 'hello world'])
    print('[hello (blocking)]', hello.stdout.read())

    hello = manager.spawn(['echo', 'hello world'])
    print('[hello (nonblocking)] waiting', end='')
    while True:
        manager.sync()
        new_line = hello.readline()
        if new_line is None:
            print('.', end='')
        else:
            print('\n[hello (nonblocking)]', repr(new_line))
            break

    start = time.time()
    def show(tag, s):
        print(int(time.time()-start),tag,repr(s))

    repeat = manager.spawn(['python3', '/home/ben/Downloads/repeat.py', '3'])
    echo = manager.spawn(['python3', '/home/ben/Downloads/echo.py'])

    while True:
        manager.sync()
        new_text = repeat.readline()
        if new_text is not None:
            show('[repeat]', new_text)
            echo.write(new_text)
        echo_text = echo.readline()
        if echo_text is not None:
            show('[echo]', echo_text)
