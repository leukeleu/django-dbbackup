from setuptools import setup, find_packages

from dbbackup import VERSION


setup(
    name='django-dbbackup',
    version=VERSION,
    description='Management commands to help backup and restore a project database to AmazonS3, Dropbox or local disk.',
    author='Michael Shepanski',
    author_email='mjs7231@gmail.com',
    license='BSD',
    url='http://bitbucket.org/mjs7231/django-dbbackup',
    keywords=['django', 'dropbox', 'database', 'backup', 'amazon', 's3'],
    packages=find_packages()
)
