from django.core.management.base import BaseCommand
from django.core.handlers.wsgi import WSGIHandler
import django
from django.conf import settings
from wsgiserver import CherryPyWSGIServer, WSGIPathInfoDispatcher
from optparse import OptionParser, make_option
import os.path, sys
from django_cherrypy.management.commands import runcpserver
from django.contrib.staticfiles.handlers import StaticFilesHandler

runcpserver.CPSERVER_HELP = runcpserver.CPSERVER_HELP.replace('runcpserver', 'runserver_cp')

def start_server_with_admin(options):
    """
    Start CherryPy server
    """

    global SERVER

    if options['daemonize'] == '1' and options['server_user'] and options['server_group']:
        #ensure the that the daemon runs as specified user
        change_uid_gid(options['server_user'], options['server_group'])

    #from cherrypy.wsgiserver import CherryPyWSGIServer as Server
    from wsgiserver import CherryPyWSGIServer as Server
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.servers.basehttp import AdminMediaHandler

    path = django.__path__[0] + '/contrib/admin/media'
    dispatcher = StaticFilesHandler(AdminMediaHandler(WSGIHandler(), path))
    threads = int(options['threads'])
    SERVER = Server(
        (options['host'], int(options['port'])),
        dispatcher,
        numthreads=threads,
        max=threads,
        server_name=options['server_name'],
        verbose=int(options['verbose']),
        shutdown_timeout = int(options['shutdown_timeout']),
        request_queue_size = int(options['request_queue_size'])
    )
    def inner_run():
        print "Validating models..."
        command = Command()
        command.stdout = sys.stdout
        command.validate(display_num_errors=True)

        print 'starting server with options %s' % options
        print "\nDjango version %s, using settings %r" % (django.get_version(), settings.SETTINGS_MODULE)
        print "Development server is running at http://%s:%s/" % (options['host'], options['port'])
        print "Quit the server with <CTRL>+C."
        try:
            SERVER.start()
        except KeyboardInterrupt:
            print 'closing...'
            SERVER.stop()

    from django.utils import autoreload
    autoreload.main(inner_run)


runcpserver.start_server = start_server_with_admin

class Command(BaseCommand):
    option_list = runcpserver.Command.option_list
    help = runcpserver.Command.help
    args = runcpserver.Command.args

    def handle(self, *args, **options):
        runcpserver.Command().execute(*args, **options)

