#!/usr/bin/python3
import re,os,subprocess,sys,argparse,tempfile

configdict={}
datadict={}

def command(argument):
    #print(argument)
    try:
      data=subprocess.run(argument,capture_output=True,shell=True,check=True)
      #print(data.stdout.decode())
      return data.stdout.decode()
    except:
      raise

#function to find the maximum commonpath between snapraid.conf entry and
#snapper configs
def findmaxcommonpath(diction,data):
    for path in diction:
        length=0
        config=""
        for line in data.splitlines():
            datum=line.strip()
            if m := re.match(r"(?P<config>\S+)\s*\|\s*(?P<path>\S+)\s*",datum):
                #print(path,m.group('path'))
                try:
                    commonpath = os.path.commonpath([m.group('path'), path])
                    if len(commonpath) > length:
                        length=len(commonpath)
                        config=m.group('config')
                except:
                    pass
        if config=="":
            print("ABORT due to snapper config missing: "+path)
            sys.exit(2)
        diction[path].append(config)
        diction[path].append(length)


def readconfigs(configfile):
    with open(configfile) as snapraidconf:
        for line in snapraidconf:
            datum=line.strip()
            #support parity split in multiple files
            if m := re.match(r"(?P<parity>\d*-?parity)\s*(?P<path>.*)",datum):
                pathlist=m.group('path').split(",")
                for path in pathlist:
                    configdict[path]=[m.group('parity')]
            if m := re.match(r"(?P<content>content)\s*(?P<path>.*)",datum):
                configdict[m.group('path')]=[m.group('content')]
            if m := re.match(r"data\s*(?P<name>\S*)\s*(?P<path>.*)",datum):
                datadict[m.group('path')]=[m.group('name')]

    #print(configdict)
    #print(datadict)

    data=command("snapper list-configs")

    findmaxcommonpath(configdict,data)

    #print(configdict)
    #print(datadict)

    findmaxcommonpath(datadict,data)

    #print(configdict)
    #print(datadict)

def snapraidtemp(configfile,replacepathdict,snapraidcommand):
    with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
        with open(configfile) as snapraidconf:
            for line in snapraidconf:
                datum=line.strip()
                #print(datum)
                #support parity split in multiple files
                if m := re.match(r"(?P<parity>\d*-?parity)\s*(?P<path>.*)",datum):
                    pathlist=m.group('path').split(",")
                    newpath=""
                    for path in pathlist:
                        try:
                            newpath+=(replacepathdict[path]+',')
                        except:
                            newpath+=(path+',')
                    newpath=newpath[:-1]
                    fp.write((m.group('parity')+" "+newpath+'\n').encode('utf-8'))
                elif m := re.match(r"(?P<content>content)\s*(?P<path>.*)",datum):
                    #print(datum)
                    newpath=""
                    try:
                       newpath+=replacepathdict[m.group('path')]
                    except:
                       newpath+=m.group('path')
                    #newpath=newpath[:-1]
                    fp.write((m.group('content')+" "+newpath+'\n').encode('utf-8'))
                elif m := re.match(r"data\s*(?P<name>\S*)\s*(?P<path>.*)",datum):
                    newpath=""
                    try:
                       newpath+=replacepathdict[m.group('path')]
                    except:
                       newpath+=m.group('path')
                    #newpath=newpath[:-1]
                    fp.write(("data "+m.group('name')+" "+newpath+'\n').encode('utf-8'))
                else:
                    fp.write((datum+'\n').encode('utf-8'))
        fp.close()
        #print(fp.name)
        print("using this snapraid config")
        print(command("cat "+fp.name))
        print(command(snapraidcommand+" -c "+fp.name))

def findlastsnapraidcounter():
    counter=0
    for path in datadict:
        data = command("snapper -c "+datadict[path][1]+" list -t single --columns number,description | grep snapraidcounter | tail -n 1")
        for line in data.splitlines():
            datum=line.strip()
            if m := re.match(r"(?P<snapshot>\d+).*snapraidcounter(?P<counter>\d+).*",datum):
                return int(m.group('counter'))
    return counter

def newsync(configfile):
    try:
        data=command("snapraid diff -c "+configfile)
        print("No sync needed, exit")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        if e.returncode != 2:
            raise
    print("Must sync")
    counter = findlastsnapraidcounter()+1
    #create new snapshots for data drives
    for path in datadict:
        command('snapper -c '+datadict[path][1]+' create -c timeline --read-write -d "snapraidcounter'+str(counter)+'"')
    replacepaths=createoldmapping(counter,True)
    snapraidtemp(configfile,replacepaths,"snapraid sync")
    #create snapshots for parity and contents
    for path in configdict:
        command('snapper -c '+configdict[path][1]+' create -c timeline --read-write -d "snapraidcounter'+str(counter)+'"')

def createoldmapping(snapraidcounter,skip_configdict):
    replacepathdict={}
    for path in datadict:
        data = command("snapper -c "+datadict[path][1]+" list -t single --columns number,description | grep snapraidcounter" + str(snapraidcounter))
        length=datadict[path][2]
        for line in data.splitlines():
            datum=line.strip()
            if m := re.match(r"(?P<snapshot>\d+).*snapraidcounter(?P<counter>\d+).*",datum):
                if int(m.group('counter')) == snapraidcounter:
                    replacepathdict[path]=path[:length]+"/.snapshots/"+m.group('snapshot')+"/snapshot/"+path[length:]
    if not skip_configdict:
        for path in configdict:
            data = command("snapper -c "+configdict[path][1]+" list -t single --columns number,description | grep snapraidcounter" + str(snapraidcounter))
            length=configdict[path][2]
            for line in data.splitlines():
                datum=line.strip()
                if m := re.match(r"(?P<snapshot>\d+).*snapraidcounter(?P<counter>\d+).*",datum):
                    if int(m.group('counter')) == snapraidcounter:
                        replacepathdict[path]=path[:length]+"/.snapshots/"+m.group('snapshot')+"/snapshot/"+path[length+1:]
    return replacepathdict

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", help="action to execute sync or instance to operate on, example: sync or 0,1,2,3..")
    parser.add_argument("-c","--snapraidconfig", nargs='?',help="snapraid conf file, default /etc/snapraid.conf",default="/etc/snapraid.conf")
    parser.add_argument('args',nargs='*',help="arguments to pass directly to snapraid, do not specify snapraid conf")
    args=parser.parse_args()
    #load snapraid config into memory for further use
    readconfigs(args.snapraidconfig)
    #Do I want to execute my sync or a classic snapraid operation?
    if args.action == "sync":
        newsync(args.snapraidconfig)
    else:
        instance=int(args.action)
        if instance==0:
            snapraidtemp(args.snapraidconfig,dict(),"snapraid "+" ".join(args.args))
        else:
            replacepaths=createoldmapping(int(args.action),False)
            snapraidtemp(args.snapraidconfig,replacepaths,"snapraid "+ " ".join(args.args))

if __name__ == "__main__":
    main()
