import re
import time

from .. import plumbing

EAR_CMD = ['python', 'maitred/prototype/ircear.py']
APP_CFG = [
    ('ping', ['python', 'maitred/prototype/pongapp.py']),
    ('what', ['python', 'maitred/prototype/whatapp.py']),
]

def main():
    pm = plumbing.ProcessManager()

    ear = pm.spawn(EAR_CMD)

    apps = [pm.spawn(cmd) for vocab, cmd in APP_CFG]
    vocabs = [re.compile(vocab) for vocab, cmd in APP_CFG]

    while True:
        pm.sync()

        ear_message = ear.readline()
        if ear_message:
            print('Got message from ear: {}'.format(repr(ear_message)))
            for vocab, app in zip(vocabs, apps):
                if vocab.match(ear_message):
                    print('Routing message to app [{}]'.format(vocab.pattern))
                    app.write(ear_message)

        for app in apps:
            app_message = app.readline()
            if app_message:
                print('Got message from app: {}'.format(repr(app_message)))
                ear.write(app_message)

        time.sleep(0.1)
