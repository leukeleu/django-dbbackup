"""
Util functions for dropbox application.
"""
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import sys
import re
from datetime import datetime
from functools import wraps

from django.core.mail import EmailMessage
from django.db import connection
from django.http import HttpRequest
from django.views.debug import ExceptionReporter

from dbbackup import settings


FAKE_HTTP_REQUEST = HttpRequest()
FAKE_HTTP_REQUEST.META['SERVER_NAME'] = ''
FAKE_HTTP_REQUEST.META['SERVER_PORT'] = ''
FAKE_HTTP_REQUEST.META['HTTP_HOST'] = 'django-dbbackup'

BYTES = (
    ('PB', 1125899906842624.0),
    ('TB', 1099511627776.0),
    ('GB', 1073741824.0),
    ('MB', 1048576.0),
    ('KB', 1024.0),
    ('B', 1.0)
)


def bytes_to_str(byteVal, decimals=1):
    """ Convert bytes to a human readable string. """
    for unit, byte in BYTES:
        if (byteVal >= byte):
            if decimals == 0:
                return '%s %s' % (int(round(byteVal / byte, 0)), unit)
            return '%s %s' % (round(byteVal / byte, decimals), unit)
    return '%s B' % byteVal


def handle_size(file_path):
    """ Given a file path return the filesize. """
    with open(file_path, 'rb') as f:
        f.seek(0, 2)
        return bytes_to_str(f.tell())


def email_uncaught_exception(func):
    """ Decorator: Email uncaught exceptions to the SERVER_EMAIL. """
    module = func.__module__
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            if settings.SEND_EMAIL:
                excType, excValue, traceback = sys.exc_info()
                reporter = ExceptionReporter(FAKE_HTTP_REQUEST, excType, 
                    excValue, traceback.tb_next)
                subject = 'Cron: Uncaught exception running %s' % module
                body = reporter.get_traceback_html()
                msgFrom = settings.SERVER_EMAIL
                msgTo = [admin[1] for admin in settings.FAILURE_RECIPIENTS]
                message = EmailMessage(subject, body, msgFrom, msgTo)
                message.content_subtype = 'html'
                message.send(fail_silently=True)
            raise
        finally:
            connection.close()
    return wrapper


def encrypt_file(input_file):
    """ Encrypt the file using gpg. The input and the output are file paths. """
    import gnupg

    output_file = '%s.gpg' % input_file

    with open(input_file, 'rb') as f:
        always_trust = settings.GPG_ALWAYS_TRUST
        g = gnupg.GPG()
        result = g.encrypt_file(f, output=output_file,
            recipients=settings.GPG_RECIPIENT, always_trust=always_trust)
        if not result:
            raise Exception('Encryption failed; status: %s' % result.status)

        return output_file


def generate_backup_filename(databasename, servername, extension):
    """
    Generate filename for backup based on FILENAME_TEMPLATE.
    """
    properties = dict(
        databasename=databasename,
        servername=servername,
        extension=extension,
        datetime=datetime.now().strftime(settings.DATE_FORMAT)
    )

    result = settings.FILENAME_TEMPLATE

    for key, value in properties.items():
        result = result.replace('{%s}' % key, value)

    return result


def get_backup_file_list(database_name, server_name, extension, storage):
    """ Return a list of backup files including the backup date. The result is a list of tuples (datetime, filename).
        The list is sorted by date.
    """
    if server_name:
        server_name = '-%s' % server_name

    backup_re = re.compile(r'^%s%s-(.*)\.%s' % (database_name, server_name, extension.replace('.', '\.')))

    def is_backup(filename):
        return backup_re.search(filename)

    def get_datetime_from_filename(filename):
        datestr = re.findall(backup_re, filename)[0]
        return datetime.strptime(datestr, settings.DATE_FORMAT)

    file_list = [
        (get_datetime_from_filename(f), f)
        for f in storage.list_directory()
        if is_backup(f)
    ]
    return sorted(file_list, key=lambda v: v[0])
