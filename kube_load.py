#!/usr/bin/python3
from kubernetes import client, config
import threading, time
import sys
import json
import yaml
import subprocess
import os
import filecmp
import psutil
from shutil import copyfile

config.load_kube_config()
client.Configuration().assert_hostname=False
client.Configuration().verify_ssl=False
v1=client.CoreV1Api()


def check_pid(pid):        
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def gen_haproxy():
    print("Generating HAproxy Config")
    applist = []
    iplist = []
    appgroup = []
    
    configFile = '/etc/cubyte/12app/haproxy_new.cfg'
    ret = v1.list_pod_for_all_namespaces(watch=False)
    srv = v1.list_service_for_all_namespaces(watch=False)

    open(configFile, 'w')

    file = open(configFile,"a")
    file.write("frontend webfront\n")
    file.write("   bind *:80\n")
    file.write("   stats uri /haproxy?stats\n")
    file.write("\n")

    for i in srv.items:
        if not "kube" in i.metadata.name:
             if i.metadata.labels['app'] == i.metadata.name:
                 domain = i.metadata.annotations['domain']
                 file.write("   acl %s_URL hdr_dom(host) -i %s\n" % (domain, domain))
    file.write("\n")
    for i in srv.items:
        if not "kube" in i.metadata.name:
             if i.metadata.labels['app'] == i.metadata.name:
                 domain = i.metadata.annotations['domain']
                 file.write("   use_backend %s_back if %s_URL\n" % (domain, domain))
    file.write("\n")

    number = 0

    for i in srv.items:
        if not "kube" in i.metadata.name:
            if i.metadata.labels['app'] == i.metadata.name:
                 domain = i.metadata.annotations['domain']
                 file.write("backend %s_back\n" % domain)
                 file.write("   balance roundrobin\n")
                 file.write("\n")
                 iploop = 0
                 for x in ret.items:
                     if x.metadata.namespace == "default":
                         if x.metadata.labels['app'] == i.metadata.name:
                             file.write("   server kuber%s%s %s:80 check\n" % (number, iploop, x.status.pod_ip))
                     iploop = iploop + 1
        number = number + 1      

def check_haproxy():
    gen_haproxy()
    print("Checking if new config is different than the current running config.")
    haproxyPID = '/var/run/haproxy.pid'

    if os.path.isfile(haproxyPID):
        with open(haproxyPID, 'r') as myfile:
            pidstr=myfile.read().replace('\n', '')
        pid = int(pidstr)
        run_pid = check_pid(pid)
        if run_pid:
            checkfile = filecmp.cmp('/etc/cubyte/12app/haproxy_new.cfg', '/etc/cubyte/12app/haproxy.cfg')
            if checkfile is False:
                copyfile("/etc/cubyte/12app/haproxy_new.cfg", "/etc/cubyte/12app/haproxy.cfg")
                print("Reloading Haproxy")
                step1 = ['haproxy', '-f', '/etc/haproxy/haproxy.cfg', '-f', '/etc/cubyte/12app/haproxy.cfg', '-p', '/var/run/haproxy.pid', '-sf', pid]
                s1 = subprocess.Popen(step1, stdout=subprocess.PIPE).stdout
            else:
                print("File is the same")
        else:
            print("Starting HAproxy")
            step1 = ['haproxy', '-f', '/etc/haproxy/haproxy.cfg', '-f', '/etc/cubyte/12app/haproxy.cfg', '-p', '/var/run/haproxy.pid']
            s1 = subprocess.Popen(step1, stdout=subprocess.PIPE).stdout
    else:
        print("Starting HAproxy")
        step1 = ['haproxy', '-f', '/etc/haproxy/haproxy.cfg', '-f', '/etc/cubyte/12app/haproxy.cfg', '-p', '/var/run/haproxy.pid']
        s1 = subprocess.Popen(step1, stdout=subprocess.PIPE).stdout
    sys.exit(0)

while True:
    time.sleep(2)
    t = threading.Thread(target=check_haproxy,args=())
    t.daemon = False 
    t.start()
