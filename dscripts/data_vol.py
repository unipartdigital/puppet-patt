#!/usr/bin/python3

"""
data_vol.py
lvm wrapper
detect unused block device to create physical volumes and then a volume group 'data'
inside logical volumes named after the basename of the mount point can be created.
pass the same argument while increasing the size to extend the volume.
example of usage:
./data_vol.py --no_fstab -m /var/lib/test1 -s "2G"
./data_vol.py --no_fstab -m /var/lib/test1 -s "3G"
./data_vol.py --no_fstab -m /var/lib/test3 -s "3G" --extend_full (ignore the size and use all free space)
"""

import subprocess
import json
import pathlib
import tempfile
import os
import sys
import pwd
import argparse
from fcntl import flock,LOCK_EX, LOCK_NB, LOCK_UN

def os_release ():
   os_release_dict = {}
   with open("/etc/os-release") as osr:
      lines=osr.readlines()
      for i in lines:
         if '=' in i:
            k,v=i.split('=',1)
            if k.upper() in ['ID', 'VERSION_ID']:
               v=v.strip()
               if v.startswith('"') and v.endswith('"'):
                  v=v[1:-1].strip()
               os_release_dict[k.upper()]=v
            if 'VERSION_ID' in os_release_dict:
               os_release_dict['MAJOR_VERSION_ID'] = os_release_dict['VERSION_ID'].split('.')[0]
   return os_release_dict

def get_bdev(only_no_child=False):
   result = {}
   lsblk_cmd = subprocess.run(["/bin/lsblk", "-b", "-J"], stdout=subprocess.PIPE)
   if lsblk_cmd.returncode == 0:
      lsblk = json.loads(lsblk_cmd.stdout)
      result = [i for i in lsblk['blockdevices'] if only_no_child * 'children' not in i.keys() and i['type'] == 'disk']
   return result

def dump_bdev(bdev):
   return json.dumps(bdev, indent=1)

def bdev_by_mnt(bdev, mnt=None):
   tmp = bdev[:]
   result = []
   while len(tmp) > 0:
      p=tmp.pop(0)
      if p['mountpoint'] == mnt:
         if mnt is not None: return p
         if 'children' not in p: result.append(p)
      if 'children' in p.keys():
            tmp = tmp + p['children']
   return result

"""
return device list not mounted ordered by size (bigger first)
device with size <= min_size don't show up
"""
def not_mounted_bdev (bdev, all=False, min_size=1073741824):
   result = bdev_by_mnt(bdev, None)
   if all: return result
   return sorted([i for i in result if int(i['size']) >= min_size ], key=lambda k: k['size'], reverse=True)

"""
return False if device can become PV (pvcreate)
"""
def skip_dev_pv (device):
    if not device[0:5] == "/dev/":
        d = "/dev/" + device
    else:
        d = device
    pv_check_cmd = subprocess.run(["pvs", "--report", "json", d],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pv_check_cmd.returncode == 0:
        pv = json.loads(pv_check_cmd.stdout)['report'][0]['pv'][0]
        if pv['vg_name'] == "":
            return False
        return True
    return False

"""
return False if device don't contain a mountable fs, True otherwise
"""
def skip_dev_fs (device):
   result = True
   mntp = tempfile.mkdtemp()
   if not device[0:5] == "/dev/":
      d = "/dev/" + device
   else:
      d = device
   try:
      mount_cmd = subprocess.run(["/bin/mount", d, mntp, "-o", "ro"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      result = mount_cmd.returncode == 0
      if result == 0:
         try:
            luksdump_cmd = subprocess.run(["/sbin/cryptsetup", "luksDump", d],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
         except FileNotFoundError:
            result = True
         except:
            result = False
         else:
            result = luksdump_cmd.returncode == 0
   except:
      pass
   finally:
      try:
         umount_cmd = subprocess.run(["/bin/umount", d],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      except:
         pass
      finally:
         try:
            os.rmdir(mntp)
         except:
            pass
   return result

"""
return list of vg (by name) available on the system
"""
def vg_list():
    vg_list_cmd = subprocess.run(["vgs", "--report", "json"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if vg_list_cmd.returncode == 0:
        vg = json.loads(vg_list_cmd.stdout)['report'][0]['vg'][:]
        return [i['vg_name'] for i in vg]

def volume_data_extend (mnt, created_pv=[], extend_full=False, lv_size="1G", fail=False):
   print ("volume_data_extend")
   d = get_bdev()
   d_mnt = bdev_by_mnt(d, mnt)
   if d_mnt and 'type' in d_mnt and d_mnt['type'] == 'lvm':
      vg,lv = d_mnt['name'].split('-')
      for p in created_pv:
         try:
            vg_extend_cmd = subprocess.run(["/sbin/vgextend", vg, "/dev/{}".format(p['name'])],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if vg_extend_cmd.returncode == 0:
               print (vg_extend_cmd.stdout.decode())
            else:
               print (vg_extend_cmd.stderr.decode(), file=sys.stderr)
               if fail: sys.exit(vg_extend_cmd.returncode)
         except:
            raise

      try:
         if extend_full:
            lv_extend_cmd = subprocess.run(["/sbin/lvextend", "-r", "-l", "100%VG",
                                            "/dev/{}/{}".format(vg,lv)],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
         else:
            lv_extend_cmd = subprocess.run(["/sbin/lvextend", "-r", "-L", lv_size, "/dev/{}/{}".format(vg,lv)],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
         if lv_extend_cmd.returncode == 0:
            print (lv_extend_cmd.stdout.decode())
         else:
            print (lv_extend_cmd.stderr.decode(), file=sys.stderr)
            if fail: sys.exit(lv_extend_cmd.returncode)
      except:
         raise

def volume_data_create (mnt, created_pv=[], extend_full=False, lv_size="1G", fail=False):
   print ("volume_data_create")
   d = get_bdev()
   d_mnt = bdev_by_mnt(d, mnt)
   if not d_mnt:
      vg = "data"
      lv = mnt.split('/')[-1]
      try:
         # vg
         for p in created_pv:
            svg = vg_list()
            if vg not in svg:
               vg_create_cmd = subprocess.run(["/sbin/vgcreate", vg, "/dev/{}".format(p['name'])],
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
               if vg_create_cmd.returncode == 0:
                  print (vg_create_cmd.stdout.decode())
               else:
                  print (vg_create_cmd.stderr.decode(), file=sys.stderr)
                  if fail: sys.exit(vg_create_cmd.returncode)
      except:
         raise
      try:
         if extend_full:
            lv_create_cmd = subprocess.run(["/sbin/lvcreate", "-qq", "-n", lv, "-l", "100%VG", vg],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
         else:
            lv_create_cmd = subprocess.run(["/sbin/lvcreate", "-qq", "-n", lv, "-L", lv_size, vg],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if lv_create_cmd.returncode == 0:
               print (lv_create_cmd.stdout.decode())
            else:
               print (lv_create_cmd.stderr.decode(), file=sys.stderr)
               if fail: sys.exit(lv_create_cmd.returncode)
      except:
         raise

def volume_data_mount_point (mnt, fs="xfs", manage_fstab=True, fstab_uuid=True, fail=False):
   d = get_bdev()
   d_mnt = bdev_by_mnt(d, mnt)
   if d_mnt: return
   vg = "data"
   lv = mnt.split('/')[-1]

   print ("volume_data_mount_point {} {} {} {}".format (vg, lv, mnt, fs))
   if fs == "xfs":
      fs_passno=0
      mkfs = "/sbin/mkfs.xfs"
   else:
      fs = "ext4"
      fs_passno = 2
      mkfs = "/sbin/mkfs.ext4"

   mkfs_cmd = subprocess.run([mkfs, "/dev/{}/{}".format(vg, lv)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   if mkfs_cmd.returncode == 0:
      if not os.path.isdir (mnt):
         pathlib.Path(mnt).mkdir(parents=True, exist_ok=True)
      else:
         print (mkfs_cmd.stderr.decode(), file=sys.stderr)
         if fail: sys.exit(mkfs_cmd.returncode)
   try:
      uuid = None
      fstab_line = None
      mount_cmd = subprocess.run(["/bin/mount", "/dev/{}/{}".format(vg, lv), mnt],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      if mount_cmd.returncode == 0:
         uuid_cmd = subprocess.run(["/sbin/blkid", "/dev/{}/{}".format(vg, lv)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
         if uuid_cmd.returncode == 0:
            print (uuid_cmd.stdout.decode())
            try:
               uuid = [i for i in uuid_cmd.stdout.decode().split() if 'UUID' in i][0]
            except:
               uuid = None
         if fstab_uuid and uuid:
            fstab_line = "{}   {}   {}   defaults   {}   {}".format(
               uuid, mnt, fs, 0, fs_passno)
         else:
            fstab_line = "/dev/mapper/{}-{}   {}   {}   defaults   {} {}".format(
               vg, lv, mnt, fs, 0, fs_passno)
         print (fstab_line)
         keyword = uuid if uuid else "/dev/mapper/{}-{}".format(vg, lv)
         try:
            if manage_fstab:
               keyword_found = False
               with open ("/run/lock/fstab.lock", mode='x') as lock:
                  with open("/etc/fstab", mode="r+") as fstab:
                     for l in fstab.readline():
                        e = l.rstrip().split()
                        if e == keyword:
                           keyword_found = True
                           break
                     if not keyword_found:
                        fstab.seek(0,2)
                        fstab.write(fstab_line + '\n')
         except:
            raise
         finally:
            if os.path.isfile ("/run/lock/fstab.lock"):
               os.unlink("/run/lock/fstab.lock")
   except:
      raise

"""
create vg and lv if necessary
or extend lv if allowed
"""
def init_mount_point (mnt, lv_size='1G', extend_full=False, mkfs="xfs",
                      manage_fstab=True, fstab_uuid=True, fail=False):
   mnt = "{}".format (pathlib.Path(mnt).resolve())
   d = get_bdev()
   d_mnt = bdev_by_mnt(d, mnt)
   created_pv = []

   # init pv
   print ("init pv")
   for n in not_mounted_bdev(d):
      if n:
         try:
            if skip_dev_pv(n['name']):
               continue
            if skip_dev_fs(n['name']):
               continue
            pvcreate_cmd = subprocess.run(["/sbin/pvcreate", "-y", "/dev/{}".format(n['name'])],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if pvcreate_cmd.returncode == 0:
               created_pv.append (n)
               print (pvcreate_cmd.stdout.decode())
            else:
               print (pvcreate_cmd.stderr.decode(), file=sys.stderr)
               if fail: sys.exit(pvcreate_cmd.returncode)
               continue
         except:
            raise

   if (os.path.isdir(mnt) and len(os.listdir(mnt)) == 0) or not os.path.isdir(mnt):
      # create
      volume_data_create (mnt, created_pv=created_pv, extend_full=extend_full, lv_size=lv_size, fail=fail)
      # mount point
      volume_data_mount_point (mnt, fs=mkfs,  manage_fstab=manage_fstab, fstab_uuid=fstab_uuid, fail=fail)
   else:
      # extend
      volume_data_extend (mnt, created_pv=created_pv, extend_full=extend_full, lv_size=lv_size, fail=fail)

if __name__ == "__main__":
   parser = argparse.ArgumentParser()
   parser.add_argument('-m','--mount_point', help='mount point', required=False)
   parser.add_argument('-u','--user_name', help='use <user_name> home dir as mount point', required=False)
   parser.add_argument('-s','--volume_size', help='volume size like 1G, 2G, 1.4T', required=True)
   parser.add_argument('-f','--fs_type', help='file system to use ext4 or xfs', required=False, default="xfs")
   parser.add_argument('--fail', help='exit with error code on first error', action='store_true', required=False)

   parser.add_argument('--lock_dir', help='lock directory', required=False, default="/var/run/lock")

   # on/off
   parser.add_argument('--extend_full',help='use the full vg free space',
                       dest='extend_full', action='store_true')
   parser.set_defaults(extend_full=False)

   parser.add_argument('--fstab', dest='fstab', action='store_true')
   parser.add_argument('--no_fstab', dest='fstab', action='store_false')
   parser.set_defaults(fstab=True)

   parser.add_argument('--fstab_uuid', dest='fstab_uuid', action='store_true')
   parser.add_argument('--no_fstab_uuid', dest='fstab_uuid', action='store_false')
   parser.set_defaults(fstab_uuid=True)

   args = parser.parse_args()
   os.chdir (os.path.dirname (__file__))

   if args.fs_type:
      assert args.fs_type in ['ext4', 'xfs']

   if args.volume_size:
      s = args.volume_size
      idx = None
      for i in range (0, len (args.volume_size)):
         if i == 0 and s[i] == '+' or s[i] == '-': continue
         if s[i] == '.': continue
         if s[i] not in ['1','2','3','4','5','6','7','8','9','0']:
            idx = i
            break
      assert float (s[0:idx])
      assert s[idx:].lower() in ['g', 'gb', 't', 'tb', 'p', 'pb']

   mount_point = None
   if args.user_name:
      try:
         mount_point = pwd.getpwnam(args.user_name).pw_dir
      except KeyError:
         # use well know vendor moutpoint
         osr = os_release()
         if args.user_name == "postgres":
            if osr['ID'] in ['rhel', 'centos', 'fedora']:
               mount_point = "/var/lib/pgsql"
            elif osr['ID'] in ['debian', 'ubuntu']:
               mount_point = "/var/lib/postgresql"
            else:
               raise KeyError
   elif args.mount_point:
      mount_point = args.mount_point

   if mount_point:
      assert mount_point[0] == '/', "mount point must be absolute"
      assert mount_point[-1] != '/', "mount point must have no trailing '/'"

      try:
         lock_filename = args.lock_dir + '/' + os.path.basename (__file__).split('.')[0] + '.lock'
         if not os.path.exists(lock_filename):
            lockf = open(lock_filename, "w+")
            lockf.close()
         lockf = open(lock_filename, "r")
         lock_fd = lockf.fileno()
         flock(lock_fd, LOCK_EX | LOCK_NB)

         init_mount_point (mount_point, lv_size=args.volume_size, extend_full=args.extend_full,
                           mkfs=args.fs_type, manage_fstab=args.fstab, fstab_uuid=args.fstab_uuid,
                           fail=args.fail)
      except:
         raise
      finally:
         flock(lock_fd, LOCK_UN)
         lockf.close()
         try:
            os.remove(lock_filename)
         except OSError:
            pass
