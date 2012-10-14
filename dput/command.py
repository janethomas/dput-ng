# -*- coding: utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

# Copyright (c) 2012 dput authors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import abc
import os
import tempfile
import time

import dput.profile
from dput.util import get_obj, get_configs
from dput.core import logger
from dput.exceptions import UploadException, DputConfigurationError, DcutError
from dput.overrides import force_passive_ftp_upload
from dput.uploader import uploader

class AbstractCommand(object):
    """
    Abstract base class for all concrete dcut command implementations.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.cmd_name = None
        self.cmd_purpose = None

    @abc.abstractmethod
    def register(self, parser, **kwargs):
        pass

    @abc.abstractmethod
    def produce(self, fh, args):
        pass

    @abc.abstractmethod
    def validate(self, args):
        pass

    @abc.abstractmethod
    def name_and_purpose(self):
        pass


def find_commands():
    return get_configs('commands')


# XXX: This function could be refactored over to dput. There a *very*
# similar function exists.
def load_commands():
    commands = []
    for command in find_commands():
        logger.debug("importing command: %s" % (command))
        obj = get_obj('commands', command)
        if obj is None:
            raise DputConfigurationError("No such checker: `%s'" % (
                command
            ))
        commands.append(obj())
    return commands


def write_header(fh, profile, args):
    email = os.environ["DEBEMAIL"]
    if not email:
        os.environ["EMAIL"]
    name = os.environ["DEBFULLNAME"]

    # TODO: parse gecos?
    logger.debug("Using %s <%s> as uploader identity" % (name, email))

    if not name or not email:
        raise DcutError("Your name or email could not be retrieved."
                        "Please set DEBEMAIL and DEBFULLNAME.")

    fh.write("Archive: %s\n" % (profile['fqdn']))
    fh.write("Uploader: %s <%s>\n\n" % (name, email))


def generate_commands_name(profile):
    # should be $login-$timestamp.dak[.-]commands
    the_file = "%s-%s.dak.commands" % (os.getlogin(), int(time.time()))
    return the_file

def invoke_dcut(args):
    profile = dput.profile.load_profile(args.host)

    fqdn = None
    if 'fqdn' in profile:
        fqdn = profile['fqdn']

    if not 'allow_dcut' in profile or not profile['allow_dcut']:
        raise UploadException("Profile %s does not allow command file uploads"
                              "Please set allow_dcut=1 to allow such uploads")

    logger.info("Uploading commands file to %s (incoming: %s)" % (
        fqdn or profile['name'],
        profile['incoming']
    ))

    if args.simulate:
        logger.warning("Not uploading for real - dry run")

    command = args.command
    assert(issubclass(type(command), AbstractCommand))
    command.validate(args)

    # XXX: Checkers for dcut?
    #if 'checkers' in profile:
    #    for checker in profile['checkers']:
    #        logger.trace("Running check: %s" % (checker))
    #        run_checker(checker, changes, profile)
    #else:
    #    logger.trace(profile)
    #    logger.warning("No checkers defined in the profile. "
    #                   "Not checking upload.")

    try:
        if command.cmd_name == "upload":
            raise DcutError("Cry! Cry! Cry! Such a fugly hack")
        else:
            fh = tempfile.NamedTemporaryFile(mode='w+r', delete=True)
            write_header(fh, profile, args)
            command.produce(fh, args)
            fh.flush()
            #print fh.name

            upload_filename = generate_commands_name(profile)

            with uploader(profile['method'], profile) as obj:
                logger.info("Uploading %s to %s" % (
                                                    upload_filename,
                                                    profile['name']
                                                    ))
                if not args.simulate:
                    obj.upload_file(fh.name, upload_filename=upload_filename)

    finally:
        fh.close()

    if args.passive:
        force_passive_ftp_upload(profile)

