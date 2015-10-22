"""
Filesystem Storage object.
"""
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import os
from .base import BaseStorage, StorageError

from dbbackup import settings


################################
#  Filesystem Storage Object
################################

class Storage(BaseStorage):
    """ Filesystem API Storage. """

    def __init__(self, server_name=None):
        self._check_filesystem_errors()
        self.name = 'Filesystem'
        BaseStorage.__init__(self)

    def _check_filesystem_errors(self):
        """ Check we have all the required settings defined. """
        if not self.backup_dir:
            raise StorageError('Filesystem storage requires DBBACKUP_BACKUP_DIRECTORY to be defined in settings.')

    ###################################
    #  DBBackup Storage Methods
    ###################################
    
    @property
    def backup_dir(self):
        return settings.BACKUP_DIRECTORY

    def delete_file(self, filepath):
        """ Delete the specified filepath. """
        os.unlink(
            os.path.join(self.backup_dir, filepath)
        )

    def list_directory(self):
        """ List all stored backups for the specified. """
        return os.listdir(self.backup_dir)

    def write_file(self, source_file):
        """ Write the specified file. """
        basename = os.path.basename(source_file)
        backuppath = os.path.join(self.backup_dir, basename)

        with open(source_file) as source_handle:
            with open(backuppath, 'wb') as target_handle:
                data = source_handle.read(1024)
                while data:
                    target_handle.write(data)
                    data = source_handle.read(1024)

    def read_file(self, filepath):
        """ Read the specified file and return it's handle. """
        return open(filepath, 'rb')
