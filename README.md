# btrfssnapraid
## btrfs snapraid auto sync

This is a utility in Python created to workaround the main drawback of [snapraid](https://www.snapraid.it/) and [snapraid-btrfs](https://github.com/automorphism88/snapraid-btrfs): *"After you execute snapraid sync, you loose old versions of files."*
Thanks to [snapper](http://snapper.io/) and btrfs we can workaround this limitation and offer a **pseudo raid5/6 functionality** in snapraid. No need to worry if you `snapraid sync` and a file was accidentally modified. You can recover from that.

## -How?

Before sync, create a btrfs snapshot of data disks.

After sync, create a btrfs snapshot of parity and contents.
Each snapshot has the same snapper description *'snapraidcounter###'* to identify the snapshot sets.

In order for this approach to work we need to have all data, parity and contents in btrfs and have a valid snapper config.
Example `etc/fstab`:
```
btrfs-dir/data1.img /mnt/data1 btrfs noauto,loop,discard,relatime,subvol=data 0 0
/btrfs-dir/data1.img /mnt/data1/.snapshots btrfs noauto,loop,discard,relatime,subvol=snapshots 0 0
/btrfs-dir/data1.img /mnt/contents1 btrfs noauto,loop,discard,relatime,subvol=contents 0 0
/btrfs-dir/data1.img /mnt/contents1/.snapshots btrfs noauto,loop,discard,relatime,subvol=snapshotscontents 0 0
/btrfs-dir/data2.img /mnt/data2 btrfs noauto,loop,discard,relatime,subvol=data 0 0
/btrfs-dir/data2.img /mnt/data2/.snapshots btrfs noauto,loop,discard,relatime,subvol=snapshots 0 0
/btrfs-dir/data2.img /mnt/contents2 btrfs noauto,loop,discard,relatime,subvol=contents 0 0
/btrfs-dir/data2.img /mnt/contents2/.snapshots btrfs noauto,loop,discard,relatime,subvol=snapshotscontents 0 0
/btrfs-dir/parity.img /mnt/parity btrfs noauto,loop,discard,relatime,subvol=parity 0 0
/btrfs-dir/parity.img /mnt/parity/.snapshots btrfs noauto,loop,discard,relatime,subvol=snapshots 0 0
```
I recommend to keep parity and contents in a different subvolumes that are **not** used for anything else.
I prefer the [alternative](https://wiki.archlinux.org/title/Snapper#Suggested_filesystem_layout) .snapshots solution for snapper so my fstab is reflecting that.

## snapraid config

Nothing special here to be done here. Make sure that disk entries are valid, and make sure to exclude .snapshots folder/subvolume as snapraid-btrfs does.
```
1-parity /mnt/parity/snapraid.parity
content /mnt/contents1/snapraid.content
content /mnt/contents2/snapraid.content
data d1 /mnt/data1
data d2 /mnt/data2

exclude *.unrecoverable
exclude /tmp/
exclude /lost+found/
exclude downloads/
exclude appdata/
exclude *.!sync
exclude /.snapshots/
```

## Snapper config

Before you use this tool, make sure that snapper works for all data, contents and parity disks! Each one entry in snapraid entry should have each own config in snapper. Example `snapper list-configs`
```
Config    | Subvolume     
----------+---------------
contents1 | /mnt/contents1
contents2 | /mnt/contents2
data1     | /mnt/data1    
data2     | /mnt/data2    
parity    | /mnt/parity   
```
Since we don't want to clean up very old snapper snapshots manually, we can use timeline cleanup algorithm of snapper to manage snapshots.
**This implies that all snapper configs should have identical settings regarding cleanup and timeline**:

```
# run daily number cleanup
NUMBER_CLEANUP="yes" <- set this to yes for all snapraid disks

# limit for number cleanup <-set these identical for all snapraid disks
NUMBER_MIN_AGE="1800"
NUMBER_LIMIT="50"
NUMBER_LIMIT_IMPORTANT="10"


# create hourly snapshots <-set it to no, because we will generate hourly snapshots via btrfssnapraid
TIMELINE_CREATE="no"

# cleanup hourly snapshots after some time <- yes, we want to delete old snapshots
TIMELINE_CLEANUP="yes"

# limits for timeline cleanup <- the limits should be identical for all disks
TIMELINE_MIN_AGE="1800"
TIMELINE_LIMIT_HOURLY="10"
TIMELINE_LIMIT_DAILY="10"
TIMELINE_LIMIT_WEEKLY="0"
TIMELINE_LIMIT_MONTHLY="10"
TIMELINE_LIMIT_YEARLY="10"
```
You should also follow snapraid-btrfs instruction for non-root [usage.](https://github.com/automorphism88/snapraid-btrfs/tree/master#q-how-do-i-configure-snapper-for-use-with-snapraid-btrfs)

## btrfsnapraid usage:
You need Python 3.12 (not earlier!), snapper, snapraid grep and tail linux utilities installed in $PATH.
```
btrfsnapraid.py [-h] [-c [SNAPRAIDCONFIG]] action [args ...]
positional arguments:
  action                action to execute sync or snapshot counter to operate on, example: sync or 0,1,2,3..
  args                  arguments to pass directly to snapraid, do not specify snapraid conf

options:
  -h, --help            show this help message and exit
  -c [SNAPRAIDCONFIG], --snapraidconfig [SNAPRAIDCONFIG]
                        snapraid conf file, default /etc/snapraid.conf
```
Possible drawbacks of this tool is more use of disk space due to snapshots and snapraid modications. Running btrfs with multiple snapshots can be slow. Maybe using btrfs compress for parity and contents helps?

### how to use on an existing installation of snapraid/snapraid-btrfs:

1. Make sure that your data disks are btrfs. If you already use snapraid-btrfs you should be fine.
2. Copy parity and contents to btrfs subvolumes. Parity must be on different disk than data. Content files can be located to the same disks as data but on different subvolumes.
3. Create snapper configs for data (if they dont exist), parity and contents
4. Make those snapper configs identical regarding timeline, cleanup and users
5. `snapper list-config` should list them all!
6. `snapper -c [diskconfig] ls` should work for all disks!
7. fix snapraid config to reflect the new paths.
8. run snapraid status, no errors should appear.

for new installation follow steps 1-7 and run `snapraid sync` once.
Now you can use btrfsnapraid:

#### Sync
run `btrfsnapraid sync`
You can check if snapper has new snapshots, via `snapper -c [parity] ls`. You should see something like:

```
 # | Type   | Pre # | Date                            | User | Cleanup  | Description       | Userdata
----+--------+-------+---------------------------------+------+----------+-------------------+---------
 0  | single |       |                                 | root |          | current           |         
 1  | single |       |                   date          | root | timeline | snapraidcounter1  |         

```
Now all the snapshots from all disks that have the same description counter (snapraidcounter1) should be snapraid protected!
You can also verify via `btrfsnapraid 0 -- status`. This execute `snapraid status` on all snapraidcounter1 snapshots, not on live filesystem!
You can use the data disks as you wish without worrying if you delete/modify files in data disks. snapraidcounter1 snapshots should exist as long as your timeline algorithm dictates!

**I highly recommend to execute `btrfsnapraid sync` on an hourly basis via cron or systemd timer**
This will ensure that you data are protected. If you need old versions of files, they exist in older snapshots and they are also protected via snapraid!

#### Scrub
No need to run snapraid scrub. All disks are protected via btrfs. btrfs scrub them as you wish. Check for btrfs errors in your devices.
+ If a btrfs error is located:
  - Stop `btrfsnapraid sync` cron job if any!
  - Stop snapper-cleanup service. we don't want snapper to auto delete old snapshots
  - Can I identify the files/snapshots impacted?
    - if yes, run `btrfsnapraid [counter] -- fix` for all snapshots impacted. Snapraid will recover all impacted files.
    - If no, run `btrfssnapraid [counter] -- fix` from newer snapshot to older snapshot. It will take time, but if you don't care for very old snapshots, you can stop after the newest snapshot.

If you are paranoid about data verification you can run `btrfssnapraid [counter] -- scrub -p full` to check what the status of a snapshot.


#### File recovery

1. Stop `btrfsnapraid sync` cron job if any!
2. Stop snapper-cleanup service. we don't want snapper to auto delete old snapshots
3. Use old snapshots to copy files to current disks. Since all data disks are btrfs, you can trust that if corruption exists in old snapshots btrfs will detect it.
If you are paranoid about data verification you can run `btrfssnapraid [counter] -- scrub -p full` to check what the status of a snapshot and then recover/copy the files/directories from it. copy using reflink should preserve disk space.
4. start using btrfsnapraid and snapper-cleanup normally.

#### Disk recovery

+ Stop `btrfsnapraid sync` cron job if any!
+ Stop snapper-cleanup service. we don't want snapper to auto delete old snapshots.
Buy new disk and format it as btrfs. Create subvolumes and snapper config for it.
Verify `snapper list-config` & `snapper -c [diskconfig] ls` work for the new disk. If content files exist there, make sure to create snapper config and subvolumes for them.

Follow snapraid [recovery](https://www.snapraid.it/manual#4.4) without using btrfsnapraid.
We need to fix the latest valid status first.

After we fix the live filesystem, we can start fixing old snapshots like this:
1. list old existing snapraidcounter snapshots, note the existing counters. `snapper -c [good disk] ls`
2. Create snapshots `snapper -c [newdisk] create -c timeline --read-write -d "snapraidcounter[highestcounter]"` and/or `snapper -c [newcontents] create -c timeline --read-write -d "snapraidcounter[highestcounter]"`
3. Recover the old snapshot via `btrfssnapraid [highestcounter] -- fix`
4. fetch the snapper counter of step 3, `snapper -c [good disk] ls`
5. Create snapshots using 'from' argument. This should preserve space and write operations of the recovery. `snapper -c [newdisk] create -c timeline --read-write -d "snapraidcounter[highestcounter-1]" --from [recovered snapshot]` and/or `snapper -c [newcontents] create -c timeline --read-write -d "snapraidcounter[highestcounter-1]" --from [recovered snapshot]`
6. Recover the old snapshot via `btrfssnapraid [highestcounter-1] -- fix`
7. go to step 4, fixing older snapshots via copying newer snapshots.
8. Fix dates of snapper backups manually, by modifying info.xml of each snapshot and copy the date from the same snapraidcounter from good old disk. This will make sure that cleanup will delete correctly older snapshots.
10. start using btrfsnapraid and snapper-cleanup normally. 
