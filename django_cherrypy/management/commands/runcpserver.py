#!/usr/bin/env python

#import logging
import sys
import os
import signal
import time
import errno
#from socket import gethostname
from django.core.management.base import BaseCommand
#from pprint import pprint


CPSERVER_HELP = r"""
  Run this project in a CherryPy webserver. To do this, CherryPy from
  http://www.cherrypy.org/ is required.

   runcpserver [options] [cpserver settings] [stop]

Optional CherryPy server settings: (setting=value)
  host=HOSTNAME         hostname to listen on
                        Defaults to localhost
  port=PORTNUM          port to listen on
                        Defaults to 8088
  server_name=STRING    CherryPy's SERVER_NAME environ entry
                        Defaults to localhost
  daemonize=0|1        whether to detach from terminal
                        Defaults to 0 (False)
  pidfile=FILE          write the spawned process-id to this file
  workdir=DIRECTORY     change to this directory when daemonizing
  threads=NUMBER        Number of threads for server to use
  ssl_certificate=FILE  SSL certificate file
  ssl_private_key=FILE  SSL private key file
  server_user=STRING    user to run daemonized process
                        Defaults to www-data
  server_group=STRING   group to daemonized process
                        Defaults to www-data
  verbose=0|1           print the request path (default 0)
  shutdown_timeout=NUMBER      grace period for allowing current requests to be processed (default 60)
  request_queue_size=NUMBER    maximum number of queued connections (default 5)

Examples:
  Run a "standard" CherryPy server
    $ manage.py runcpserver

  Run a CherryPy server on port 80
    $ manage.py runcpserver port=80

  Run a CherryPy server as a daemon and write the spawned PID in a file
    $ manage.py runcpserver daemonize=true pidfile=/var/run/django-cpserver.pid

"""

CPSERVER_OPTIONS = {
    'host': 'localhost',
    'port': 8000,
    'server_name': 'localhost',
    'threads': 10,
    'daemonize': 0,
    'workdir': None,
    'pidfile': None,
    'server_user': 'www-data',
    'server_group': 'www-data',
    'ssl_certificate': None,
    'ssl_private_key': None,
    'verbose': 1,
    'shutdown_timeout': 60,
    'request_queue_size': 5,
}

SERVER = None


class Command(BaseCommand):
    help = "CherryPy Server for project. Requires CherryPy."
    args = "[various KEY=val options, use `runcpserver help` for help]"

    def handle(self, *args, **options):
        from django.conf import settings
        from django.utils import translation
        # Activate the current language, because it won't get activated later.
        try:
            translation.activate(settings.LANGUAGE_CODE)
        except AttributeError:
            pass
        runcpserver(*args)

    def usage(self, subcommand):
        return CPSERVER_HELP


def change_uid_gid(uid, gid=None):
    """Try to change UID and GID to the provided values.
    UID and GID are given as names like 'nobody' not integer.

    Src: http://mail.mems-exchange.org/durusmail/quixote-users/4940/1/
    """
    if not os.geteuid() == 0:
        # Do not try to change the gid/uid if not root.
        return
    (uid, gid) = get_uid_gid(uid, gid)
    os.setgid(gid)
    os.setuid(uid)


def get_uid_gid(uid, gid=None):
    """Try to change UID and GID to the provided values.
    UID and GID are given as names like 'nobody' not integer.

    Src: http://mail.mems-exchange.org/durusmail/quixote-users/4940/1/
    """
    import pwd
    import grp
    uid, default_grp = pwd.getpwnam(uid)[2:4]
    if gid is None:
        gid = default_grp
    else:
        try:
            gid = grp.getgrnam(gid)[2]
        except KeyError:
            gid = default_grp
    return (uid, gid)


def poll_process(pid):
    """
    Poll for process with given pid up to 10 times waiting .25 seconds in between each poll.
    Returns False if the process no longer exists otherwise, True.
    """
    for n in range(10):
        time.sleep(0.25)
        try:
            # poll the process state
            os.kill(pid, 0)
        except OSError, e:
            if e[0] == errno.ESRCH:
                # process has died
                return False
            else:
                raise  # TODO
    return True


def stop_server(pidfile):
    """
    Stop process whose pid was written to supplied pidfile.
    First try SIGTERM and if it fails, SIGKILL. If process is still running, an exception is raised.
    """
    if SERVER:
        SERVER.stop()

    if os.path.exists(pidfile):
        pid = int(open(pidfile).read())
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:  # process does not exist
            os.remove(pidfile)
            return
        if poll_process(pid):
            #process didn't exit cleanly, make one last effort to kill it
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                print "Process {0} did not stop.".format(pid)
                raise
        os.remove(pidfile)


def start_server(options):
    """
    Start CherryPy server
    """

    global SERVER

    try:
        import newrelic.agent
        PATH_TO_NEWRELIC = os.path.join(os.getcwd(), 'newrelic.ini')
        newrelic.agent.initialize(PATH_TO_NEWRELIC)
    except:
        print "To run cherrypy instances with newrelic,"
        print "(1)  pip install newrelic"
        print "(2) newrelic-admin generate-config [YOUR_API_KEY] newrelic.ini"
        print "continuing runcpserver without newrelic..."
        pass

    print 'starting server with options %s' % options
    if options['daemonize'] == '1' and options['server_user'] and options['server_group']:
        #ensure the that the daemon runs as specified user
        change_uid_gid(options['server_user'], options['server_group'])

    #from cherrypy.wsgiserver import CherryPyWSGIServer as Server
    from wsgiserver import CherryPyWSGIServer as Server
    from django.core.handlers.wsgi import WSGIHandler
    threads = int(options['threads'])
    SERVER = Server(
        (options['host'], int(options['port'])),
        WSGIHandler(),
        numthreads = threads,
        max = threads,
        server_name = options['server_name'],
        verbose = int(options['verbose']),
        shutdown_timeout = int(options['shutdown_timeout']),
        request_queue_size = int(options['request_queue_size'])
    )
    #if options['ssl_certificate'] and options['ssl_private_key']:
        #server.ssl_certificate = options['ssl_certificate']
        #server.ssl_private_key = options['ssl_private_key']
    try:
        SERVER.start()
        #from django.utils import autoreload
        #autoreload.main(server.start)
    except KeyboardInterrupt:
        SERVER.stop()


def runcpserver(*args):
    # Get the options
    options = CPSERVER_OPTIONS.copy()
    for arg in args:
        if '=' in arg:
            k, v = arg.split('=', 1)
            options[k] = v

    if "help" in args:
        print CPSERVER_HELP
        return

    if "stop" in args:
        stop_server(options['pidfile'])
        return True

    if options['daemonize'] == '1':
        if not options['pidfile']:
            options['pidfile'] = '/var/run/cpserver_%s.pid' % options['port']
        stop_server(options['pidfile'])

        from django.utils.daemonize import become_daemon
        if options['workdir']:
            become_daemon(our_home_dir=options['workdir'])
        else:
            become_daemon()

        fp = open(options['pidfile'], 'w')
        fp.write("%d\n" % os.getpid())
        fp.close()

    # Start the webserver
    start_server(options)


if __name__ == '__main__':
    runcpserver(sys.argv[1:])
