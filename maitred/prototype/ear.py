import threading
import collections

Message = collections.namedtuple('Message', ['user', 'text'])

class Ear:
    """Base class for an Ear, or chat channel listener."""

    def __init__(self, config):
        self.config = config
        self.__message_queue = collections.deque()

    def connect(self):
        """Connect to the chat channel. (Called once.)"""
        raise NotImplementedError()

    def sync(self):
        """Get updates from the channel. (Called repeatedly.)"""
        raise NotImplementedError()

    def write(self, text):
        """Send a message back to the channel."""
        raise NotImplementedError()

    def handle_message(self, user, text):
        """Handle a message from the channel."""
        self.__message_queue.append((user, text))

    # Support "for message in ear" construction
    def __iter__(self):
        return self
    def __next__(self):
        if not self.__message_queue:
            raise StopIteration
        user, text = self.__message_queue.popleft()
        return Message(user=user, text=text)

class ThreadedEar(Ear):
    def main(self):
        """Blocking main function. (Called once in thread.)"""
        raise NotImplementedError()
    def sync(self):
        # Spawn a thread containing the main() function.
        if not hasattr(self, 'main_thread'):
            self.main_thread = threading.Thread(target=self.main)
            self.main_thread.start()
