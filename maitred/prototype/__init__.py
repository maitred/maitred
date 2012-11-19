import re
import sys
import ast
import time
import importlib

from .. import plumbing

def main():
    if len(sys.argv) == 1:
        config = {'ears': []}
    elif len(sys.argv) == 2:
        with open(sys.argv[1]) as configfile:
            config = ast.literal_eval(configfile.read())
    else:
        print('USAGE: {} [configfile]'.format(sys.argv[0]))

    pm = plumbing.ProcessManager()

    ears = {}
    apps = {}
    vocabs = {}
    auths = {}
    for ear_config in config['ears']:
        ear_module = importlib.import_module(ear_config['module'])
        EarClass = getattr(ear_module, ear_config['class'])

        ear = EarClass(ear_config['settings'])
        ear.connect()

        ear_id = ear_config['id']
        ears[ear_id] = ear

        apps[ear_id] = [pm.spawn(app['argv']) for app in ear_config['apps']]
        vocabs[ear_id] = [re.compile(app['vocab']) for app in ear_config['apps']]
        auths[ear_id] = [app['users'] if 'users' in app else None
                for app in ear_config['apps']]

    while True:
        pm.sync()

        for ear_id, ear in ears.items():
            ear.sync()
            for message in ear:
                print('Got message from {}: {}'.format(message.user,
                    repr(message.text)))
                for vocab, app, auth in zip(vocabs[ear_id], apps[ear_id],
                        auths[ear_id]):
                    if vocab.match(message.text):
                        print('Routing message to app [{}]'.format(vocab.pattern))
                        if (auth is None or message.user in auth):
                            app.write(message.text + '\n')
                            break
                        else:
                            print('User {} not authorized for this '
                                  'app.'.format(message.user))

            for app in apps[ear_id]:
                app_message = app.readline()
                if app_message:
                    print('Got message from app: {}'.format(repr(app_message)))
                    ear.write(app_message)

        time.sleep(0.1)
