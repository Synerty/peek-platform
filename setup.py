import os
import shutil
from distutils.core import setup

from setuptools import find_packages

package_name = "peek-platform"
package_version = '0.0.7'

egg_info = "%s.egg-info" % package_name
if os.path.isdir(egg_info):
    shutil.rmtree(egg_info)

requirements = [
    # packages used for the platform to test and upgrade it's self
    "pip >= 9.0.0",
    "setuptools >= 18.0.0",
    "virtualenv >= 15.1.0",

    # networking and async framework. Peek is based on Twisted.
    "Cython >= 0.21.1",
    "Twisted[tls,conch] >= 16.0.0",
    "pyOpenSSL >= 16.2.0",
    "pyasn1 >= 0.1.9",
    "pyasn1-modules >= 0.0.8",

    # Database
    "psycopg2 >= 2.6.2",  # PostGreSQL for Linux
    "GeoAlchemy2",  # Geospatial addons to SQLAlchemy
    "Shapely >= 1.5.16",  # Geospatial shape manipulation
    "SQLAlchemy >= 1.0.14",  # Database abstraction layer
    "SQLAlchemy-Utils >= 0.32.9",
    "alembic >= 0.8.7",  # Database migration utility

    # Utilities
    "python-dateutil >= 2.6.0",
    "Pygments >= 2.0.1",  # Generate HTML for code that is syntax styled
    "rx >= 1.5.7", # RxPY by Microsoft. Potentially used in plugins to create Observables.

    # Licensing
    "pycrypto",

    # Celery packages
    "flower",
    # "amqp >= 1.4.9",  # DEPENDENCY LINK BELOW
    "celery[redis,auth]",
    "redis >= 2.10.5",

    # Potitially useful packages
    "GitPython >= 2.0.8",
    "jira",
    "dxfgrabber >= 0.7.4",

    # Synerty packages
    # SOAPpy, used in Twisted, twisted.web.soap is only valid for py2
    "SOAPpy-py3 >= 0.52.24", # See http://soappy.ooz.ie for tutorials
    "wstools-py3 >= 0.54.2",

    "pytmpdir >= 0.1.0",  # A temporary directory, useful for extracting archives to
    "txhttputil >= 0.1.7",  # Utility class for http requests
    "vortexpy >= 0.2.0",  # Data serialisation and transport layer, observable based
    "json-cfg-rw",
    "txsuds-py3",
    "txcelery-py3 >= 1.1.2",

    # Peek platform dependencies, all must match
    "peek-plugin-base",  ##==%s" % package_version,
]

# Packages that are presently installed from a git repo
# See http://stackoverflow.com/questions/17366784/setuptools-unable-to-use-link-from-dependency-links/17442663#17442663
dependency_links = [
    # Celery packages
    # "git+https://github.com/celery/py-amqp#egg=amqp",

]

dev_requirements = [
    "coverage >= 4.2",
    "mock >= 2.0.0",
    "selenium >= 2.53.6",
    "Sphinx >= 1.4.8",
]

setup(
    name=package_name,
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=requirements,
    dependency_links=dependency_links,
    process_dependency_links=True,
    version=package_version,
    description='Peek Platform Common Code',
    author='Synerty',
    author_email='contact@synerty.com',
    url='https://github.com/Synerty/%s' % package_version,
    download_url='https://github.com/Synerty/%s/tarball/%s' % (
        package_name, package_version),
    keywords=['Peek', 'Python', 'Platform', 'synerty'],
    classifiers=[
        "Programming Language :: Python :: 3.5",
    ],
)
