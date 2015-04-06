#!/usr/bin/env python

'''Get Pods from Kubernetes'''

__author__ = 'pjs7678@pjs7678'

import getopt
import os
import sys
import json
import kubernetes
import time

from kubernetes import KubernetesError

USAGE = '''Usage: tweet [options] message

  This script get Pods from Kubernetes.

  Options:

    -h --help : print this help
    --url : the kubernetes master host
    --user-id : the kubernetes user id
    --user-pw : the kubernetes user password
    --encoding : the character set encoding used in input strings, e.g. "utf-8". [optional]

  Documentation:

  If either of the command line flags are not present, the environment
  variables KUBERNETESUSERNAME and KUBERNETESPASSWORD will then be checked for your
  user id or user password, respectively.

  If neither the command line flags nor the environment variables are
  present, the .kubernetes_auth file, if it exists, can be used to set the
  default user_id and user_password.  The file should contain the
  following five lines, replacing *User* with your user id, and
  *Password* with your user password:

  A skeletal .kubernetes_auth file:
      {
      "User": "admin",
      "Password": "hdrmCA3OXuL1lq12",
      "CAFile": "/Users/tigmi/.kubernetes.ca.crt",
      "CertFile": "/Users/tigmi/.kubecfg.crt",
      "KeyFile": "/Users/tigmi/.kubecfg.key"
      }
      '''

def PrintUsageAndExit():
    print USAGE
    sys.exit(2)

def GetUserIDKeyEnv():
    return os.environ.get("KUBERNETESUSERNAME", None)

def GetUserPasswordEnv():
    return os.environ.get("KUBERNETESPASSWORD", None)

class KubernetesRc(object):
    def __init__(self):
        pass

    def GetUserIdKey(self):
        return self._GetValue('User')

    def GetUserPasswordKey(self):
        return self._GetValue('Password')

    def _GetOption(self, option):
        try:
            return self._GetConfig().get(option)
        except:
            return None

    def _GetValue(self, key):
        if os.environ.get('KUBERNETES_PROVIDER') and os.environ.get('KUBERNETES_PROVIDER') is 'vagrant':
            path = '~/.kubernetes_vagrant_auth'
        else:
            path = '~/.kubernetes_auth'
            with open(os.path.expanduser(path)) as f:
                value = json.load(f)[key]
                return value

def main():
    try:
        shortflags = 'h'
        longflags = ['help', 'rc-data=', 'pod-data=', 'service-data=', 'version=', 'host=', 'namespace=', 'user-id=', 'user-pw=', 'url=', 'encoding=']
        opts, args = getopt.gnu_getopt(sys.argv[1:], shortflags, longflags)
    except getopt.GetoptError:
        PrintUsageAndExit()

    user_idflag = None
    user_passwordflag = None
    encoding = None
    url = None
    namespace = None
    version = 'v1beta3'
    host = '172.30.10.185'
    rc_data = None
    service_data = None
    pod_data = None
    for o, a in opts:
        #if o in ("-h", "--help"):
        #PrintUsageAndExit()
        #if o in ("--user-id"):
        #user_idflag = a
        #if o in ("--user-pw"):
        #user_passwordflag = a
        #if o in ("--encoding"):
        #encoding = a
        #if o in ("--url"):
        #url = a
        if o in ("--namespace"):
            namespace = a
        if o in ("--host"):
            host = a
        if o in ("--version"):
            version = a
        if o in ("--pod-data"):
            pod_data= a
        if o in ("--rc-data"):
            rc_data= a
        if o in ("--service-data"):
            service_data= a

    rc = KubernetesRc()
    #user_id = user_idflag or GetUserIDKeyEnv() or rc.GetUserIdKey()
    #user_password = user_passwordflag or GetUserPasswordEnv() or rc.GetUserPasswordKey()

    #print user_id
    #print user_password

    #if not user_id or not user_password:
    #PrintUsageAndExit()
    def _gen_url(host, version):
        return 'http://%s:8080/api/%s' % (host, version)
    api = kubernetes.Api(user_id=None, user_password=None,
                         input_encoding=encoding,
                         base_url=_gen_url(host, version),
                         debugHTTP=True)


    #try create first

    rc_obj = None
    try:
        if rc_data:
            f = open(rc_data)
            content = f.read()
            f.close()
            rc_obj = api.CreateRc(data=content, namespace=namespace)

        if service_data:
            f = open(service_data)
            content = f.read()
            api.CreateService(data=content, namespace=namespace)
    except KubernetesError,e:
        print e.message
    try:
        pod_list = api.GetPods(namespace=namespace, selector="nginx-test1")
        if rc_obj:
            while(pod_list.Items is None or (len(pod_list.Items) < rc_obj.DesiredState)):
                pod_list = api.GetPods(namespace=namespace, selector="nginx-test1")
                time.sleep(1)
        rc_list = api.GetReplicationControllers(namespace=namespace)
        srv_list = api.GetServices(namespace=namespace)
    except UnicodeDecodeError:
        print "Error!! "
        sys.exit(2)
    print "GetReplicationControllers: %s" % (rc_list.AsJsonString())
    print "GetPods: %s" % (pod_list.AsJsonString())
    print "GetServices: %s" % (srv_list.AsJsonString())

    try:
        if rc_list.Items:
            for rc in rc_list.Items:
                api.DeleteReplicationController(name=rc.Name, namespace=namespace)
                time.sleep(5)
        if pod_list.Items:
            while ((api.GetReplicationControllers(namespace)).Items):
                time.sleep(1)
            for pod in pod_list.Items:
                api.DeletePods(name=pod.Name, namespace=namespace)
        if srv_list.Items:
            for srv in srv_list.Items:
                api.DeleteService(name=srv.Name, namespace=namespace)
    except KubernetesError, e:
        print e.message

if __name__ == "__main__":
    main()
