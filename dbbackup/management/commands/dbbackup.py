"""
Save backup files to Dropbox.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import shutil
import tempfile
import gzip
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.management.base import LabelCommand

from dbbackup import utils
from dbbackup.dbcommands import DBCommands
from dbbackup.storage.base import BaseStorage
from dbbackup.storage.base import StorageError
from dbbackup import settings as dbbackup_settings


class Command(LabelCommand):
    help = "dbbackup [-c] [-d <dbname>] [-s <servername>] [--compress] [--encrypt]"
    option_list = BaseCommand.option_list + (
        make_option("-c", "--clean", help="Clean up old backup files", action="store_true", default=False),
        make_option("-d", "--database", help="Database to backup (default: everything)"),
        make_option("-x", "--backup-extension", help="The extension to use when saving backups."),
        make_option("-s", "--servername", help="Specify server name to include in backup filename"),
        make_option("-z", "--compress", help="Compress the backup files", action="store_true", default=False),
        make_option("-e", "--encrypt", help="Encrypt the backup files", action="store_true", default=False),
    )

    @utils.email_uncaught_exception
    def handle(self, **options):
        """ Django command handler. """
        try:
            self.clean = options.get('clean')
            self.clean_keep = getattr(settings, 'DBBACKUP_CLEANUP_KEEP', 10)
            self.database = options.get('database')
            self.servername = options.get('servername') or dbbackup_settings.SERVER_NAME
            self.backup_extension = options.get('backup-extension') or None
            self.compress = options.get('compress')
            self.encrypt = options.get('encrypt')
            self.storage = BaseStorage.storage_factory()
            if self.database:
                database_keys = self.database,
            else:
                database_keys = dbbackup_settings.DATABASES
            for database_key in database_keys:
                database = settings.DATABASES[database_key]
                database_name = database['NAME']

                self.dbcommands = DBCommands(database)
                self.save_new_backup(database_name)

                if self.clean:
                    self.cleanup_old_backups(database_name)
        except StorageError as err:
            raise CommandError(err)

    def save_new_backup(self, database_name):
        """ Save a new backup file. """
        print("Backing Up Database: %s" % database_name)

        temp_dir = tempfile.mkdtemp(prefix='backup')
        try:
            backup_extension = self.backup_extension or self.dbcommands.settings.extension

            backup_file = os.path.join(
                temp_dir,
                utils.generate_backup_filename(database_name, self.servername, backup_extension)
            )

            with open(backup_file, 'wb') as f:
                self.dbcommands.run_backup_commands(f)

            if self.compress:
                backup_file = self.compress_file(backup_file)

            if self.encrypt:
                backup_file = utils.encrypt_file(backup_file)

            print("  Backup tempfile created: %s" % (utils.handle_size(backup_file)))
            print("  Writing file to %s: %s" % (self.storage.name, backup_file))

            self.storage.write_file(backup_file)
        finally:
            shutil.rmtree(temp_dir)

    def cleanup_old_backups(self, database_name):
        """ Cleanup old backups, keeping the number of backups specified by
            DBBACKUP_CLEANUP_KEEP and any backups that occur on first of the month.
        """
        print("Cleaning Old Backups for: %s" % database_name)

        file_list = utils.get_backup_file_list(
            database_name,
            self.servername,
            self.dbcommands.settings.extension,
            self.storage
        )

        for backup_date, filename in sorted(file_list[0:-self.clean_keep]):
            if int(backup_date.strftime("%d")) != 1:
                print("  Deleting: %s" % filename)
                self.storage.delete_file(filename)

    def compress_file(self, input_path):
        """ Compress this file using gzip.
            The input and the output are paths.
        """
        output_path = input_path + '.gz'

        with open(output_path, 'wb') as output_f:
            zipfile = gzip.GzipFile(fileobj=output_f, mode="wb")

            try:
                with open(input_path) as input_f:
                    zipfile.write(input_f.read())
            finally:
                zipfile.close()

        return output_path
