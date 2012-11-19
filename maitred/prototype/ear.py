import threading
import collections

Message = collections.namedtuple('Message', ['user', 'text'])

class Ear:
    def __init__(self, config):
        self.config = config
        self.__message_queue = collections.deque()
    def connect(self):
        raise NotImplementedError()
    def sync(self):
        raise NotImplementedError()
    def write(self):
        raise NotImplementedError()
    def handle_message(self, user, text):
        self.__message_queue.append((user, text))
    def __iter__(self):
        return self
    def __next__(self):
        if not self.__message_queue:
            raise StopIteration
        user, text = self.__message_queue.popleft()
        return Message(user=user, text=text)

class ThreadedEar(Ear):
    def main(self):
        raise NotImplementedError()
    def sync(self):
        if not hasattr(self, 'main_thread'):
            self.main_thread = threading.Thread(target=self.main)
            self.main_thread.start()
