#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  ypkg.py
#
#  Copyright 2015 Ikey Doherty <ikey@solus-project.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
import sys

sys.path.append("/usr/share/ypkg")

import build
import packageit
import subprocess
import shlex
import sanity
from sanity import sane
import os
import shutil
import xml.etree.ElementTree as ET


def load_component(fname):
    try:
        tree = ET.parse(fname)
        root = tree.getroot()

        name = root.findall("Name")[0].text
        return name
    except Exception as e:
        return None


def build_package(tars, fpath, emul32=False):
    build.emul32 = emul32

    if sanity.pkg_extract:
        build.extract(tars)
    else:
        try:
            if not os.path.exists(build.get_build_dir()):
                os.makedirs(build.get_build_dir())
        except Exception as e:
            print "Unable to create build directory: %s" % e
            return False
    try:
        build.build(fpath)
    except Exception as e:
        print "Build failure: %s" % e
        return False
    return True


def main():
    if len(sys.argv) < 2:
        print "Not enough arguments"
        return 1

    fpath = sys.argv[1]
    if not os.path.exists(fpath):
        print "%s does not exist.." % fpath
        return 1
    if not fpath.endswith("package.yml"):
        print "Unnecessarily anal warning: File is not named package.yml"

    if not sane(fpath, True):  # then y made for linoox
        return 1

    if packageit.component is None:
        comp = os.path.join(
            os.path.dirname(
                os.path.abspath(fpath)),
            "..",
            "component.xml")
        if os.path.exists(comp):
            packageit.component = load_component(comp)
        else:
            comp = os.path.join(
                os.path.dirname(
                    os.path.abspath(fpath)),
                "..",
                "..",
                "component.xml")
            if os.path.exists(comp):
                packageit.component = load_component(comp)

    pspec = build.BuildPrefix + "/%s.xml" % sanity.name
    actions = build.BuildPrefix + "/actions.py"

    # Ensure installed

    insList = list()
    if sanity.buildDeps:
        for dep in sanity.buildDeps:
            if not sanity._idb.has_package(dep) and dep not in insList:
                insList.append(dep)
    if len(insList) > 0:
        cmd = "eopkg install %s" % (" ".join(insList))
        if not build.LeRoot:
            cmd = "sudo %s" % cmd
        if "--force" in sys.argv:
            cmd += " -y"
        print "\nInstalling build dependencies...."
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            return ret

    build.cleanup()
    sources = sanity.get_sources()
    tars = build.fetch_source(sources)

    # Emul32 first, so 64-bit can overwrite files
    if sanity.emul32:
        print("Building for 32-bit")
        try:
            if not build_package(tars, fpath, True):
                print("32-bit build failure")
                return 1
        except Exception as e:
            print("32-bit build failure: %s" % e)
            return 1

    try:
        print("Building native package")
        if not build_package(tars, fpath):
            return 1
    except Exception as e:
        print("Native build failure: %s" % e)
        return 1

    packageit.packageit(fpath, build.InstallDir, pspec)
    f = open(actions, "w")
    tmpl = """
import shutil
from pisi.actionsapi import get

def install():
    shutil.move("%s/", get.installDIR())
""" % build.InstallDir

    if not sanity.autodep:
        tmpl += "\nIgnoreAutodep=True\n"
    if not sanity.pkg_strip:
        tmpl += "\nNoStrip = [\"/\"]\n"
    f.writelines(tmpl)
    f.close()

    cmd = "eopkg build --ignore-dependency --ignore-safety %s" % pspec
    if not build.LeRoot:
        cmd = "sudo %s" % cmd
    ret = subprocess.call(shlex.split(cmd), shell=False)
    if ret != 0:
        print "Failed to build package"
        return ret

    try:
        shutil.copy(pspec, "%s/pspec_%s.xml" % (os.getcwd(), build.arch))
    except:
        print "Unable to copy pspec.xml to current directory!"
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
