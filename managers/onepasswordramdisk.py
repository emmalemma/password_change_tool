import json
import os
from urlparse import urlparse
import time
import sys
import subprocess
import wx
from wx.lib.pubsub import pub

import threading, time
import ramdisk
import re

from helpers import SizerPanel, show_error
from models import GlobalState


wildcard = "1Password Interchange File (*.1pif)|*.1pif"
regex = "\.1pif$"

class OnePasswordRamdiskImporter(object):
    def __init__(self, controller):
        self.controller = controller
        GlobalState.onepassword = {}
        pub.subscribe(self.show_import_instructions, "onepassword__show_import_instructions")

    def get_password_data(self):
        self.controller.show_panel(OnePasswordRamdiskReader)

    def save_changes(self, changed_entries):
        self.controller.show_panel(GetOutputLocationPanel, changed_entries=changed_entries)

    def show_import_instructions(self, import_file_path):
        self.controller.show_panel(ImportInstructionsPanel, import_file_path=import_file_path)


class OnePasswordRamdiskReader(SizerPanel):

    def add_controls(self):
        self.add_text("""
            First you'll need to export your passwords from 1Password so we can import them.

            We've created a Secure Storage drive to safely store your passwords while we change them. Your passwords won't be written to disk.

            To export your logins from 1Password, select the items you want to export and go to "File -> Export -> Selected Items ...". Select the Secure Storage drive, and click Save.
         """)
        self.add_button("Open 1Password", None)
        self.ramdisk = ramdisk.RamDisk("Secure Storage")
        self.ramdisk.watch()
        pub.subscribe(self.handle_files, 'ramdisk.files_added')

    def handle_files(self, paths):
        for path in paths:
            if re.search(regex, path):
                self.process_file(path)
                return

    def process_file(self, path):
        time.sleep(1)
        entries = []

        original_path = path
        if os.path.isdir(path):
            path = os.path.join(path, "data.1pif")

        last_entry = None
        with open(path, 'rb') as file:
            for line in file:
                if line.startswith('{'):
                    entry = {
                        'data':json.loads(line)
                    }
                    entries.append(entry)
                    last_entry = entry
                elif line.startswith('***') and last_entry:
                    last_entry['separator_line'] = line
                else:
                    print "Unrecognized line:", line

        if not entries:
            show_error("No password entries were found in that file. Are you sure it is a 1Password interchange file?")
            return

        GlobalState.onepassword['original_path'] = original_path
        GlobalState.default_log_file_path = original_path+".log"

        def set_error(entry):
            entry['error'] = "Entry must have a location, username, and password."

        for entry in entries:
            entry['label'] = entry['data']['title']

            if not 'location' in entry['data'] or not 'secureContents' in entry['data'] or not 'fields' in entry['data']['secureContents']:
                set_error(entry)
                continue

            entry['location'] = entry['data'].get("location", None)
            entry['id'] = entry['data'].get("uuid", None)
            if not entry['location'] or not entry['id']:
                set_error(entry)
                continue

            entry['domain'] = urlparse(entry['location']).netloc
            if not entry['domain']:
                set_error('entry')
                continue

            for field in entry['data']['secureContents']['fields']:
                for target in ('username', 'password'):
                    if field.get('designation', None) == target:
                        entry[target] = field.get('value', None)
                        break

            if not entry.get('username', None) or not entry.get('password', None):
                set_error('entry')
                continue

        GlobalState.logins = entries
        pub.sendMessage("got_password_entries")


class GetOutputLocationPanel(SizerPanel):
    def __init__(self, parent, changed_entries):
        super(GetOutputLocationPanel, self).__init__(parent)
        self.changed_entries = changed_entries

    def add_controls(self):
        self.add_text("""
            Your passwords have been updated. Next you will need to import your new passwords back into 1Password.

            IMPORTANT: This file will contain unencrypted passwords. Save it somewhere safe and delete it once you are done with it.
         """)
        self.add_button("Choose 1Password Export Destination", self.choose_file)

    def choose_file(self, evt):
        default_dir, default_file = os.path.split(GlobalState.onepassword["original_path"])
        default_file = default_file.replace(".1pif", "_reimport.1pif")
        dlg = wx.FileDialog(
            self, message="Choose a file",
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard=wildcard,
            style=wx.SAVE
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.save_file(dlg.GetPath())

    def save_file(self, path):
        epoch_seconds = int(time.time())
        with open(path, 'wb') as out_file:
            for entry in self.changed_entries:
                out = entry['data']
                for field in out['secureContents']['fields']:
                    if field.get('designation', None) == 'password':
                        field['value'] = entry['new_password']
                if not 'passwordHistory' in out:
                    out['passwordHistory'] = []
                out['passwordHistory'].insert(0, {'value':entry['password'], 'time':epoch_seconds})
                out_file.write(json.dumps(out)+"\n"+entry['separator_line'])
        pub.sendMessage("onepassword__show_import_instructions", import_file_path=path)


class ImportInstructionsPanel(SizerPanel):
    def __init__(self, parent, import_file_path):
        super(ImportInstructionsPanel, self).__init__(parent)
        self.import_file_path = import_file_path

    def add_controls(self):
        self.add_text("""
            The last step is to import the file you just saved back into 1Password.

            You can do that manually by going to "File -> Import ...", or we can try to open it for you now:
        """)
        self.add_button("Open file in 1Password", self.open_file)
        self.add_button("All set", self.done)

    def open_file(self, evt):
        path = self.import_file_path
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', path))
        elif os.name == 'nt':
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', path))

    def done(self, evt):
        pub.sendMessage("finished")