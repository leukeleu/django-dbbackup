from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import tarfile
import tempfile
from optparse import make_option
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dbbackup import utils
from dbbackup.storage.base import BaseStorage
from dbbackup.storage.base import StorageError
from dbbackup import settings as dbbackup_settings


class Command(BaseCommand):
    help = "backup_media [--encrypt]"
    option_list = BaseCommand.option_list + (
        make_option("-c", "--clean", help="Clean up old backup files", action="store_true", default=False),
        make_option("-s", "--servername", help="Specify server name to include in backup filename"),
        make_option("-e", "--encrypt", help="Encrypt the backup files", action="store_true", default=False),
    )

    @utils.email_uncaught_exception
    def handle(self, *args, **options):
        try:
            self.servername = options.get('servername')
            self.storage = BaseStorage.storage_factory()

            self.backup_mediafiles(options.get('encrypt'))

            if options.get('clean'):
                self.cleanup_old_backups()

        except StorageError as err:
            raise CommandError(err)

    def backup_mediafiles(self, encrypt):
        source_dir = self.get_source_dir()
        if not source_dir:
            print("No media source dir configured.")
            sys.exit(0)

        temp_dir = tempfile.mkdtemp(prefix='backup')
        try:
            print("Backing up media files in %s" % source_dir)

            output_file = os.path.join(temp_dir, self.get_backup_basename())

            self.create_backup_file(source_dir, output_file)

            if encrypt:
                encrypted_file = utils.encrypt_file(output_file)

                # remove previous file to save disk space
                os.remove(output_file)

                output_file = encrypted_file

            print("  Backup tempfile created: %s (%s)" % (output_file, utils.handle_size(output_file)))
            print("  Writing file to %s: %s" % (self.storage.name, output_file))
            self.storage.write_file(output_file)
        finally:
            shutil.rmtree(temp_dir)

    def get_backup_basename(self):
        return utils.generate_backup_filename(
            self.get_databasename(),
            self.get_servername(),
            'media.tar.gz'
        )

    def get_databasename(self):
        # TODO: WTF is this??
        return settings.DATABASES['default']['NAME']

    def create_backup_file(self, source_dir, archive_file):
        """
        Create an archive of the files in the source dir.
        - backup_basename: name of the archive file
        - archive_file: full path of the archive file
        """
        tar_file = tarfile.open(archive_file, 'w|gz')
        try:
            tar_file.add(source_dir)
        finally:
            tar_file.close()

    def get_source_dir(self):
        return dbbackup_settings.MEDIA_PATH

    def cleanup_old_backups(self):
        """ Cleanup old backups, keeping the number of backups specified by
        DBBACKUP_CLEANUP_KEEP and any backups that occur on first of the month.
        """
        print("Cleaning Old Backups for media files")

        file_list = utils.get_backup_file_list(
            self.get_databasename(),
            self.get_servername(),
            'media.tar.gz',
            self.storage
        )

        for backup_date, filename in file_list[0:-dbbackup_settings.CLEANUP_KEEP_MEDIA]:
            if int(backup_date.strftime("%d")) != 1:
                print("  Deleting: %s" % filename)
                self.storage.delete_file(filename)

    def get_servername(self):
        return self.servername or dbbackup_settings.SERVER_NAME
