from .ear import ThreadedEar

class StdEar(ThreadedEar):
    def write(self, text):
        print(text)
    def connect(self):
        pass
    def main(self):
        while True:
            message = input().strip()
            self.handle_message(user='default', text=message)
