from .ear import Ear

from oyoyo.client import IRCClient
from oyoyo.cmdhandler import DefaultCommandHandler
from oyoyo import helpers

class IrcEar(Ear):
    def write(self, text):
        helpers.msg(self.client, self.config['channel'], text)
    def connect(self):
        class Handler(DefaultCommandHandler):
            def privmsg(self_handler, nick, chan, msg):
                user = nick.decode().split('!')[0]
                text = msg.decode()
                self.handle_message(user, text)
        def connectcb(client):
            helpers.join(client, self.config['channel'])
        self.client = IRCClient(Handler, host=self.config['host'],
                port=self.config['port'], nick=self.config['nick'],
                connect_cb=connectcb)
        self.connection = self.client.connect()
    def sync(self):
        next(self.connection)

if __name__ == '__main__':
    import time
    config = {
        'host': 'irc.freenode.net',
        'port': 6667,
        'nick': 'maitred',
        'channel': '#maitred',
    }
    ear = IrcEar(config)
    ear.connect()
    while True:
        ear.sync()

        for message in ear:
            print('[message from {}]'.format(message.user))
            print(repr(message.text))
            print('[end message]')

        time.sleep(0.1)
