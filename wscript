#! /usr/bin/env python
# encoding: utf-8

# Kupfer's main wscript description file for Waf, written by Ulrik Sverdrup
# may be distributed, changed, used, etc freely for any purpose

import os
import sys
try:
	from waflib import Configure, Options, Utils, Logs
except ImportError:
	print("You need to upgrade to Waf 1.6! See README.")
	sys.exit(1)

# the following two variables are used by the target "waf dist"
APPNAME="kupfer"
VERSION = "undefined"

def _get_git_version():
	""" try grab the current version number from git"""
	version = None
	if os.path.exists(".git"):
		try:
			version = os.popen("git describe").read().strip()
		except Exception as e:
			print(e)
	return version

def _read_git_version():
	"""Read version from git repo, or from GIT_VERSION"""
	version = _get_git_version()
	if not version and os.path.exists("GIT_VERSION"):
		with open("GIT_VERSION", "r") as f:
			version = f.read().strip()
	if version:
		global VERSION
		VERSION = version

def _write_git_version():
	""" Write the revision to a file called GIT_VERSION,
	to grab the current version number from git when
	generating the dist tarball."""
	version = _get_git_version()
	if not version:
		return False
	with open("GIT_VERSION", "w") as version_file:
		version_file.write(version + "\n")
	return True


_read_git_version()

# these variables are mandatory ('/' are converted automatically)
top = '.'
out = 'build'

config_subdirs = "auxdata extras help"
build_subdirs = "auxdata data po extras help"

EXTRA_DIST = [
	"waf",
	"GIT_VERSION",
]

def _tarfile_append_as(tarname, filename, destname):
	import tarfile
	tf = tarfile.TarFile.open(tarname, "a")
	try:
		tf.add(filename, destname)
	finally:
		tf.close()

def gitdist(ctx):
	"""Make the release tarball using git-archive"""
	import subprocess
	if not _write_git_version():
		raise Exception("No version")
	basename = f"{APPNAME}-{VERSION}"
	outname = f"{basename}.tar"
	proc = subprocess.Popen(
		["git", "archive", "--format=tar", f"--prefix={basename}/", "HEAD"],
		stdout=subprocess.PIPE,
	)

	fd = os.open(outname, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
	os.write(fd, proc.communicate()[0])
	os.close(fd)
	for distfile in EXTRA_DIST:
		_tarfile_append_as(outname, distfile, os.path.join(basename, distfile))
	subprocess.call(["gzip", outname])
	subprocess.call(["sha1sum", f"{outname}.gz"])

def dist(ctx):
	"The standard waf dist process"
	import Scripting
	_write_git_version()
	Scripting.g_gz = "gz"
	Scripting.dist(ctx)


def options(opt):
	# options for disabling pyc or pyo compilation
	opt.tool_options("python")
	opt.tool_options("gnu_dirs")
	opt.add_option('--nopyo',action='store_false',default=False,help='Do not install optimised compiled .pyo files [This is the default for Kupfer]',dest='pyo')
	opt.add_option('--pyo',action='store_true',default=False,help='Install optimised compiled .pyo files [Default:not install]',dest='pyo')
	opt.add_option('--no-runtime-deps',action='store_false',default=True,
			help='Do not check for any runtime dependencies',dest='check_deps')
	opt.sub_options(config_subdirs)

def configure(conf):
	conf.check_tool("python")
	try:
		conf.check_python_version((2,6,0))
	except Configure.ConfigurationError:
		# with explicitly set python that is not found, we
		# must show an error
		if os.getenv("PYTHON"):
			raise
		conf.env["PYTHON"] = "python2.6"
		conf.check_python_version((2,6,0))
	conf.check_tool("gnu_dirs")

	conf.check_tool("intltool")

	conf.env["KUPFER"] = Utils.subst_vars("${BINDIR}/kupfer", conf.env)
	conf.env["VERSION"] = VERSION
	conf.sub_config(config_subdirs)

	# Setup PYTHONDIR so we install into $DATADIR
	conf.env["PYTHONDIR"] = Utils.subst_vars("${DATADIR}/kupfer", conf.env)
	Logs.pprint("NORMAL",
			"Installing python modules into: %(PYTHONDIR)s" % conf.env)

	opt_build_programs = {
			"rst2man": "Generate and install man page",
		}
	for prog in opt_build_programs:
		try:
			conf.find_program(prog, var=prog.replace("-", "_").upper())
		except conf.errors.ConfigurationError:
			Logs.pprint("YELLOW", f"Optional, allows: {opt_build_programs[prog]}")

	if not Options.options.check_deps:
		return

	python_modules = """
		gio
		gtk
		xdg
		dbus
		"""
	for module in python_modules.split():
		conf.check_python_module(module)

	Logs.pprint("NORMAL", "Checking optional dependencies:")

	opt_programs = {
			"dbus-send": "Focus kupfer from the command line",
		}
	opt_pymodules = {
			"wnck": "Identify and focus running applications",
			"gnome": ("Log out cleanly with session managers *OTHER* than "
				"gnome-session >= 2.24"),
			"keyring": "Required by plugins that save passwords",
		}

	for prog in opt_programs:
		try:
			conf.find_program(prog, var=prog.replace("-", "_").upper())
		except conf.errors.ConfigurationError:
			Logs.pprint("YELLOW", f"Optional, allows: {opt_programs[prog]}")

	try:
		conf.check_python_module("keybinder")
	except Configure.ConfigurationError:
		Logs.pprint("RED", "Python module keybinder is recommended")
		Logs.pprint("RED", "Please see README")

	for mod in opt_pymodules:
		try:
			conf.check_python_module(mod)
		except Configure.ConfigurationError:
			Logs.pprint(
				"YELLOW", f"module {mod} is recommended, allows {opt_pymodules[mod]}"
			)


def _new_package(bld, name):
	"""Add module @name to sources to be installed,
	where the name is the full (relative) path to the package
	"""
	obj = bld.new_task_gen("py")
	node = bld.path.find_dir(name)
	obj.source = node.ant_glob("*.py")
	obj.install_path = "${PYTHONDIR}/%s" % name

	# Find embedded package datafiles
	pkgnode = bld.path.find_dir(name)

	bld.install_files(obj.install_path, pkgnode.ant_glob("icon-list"))
	bld.install_files(obj.install_path, pkgnode.ant_glob("*.png"))
	bld.install_files(obj.install_path, pkgnode.ant_glob("*.svg"))

def _find_packages_in_directory(bld, name):
	"""Go through directory @name and recursively add all
	Python packages with contents to the sources to be installed
	"""
	for dirname, dirs, filenames in os.walk(name):
		if "__init__.py" in filenames:
			_new_package(bld, dirname)

def _dict_slice(D, keys):
	return {k: D[k] for k in keys}

def build(bld):
	# always read new version
	bld.env["VERSION"] = VERSION

	# kupfer/
	# kupfer module version info file
	version_subst_file = "kupfer/version_subst.py"
	bld(
		features="subst",
		source=f"{version_subst_file}.in",
		target=version_subst_file,
		dict=_dict_slice(bld.env, "VERSION DATADIR PACKAGE LOCALEDIR".split()),
	)

	bld.install_files("${PYTHONDIR}/kupfer", "kupfer/version_subst.py")

	bld.new_task_gen(
		source="kupfer.py",
		install_path="${PYTHONDIR}"
		)

	# Add all Python packages recursively
	_find_packages_in_directory(bld, "kupfer")

	# bin/
	# Write in some variables in the shell script binaries
	bld(features="subst",
		source = "bin/kupfer.in",
		target = "bin/kupfer",
		dict = _dict_slice(bld.env, "PYTHON PYTHONDIR".split())
		)
	bld.install_files("${BINDIR}", "bin/kupfer", chmod=0o755)

	bld(features="subst",
		source = "bin/kupfer-exec.in",
		target = "bin/kupfer-exec",
		dict = _dict_slice(bld.env, "PACKAGE LOCALEDIR".split())
		)
	bld.install_files("${BINDIR}", "bin/kupfer-exec", chmod=0o755)

	# Documentation/
	if bld.env["RST2MAN"]:
		# generate man page from Quickstart.rst
		bld.new_task_gen(
			source = "Documentation/Quickstart.rst",
			target = "kupfer.1",
			rule = 'rst2man ${SRC} > ${TGT}',
		)
		bld.add_group()
		# compress and install man page
		manpage = bld.new_task_gen(
			source = "kupfer.1",
			target = "kupfer.1.gz",
			rule = 'gzip -9 -c ${SRC} > ${TGT}',
			install_path = "${MANDIR}/man1",
		)
		man_path = Utils.subst_vars(
				os.path.join(manpage.install_path, manpage.target),
				bld.env)
		bld.symlink_as("${MANDIR}/man1/kupfer-exec.1.gz", man_path)

	# Separate subdirectories
	bld.add_subdirs(build_subdirs)

def intlupdate(util):
	print("You should use intltool-update directly.")
	print("You can read about this in Documentation/Manual.rst")
	print("in the localization chapter!")

def test(bld):
	# find all files with doctests
	python = os.getenv("PYTHON", "python")
	paths = os.popen("grep -lR 'doctest.testmod()' kupfer/").read().split()
	os.putenv("PYTHONPATH", ".")
	all_success = True
	verbose = ("-v" in sys.argv)
	for p in paths:
		print(p)
		cmd = [python, p]
		if verbose:
			cmd.append("-v")
		sin, souterr = os.popen4(cmd)
		sin.close()
		res = souterr.read()
		souterr.close()
		print (res or "OK")
		all_success = all_success and bool(res)
	return all_success

def shutdown(bld):
	pass


