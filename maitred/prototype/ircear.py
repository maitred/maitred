from time import sleep
from threading import Thread

from oyoyo.client import IRCClient
from oyoyo.cmdhandler import DefaultCommandHandler
from oyoyo import helpers

HOST = 'irc.freenode.net'
PORT = 6667
NICK = 'maitred'
CHANNEL = '#maitred'

class Ear(DefaultCommandHandler):
    def privmsg(self, nick, chan, msg):
        msg = msg.decode()
        print(msg)

def join_channel(cli):
    helpers.join(cli, CHANNEL)

if __name__ == '__main__':
    cli = IRCClient(Ear, host=HOST, port=PORT, nick=NICK,
            connect_cb=join_channel)
    conn = cli.connect()

    class Listen(Thread):
        def run(self):
            while True:
                next(conn)
                sleep(0.1)
    Listen().start()

    while True:
        msg = input().strip()
        helpers.msg(cli, CHANNEL, msg)
