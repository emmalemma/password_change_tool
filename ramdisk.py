import subprocess
import threading
from wx.lib.pubsub import pub
import os

class RamDisk(object):
	"""OSX-only ramdrive with file watches"""

	def __init__(self, name="RAM Disk", size=1024*25):
		self.name = name
		self.path = "/Volumes/%s" % name
		self.size = size
		self.watch_timer = None
		self.mount()

	def __del__(self):
		self.unmount()

	def mount(self):
		subprocess.call("diskutil erasevolume HFS+ '%s' `hdiutil attach -nomount -readwrite ram://%d`" % (self.name, self.size), shell=True)
		subprocess.call(["chmod", "ugo+w", self.path])

	def watch(self):
		"""publish any top-level files added to the drive"""
		if self.watch_timer:
			raise Exception("only one watch can be active on a ramdisk")

		self.current_files = set(os.listdir(self.path))
		def check():
			new_files = set(os.listdir(self.path))
			diff = new_files.difference(self.current_files)
			if len(diff) > 0:
				print 'diff', diff
				self.current_files = new_files
				pub.sendMessage('ramdisk.files_added', paths=self.absolute_paths(diff))
			self.watch_timer = threading.Timer(0.5, check)
			self.watch_timer.start()
		check()

	def unwatch(self):
		if self.watch_timer:
			self.watch_timer.cancel()
			self.watch_timer = None


	def unmount(self):
		"""terminate any watches and unmount the drive"""
		self.unwatch()
		subprocess.call(["umount", self.path])

	def absolute_paths(self, names):
		return map(lambda name: os.path.join(self.path, name), list(names))
