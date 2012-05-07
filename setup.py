from distutils.core import setup

setup(
    name='Django Cherrypy',
    version='0.1dev',
    packages=['django_cherrypy', ],
    license='LICENSE',
    description='cherrypy, running under django',
    long_description=open('README.md').read(),
    author='Calvin Cheng',
    author_email='calvin@calvinx.com',
    install_requires=[],
)
